"""Vision sense — USB webcam + optional ONVIF PTZ camera."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from typing import Any

from mcp.types import ImageContent, TextContent, Tool

from ..config import VisionConfig
from ..types import CaptureResult, Direction, SenseStatus
from .base import Sense

# Suppress OpenCV logging noise
os.environ["OPENCV_LOG_LEVEL"] = "OFF"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"

logger = logging.getLogger(__name__)


class VisionSense(Sense):
    """Vision sense combining USB webcam and optional ONVIF PTZ camera."""

    def __init__(self, config: VisionConfig, capture_dir: str = "/tmp/mcp-pet") -> None:
        self._config = config
        self._capture_dir = capture_dir

        self._usb_available = False
        self._onvif_adapter = None  # type: ignore[assignment]
        self._onvif_available = False
        self._skyway_available = False

    @property
    def name(self) -> str:
        return "vision"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        # USB: probe the configured camera index
        if self._config.usb_enabled:
            try:
                available = await asyncio.to_thread(self._probe_usb)
                self._usb_available = available
                if available:
                    logger.info("USB camera available at index %d", self._config.usb_index)
                else:
                    logger.warning("USB camera at index %d not found", self._config.usb_index)
            except Exception as e:
                logger.warning("USB camera probe failed: %s", e)
                self._usb_available = False

        # SkyWay: check if frame path exists
        if self._config.skyway_enabled:
            from pathlib import Path

            frame_path = Path(self._config.skyway_frame_path)
            if frame_path.parent.exists():
                self._skyway_available = True
                logger.info("SkyWay frame source configured: %s", self._config.skyway_frame_path)
            else:
                logger.warning("SkyWay frame directory not found: %s", frame_path.parent)

        # ONVIF: attempt connection if configured
        if self._config.onvif_enabled:
            try:
                from ._onvif_adapter import ONVIFAdapter

                self._onvif_adapter = ONVIFAdapter(self._config, capture_dir=self._capture_dir)
                await self._onvif_adapter.connect()
                self._onvif_available = True
                logger.info("ONVIF camera connected at %s", self._config.onvif_host)
            except ImportError:
                logger.warning("ONVIF dependencies not installed (pip install mcp-pet[ptz])")
                self._onvif_available = False
            except Exception as e:
                logger.warning("ONVIF camera connection failed: %s", e)
                self._onvif_available = False

    async def shutdown(self) -> None:
        if self._onvif_adapter is not None:
            try:
                await self._onvif_adapter.disconnect()
            except Exception:
                pass
            self._onvif_adapter = None
            self._onvif_available = False
        self._usb_available = False
        self._skyway_available = False

    # ------------------------------------------------------------------
    # USB helpers
    # ------------------------------------------------------------------

    def _probe_usb(self) -> bool:
        import cv2

        cap = cv2.VideoCapture(self._config.usb_index)
        opened = cap.isOpened()
        cap.release()
        return opened

    def _capture_usb(self) -> CaptureResult:
        """Capture image from USB webcam (blocking — run via to_thread)."""
        import cv2
        from PIL import Image

        cap = cv2.VideoCapture(self._config.usb_index)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open USB camera at index {self._config.usb_index}")

        try:
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()
            if not ret:
                raise RuntimeError("Failed to capture image from USB camera")

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)

            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            from datetime import datetime

            return CaptureResult(
                image_base64=image_base64,
                timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
                width=image.width,
                height=image.height,
                source="usb",
            )
        finally:
            cap.release()

    def _find_available_cameras(self, max_cameras: int = 10) -> list[dict[str, Any]]:
        """Find available USB camera devices (blocking)."""
        import cv2

        cameras = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras.append({"index": i, "width": width, "height": height})
                cap.release()
        return cameras

    # ------------------------------------------------------------------
    # SkyWay helpers
    # ------------------------------------------------------------------

    def _capture_skyway(self) -> CaptureResult:
        """Read the latest frame saved by SkyWay embodied handler (blocking)."""
        import base64
        from datetime import datetime
        from pathlib import Path

        from PIL import Image

        frame_path = Path(self._config.skyway_frame_path)
        if not frame_path.exists():
            raise RuntimeError(f"SkyWay frame not found: {frame_path}")

        image = Image.open(frame_path)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return CaptureResult(
            image_base64=image_base64,
            timestamp=datetime.now().strftime("%Y%m%d_%H%M%S"),
            width=image.width,
            height=image.height,
            source="skyway",
        )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tools(self) -> list[Tool]:
        tools = [
            Tool(
                name="see",
                description=(
                    "See what's in front of you right now. "
                    "Returns the current view as an image."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "Camera source: 'auto' (default), 'usb', 'onvif', or 'skyway'",
                            "default": "auto",
                            "enum": ["auto", "usb", "onvif", "skyway"],
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="list_cameras",
                description="List available camera devices.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

        # PTZ tools only when ONVIF is available
        if self._onvif_available:
            tools.extend([
                Tool(
                    name="look",
                    description=(
                        "Turn your head to look in a direction. "
                        "Use this to look left, right, up, or down."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "direction": {
                                "type": "string",
                                "description": "Direction to look: left, right, up, down",
                                "enum": ["left", "right", "up", "down"],
                            },
                            "degrees": {
                                "type": "integer",
                                "description": "How far to turn (1-90 degrees, default: 30)",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 90,
                            },
                        },
                        "required": ["direction"],
                    },
                ),
                Tool(
                    name="look_around",
                    description=(
                        "Look around the room by turning to see multiple angles "
                        "(center, left, right, up). Returns multiple images."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            ])

        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[TextContent | ImageContent] | None:
        match name:
            case "see":
                return await self._handle_see(arguments)
            case "list_cameras":
                return await self._handle_list_cameras()
            case "look":
                return await self._handle_look(arguments)
            case "look_around":
                return await self._handle_look_around()
            case _:
                return None

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    async def _handle_see(
        self, arguments: dict[str, Any]
    ) -> list[TextContent | ImageContent]:
        source = arguments.get("source", "auto")

        if source == "auto":
            # Prefer ONVIF → SkyWay → USB
            if self._onvif_available:
                source = "onvif"
            elif self._skyway_available:
                source = "skyway"
            elif self._usb_available:
                source = "usb"
            else:
                return [TextContent(type="text", text="Error: No camera available")]

        if source == "usb":
            if not self._usb_available:
                return [TextContent(type="text", text="Error: USB camera not available")]
            try:
                result = await asyncio.to_thread(self._capture_usb)
                return [
                    ImageContent(type="image", data=result.image_base64, mimeType="image/jpeg"),
                    TextContent(
                        type="text",
                        text=f"Captured via USB at {result.timestamp} ({result.width}x{result.height})",
                    ),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Error capturing from USB: {e}")]

        if source == "onvif":
            if not self._onvif_available:
                return [TextContent(type="text", text="Error: ONVIF camera not available")]
            try:
                result = await self._onvif_adapter.capture_image()
                return [
                    ImageContent(type="image", data=result.image_base64, mimeType="image/jpeg"),
                    TextContent(
                        type="text",
                        text=f"Captured via ONVIF at {result.timestamp} ({result.width}x{result.height})",
                    ),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Error capturing from ONVIF: {e}")]

        if source == "skyway":
            if not self._skyway_available:
                return [TextContent(type="text", text="Error: SkyWay source not configured")]
            try:
                result = await asyncio.to_thread(self._capture_skyway)
                return [
                    ImageContent(type="image", data=result.image_base64, mimeType="image/jpeg"),
                    TextContent(
                        type="text",
                        text=f"Captured via SkyWay at {result.timestamp} ({result.width}x{result.height})",
                    ),
                ]
            except Exception as e:
                return [TextContent(type="text", text=f"Error reading SkyWay frame: {e}")]

        return [TextContent(type="text", text=f"Unknown source: {source}")]

    async def _handle_list_cameras(self) -> list[TextContent | ImageContent]:
        lines = ["Available cameras:"]

        # USB cameras
        try:
            cameras = await asyncio.to_thread(self._find_available_cameras)
            for cam in cameras:
                lines.append(f"  - USB index {cam['index']}: {cam['width']}x{cam['height']}")
        except Exception as e:
            lines.append(f"  - USB: error scanning ({e})")

        # ONVIF camera
        if self._onvif_available:
            lines.append(f"  - ONVIF: {self._config.onvif_host} (connected)")
        elif self._config.onvif_enabled:
            lines.append(f"  - ONVIF: {self._config.onvif_host} (not connected)")

        # SkyWay remote
        if self._skyway_available:
            lines.append(f"  - SkyWay: {self._config.skyway_frame_path} (active)")
        elif self._config.skyway_enabled:
            lines.append(f"  - SkyWay: {self._config.skyway_frame_path} (configured, dir not found)")

        if len(lines) == 1:
            lines.append("  (none found)")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_look(
        self, arguments: dict[str, Any]
    ) -> list[TextContent | ImageContent]:
        if not self._onvif_available:
            return [TextContent(type="text", text="Error: PTZ camera not available")]

        direction_str = arguments.get("direction", "")
        degrees = arguments.get("degrees", 30)

        try:
            direction = Direction(direction_str)
        except ValueError:
            return [TextContent(type="text", text=f"Invalid direction: {direction_str}")]

        result = await self._onvif_adapter.move(direction, degrees)
        return [TextContent(type="text", text=result.message)]

    async def _handle_look_around(self) -> list[TextContent | ImageContent]:
        if not self._onvif_available:
            return [TextContent(type="text", text="Error: PTZ camera not available")]

        captures = await self._onvif_adapter.look_around()
        contents: list[TextContent | ImageContent] = []
        directions = ["Center", "Left", "Right", "Up"]

        for i, capture in enumerate(captures):
            label = directions[i] if i < len(directions) else f"Angle {i}"
            contents.append(TextContent(type="text", text=f"--- {label} View ---"))
            contents.append(
                ImageContent(type="image", data=capture.image_base64, mimeType="image/jpeg")
            )

        contents.append(
            TextContent(
                type="text",
                text=f"Captured {len(captures)} angles. Camera returned to center.",
            )
        )
        return contents

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> SenseStatus:
        details: dict[str, str] = {}

        if self._usb_available:
            details["usb"] = f"index {self._config.usb_index} (available)"
        elif self._config.usb_enabled:
            details["usb"] = f"index {self._config.usb_index} (not found)"

        if self._onvif_available:
            details["onvif"] = f"{self._config.onvif_host} (connected)"
        elif self._config.onvif_enabled:
            details["onvif"] = f"{self._config.onvif_host} (not connected)"

        if self._skyway_available:
            details["skyway"] = f"{self._config.skyway_frame_path} (active)"
        elif self._config.skyway_enabled:
            details["skyway"] = f"{self._config.skyway_frame_path} (dir not found)"

        return SenseStatus(
            name=self.name,
            available=self._usb_available or self._onvif_available or self._skyway_available,
            details=details,
        )
