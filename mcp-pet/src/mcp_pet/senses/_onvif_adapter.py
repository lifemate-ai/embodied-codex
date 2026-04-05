"""ONVIF PTZ camera adapter.

Handles connection lifecycle, image capture (ONVIF snapshot + RTSP fallback),
and PTZ control via RelativeMove. Adapted from wifi-cam-mcp's TapoCamera.

Requires optional dependency: pip install mcp-pet[ptz]
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

from ..config import VisionConfig
from ..types import CaptureResult, Direction, MoveResult

logger = logging.getLogger(__name__)

# Degree <-> ONVIF normalized conversion
PAN_RANGE_DEGREES = 180.0
TILT_RANGE_DEGREES = 90.0

MAX_RECONNECT_RETRIES = 2
RECONNECT_DELAY = 1.0


def _degrees_to_normalized_pan(degrees: float) -> float:
    return max(-1.0, min(1.0, degrees / PAN_RANGE_DEGREES))


def _degrees_to_normalized_tilt(degrees: float) -> float:
    return max(-1.0, min(1.0, degrees / TILT_RANGE_DEGREES))


@dataclass
class CameraPosition:
    """Software-tracked PTZ position."""

    pan: float = 0.0
    tilt: float = 0.0


class ONVIFAdapter:
    """ONVIF PTZ camera adapter for Tapo C210/C220 and compatible cameras."""

    def __init__(self, config: VisionConfig, capture_dir: str = "/tmp/mcp-pet") -> None:
        self._config = config
        self._capture_dir = Path(capture_dir)
        self._lock = asyncio.Lock()

        self._cam = None
        self._media_service = None
        self._ptz_service = None
        self._profile_token: str | None = None

        self._sw_position = CameraPosition()
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish ONVIF connection."""
        async with self._lock:
            if self._connected:
                return
            await self._do_connect()

    async def _do_connect(self) -> None:
        import os

        import onvif
        from onvif import ONVIFCamera

        logger.info("Connecting to ONVIF camera at %s:%d...", self._config.onvif_host, self._config.onvif_port)

        onvif_dir = os.path.dirname(onvif.__file__)
        wsdl_dir = os.path.join(onvif_dir, "wsdl")
        if not os.path.isdir(wsdl_dir):
            wsdl_dir = os.path.join(os.path.dirname(onvif_dir), "wsdl")

        self._cam = ONVIFCamera(
            self._config.onvif_host,
            self._config.onvif_port,
            self._config.onvif_username,
            self._config.onvif_password,
            wsdl_dir=wsdl_dir,
            adjust_time=True,
        )
        await self._cam.update_xaddrs()

        if self._config.onvif_host in ("localhost", "127.0.0.1"):
            for key, url in self._cam.xaddrs.items():
                self._cam.xaddrs[key] = re.sub(
                    r"http://[\d.]+:(\d+)", r"http://localhost:\1", url
                )

        self._media_service = await self._cam.create_media_service()
        self._ptz_service = await self._cam.create_ptz_service()

        profiles = await self._media_service.GetProfiles()
        if not profiles:
            raise RuntimeError("No media profiles found on camera")
        self._profile_token = profiles[0].token

        self._capture_dir.mkdir(parents=True, exist_ok=True)
        self._connected = True
        logger.info("Connected to ONVIF camera (profile=%s, mount=%s)", self._profile_token, self._config.onvif_mount_mode)

    async def disconnect(self) -> None:
        async with self._lock:
            if self._cam is not None:
                try:
                    await self._cam.close()
                except Exception:
                    pass
            self._cam = None
            self._media_service = None
            self._ptz_service = None
            self._profile_token = None
            self._connected = False

    async def _ensure_connected(self) -> None:
        if self._connected and self._cam is not None:
            return
        async with self._lock:
            if self._connected and self._cam is not None:
                return
            logger.warning("ONVIF camera not connected, attempting reconnect...")
            for attempt in range(1, MAX_RECONNECT_RETRIES + 1):
                try:
                    await self._do_connect()
                    return
                except Exception as e:
                    logger.error("Reconnect attempt %d failed: %s", attempt, e)
                    if attempt < MAX_RECONNECT_RETRIES:
                        await asyncio.sleep(RECONNECT_DELAY)
            raise RuntimeError(f"ONVIF camera not connected after {MAX_RECONNECT_RETRIES} attempts")

    async def _with_reconnect(self, operation, *args, **kwargs):
        try:
            await self._ensure_connected()
            return await operation(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if any(kw in error_str for kw in ("connection", "timeout", "refused", "reset", "broken")):
                logger.warning("Connection error, reconnecting: %s", e)
                self._connected = False
                self._cam = None
                await self._ensure_connected()
                return await operation(*args, **kwargs)
            raise

    # ------------------------------------------------------------------
    # Image capture
    # ------------------------------------------------------------------

    async def capture_image(self, save_to_file: bool = False) -> CaptureResult:
        return await self._with_reconnect(self._capture_image_impl, save_to_file)

    async def _capture_image_impl(self, save_to_file: bool) -> CaptureResult:
        image_data = None
        try:
            image_data = await self._try_onvif_snapshot()
        except Exception:
            pass

        if image_data is None:
            logger.info("ONVIF snapshot unavailable, falling back to RTSP")
            image_data = await self._capture_via_rtsp()

        image = Image.open(io.BytesIO(image_data))

        if self._config.onvif_mount_mode != "ceiling":
            image = image.rotate(180)

        if image.width > self._config.capture_max_width or image.height > self._config.capture_max_height:
            image.thumbnail(
                (self._config.capture_max_width, self._config.capture_max_height),
                Image.LANCZOS,
            )

        width, height = image.size
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_base64 = base64.standard_b64encode(buffer.getvalue()).decode("utf-8")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = None
        if save_to_file:
            file_path = str(self._capture_dir / f"capture_{timestamp}.jpg")
            with open(file_path, "wb") as f:
                f.write(buffer.getvalue())

        return CaptureResult(
            image_base64=image_base64,
            timestamp=timestamp,
            width=width,
            height=height,
            source="onvif",
            file_path=file_path,
        )

    async def _try_onvif_snapshot(self) -> bytes | None:
        try:
            image_bytes = await self._cam.get_snapshot(self._profile_token)
            if image_bytes and len(image_bytes) > 0:
                return image_bytes
        except Exception as e:
            logger.debug("ONVIF snapshot failed: %s", e)
        return None

    async def _capture_via_rtsp(self) -> bytes:
        try:
            return await self._capture_rtsp_stream(self._get_rtsp_url(sub_stream=False))
        except Exception:
            return await self._capture_rtsp_stream(self._get_rtsp_url(sub_stream=True))

    async def _capture_rtsp_stream(self, rtsp_url: str) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cmd = [
                "ffmpeg", "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-frames:v", "1", "-f", "image2", "-y", tmp_path,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr_data = await asyncio.wait_for(process.communicate(), timeout=10.0)
            except asyncio.TimeoutError:
                process.kill()
                raise RuntimeError("RTSP capture timed out after 10s")

            if process.returncode != 0:
                stderr_msg = stderr_data.decode(errors="replace").strip()[-500:]
                raise RuntimeError(f"ffmpeg RTSP capture failed (rc={process.returncode}): {stderr_msg}")

            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _get_rtsp_url(self, sub_stream: bool = False) -> str:
        if self._config.onvif_stream_url:
            return self._config.onvif_stream_url
        stream = "stream2" if sub_stream else "stream1"
        return (
            f"rtsp://{self._config.onvif_username}:{self._config.onvif_password}"
            f"@{self._config.onvif_host}:554/{stream}"
        )

    # ------------------------------------------------------------------
    # PTZ control
    # ------------------------------------------------------------------

    async def move(self, direction: Direction, degrees: int = 30) -> MoveResult:
        return await self._with_reconnect(self._move_impl, direction, degrees)

    async def _move_impl(self, direction: Direction, degrees: int) -> MoveResult:
        degrees = max(1, min(degrees, 90))

        pan_delta = 0.0
        tilt_delta = 0.0

        match direction:
            case Direction.LEFT:
                pan_delta = -_degrees_to_normalized_pan(degrees)
            case Direction.RIGHT:
                pan_delta = _degrees_to_normalized_pan(degrees)
            case Direction.UP:
                tilt_delta = -_degrees_to_normalized_tilt(degrees)
            case Direction.DOWN:
                tilt_delta = _degrees_to_normalized_tilt(degrees)

        if self._config.onvif_mount_mode == "ceiling":
            pan_delta = -pan_delta
            tilt_delta = -tilt_delta

        try:
            await self._ptz_service.RelativeMove({
                "ProfileToken": self._profile_token,
                "Translation": {
                    "PanTilt": {"x": pan_delta, "y": tilt_delta},
                },
            })

            match direction:
                case Direction.LEFT:
                    self._sw_position.pan = max(-180.0, self._sw_position.pan - degrees)
                case Direction.RIGHT:
                    self._sw_position.pan = min(180.0, self._sw_position.pan + degrees)
                case Direction.UP:
                    self._sw_position.tilt = min(90.0, self._sw_position.tilt + degrees)
                case Direction.DOWN:
                    self._sw_position.tilt = max(-90.0, self._sw_position.tilt - degrees)

            await asyncio.sleep(0.5)

            return MoveResult(
                direction=direction,
                degrees=degrees,
                success=True,
                message=f"Moved {direction.value} by {degrees} degrees",
            )
        except Exception as e:
            return MoveResult(
                direction=direction,
                degrees=degrees,
                success=False,
                message=f"Failed to move: {e!s}",
            )

    async def look_around(self) -> list[CaptureResult]:
        """Capture from 4 angles: center, left, right, up."""
        captures: list[CaptureResult] = []

        captures.append(await self.capture_image())

        await self.move(Direction.LEFT, 45)
        captures.append(await self.capture_image())

        await self.move(Direction.RIGHT, 90)
        captures.append(await self.capture_image())

        await self.move(Direction.LEFT, 45)
        await self.move(Direction.UP, 20)
        captures.append(await self.capture_image())

        await self.move(Direction.DOWN, 20)

        return captures

    def get_position(self) -> CameraPosition:
        return CameraPosition(pan=self._sw_position.pan, tilt=self._sw_position.tilt)

    def reset_position(self) -> None:
        self._sw_position = CameraPosition()
