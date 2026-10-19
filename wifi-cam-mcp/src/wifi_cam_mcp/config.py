"""Configuration for WiFi Camera MCP Server."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class CameraConfig:
    """Camera connection configuration."""

    host: str
    username: str
    password: str = field(repr=False)
    onvif_port: int = 2020
    stream_url: str | None = field(default=None, repr=False)
    max_width: int = 1920
    max_height: int = 1080
    mount_mode: str = "normal"  # "normal" (desktop) or "ceiling" (inverted)
    use_behavior_mount: bool = True  # Legacy shared override; false for named cameras

    @classmethod
    def from_env(cls, prefix: str = "TAPO") -> "CameraConfig":
        """Create config from environment variables.

        Args:
            prefix: Environment variable prefix (default: "TAPO")
                    For right camera, use "TAPO_RIGHT"
        """
        host = os.getenv(f"{prefix}_CAMERA_HOST", "") or os.getenv("TAPO_CAMERA_HOST", "")
        username = os.getenv(f"{prefix}_USERNAME", "") or os.getenv("TAPO_USERNAME", "")
        password = os.getenv(f"{prefix}_PASSWORD", "") or os.getenv("TAPO_PASSWORD", "")
        onvif_port = int(
            os.getenv(f"{prefix}_ONVIF_PORT", "") or os.getenv("TAPO_ONVIF_PORT", "") or "2020"
        )
        stream_url = os.getenv(f"{prefix}_STREAM_URL") or os.getenv("TAPO_STREAM_URL")
        mount_mode = (
            os.getenv(f"{prefix}_MOUNT_MODE", "") or os.getenv("TAPO_MOUNT_MODE", "") or "normal"
        ).lower()
        if mount_mode not in ("normal", "ceiling"):
            raise ValueError(f"Invalid mount mode '{mount_mode}'. Must be 'normal' or 'ceiling'.")
        max_width = int(os.getenv("CAPTURE_MAX_WIDTH", "1920"))
        max_height = int(os.getenv("CAPTURE_MAX_HEIGHT", "1080"))

        if not host:
            raise ValueError(f"{prefix}_CAMERA_HOST environment variable is required")
        if not username:
            raise ValueError(f"{prefix}_USERNAME environment variable is required")
        if not password:
            raise ValueError(f"{prefix}_PASSWORD environment variable is required")

        return cls(
            host=host,
            username=username,
            password=password,
            onvif_port=onvif_port,
            stream_url=stream_url,
            mount_mode=mount_mode,
            max_width=max_width,
            max_height=max_height,
        )

    @classmethod
    def right_camera_from_env(cls) -> "CameraConfig | None":
        """Create config for right camera if configured.

        Returns:
            CameraConfig for right camera, or None if not configured
        """
        host = os.getenv("TAPO_RIGHT_CAMERA_HOST", "")
        if not host:
            return None

        # Right camera can share username/password with left, or have its own
        username = os.getenv("TAPO_RIGHT_USERNAME", "") or os.getenv("TAPO_USERNAME", "")
        password = os.getenv("TAPO_RIGHT_PASSWORD", "") or os.getenv("TAPO_PASSWORD", "")
        onvif_port = int(
            os.getenv("TAPO_RIGHT_ONVIF_PORT", "") or os.getenv("TAPO_ONVIF_PORT", "") or "2020"
        )
        stream_url = os.getenv("TAPO_RIGHT_STREAM_URL")
        mount_mode = (
            os.getenv("TAPO_RIGHT_MOUNT_MODE", "") or os.getenv("TAPO_MOUNT_MODE", "") or "normal"
        ).lower()
        max_width = int(os.getenv("CAPTURE_MAX_WIDTH", "1920"))
        max_height = int(os.getenv("CAPTURE_MAX_HEIGHT", "1080"))

        if not username or not password:
            return None

        return cls(
            host=host,
            username=username,
            password=password,
            onvif_port=onvif_port,
            stream_url=stream_url,
            mount_mode=mount_mode,
            max_width=max_width,
            max_height=max_height,
        )


@dataclass(frozen=True)
class ServerConfig:
    """MCP Server configuration."""

    name: str = "wifi-cam-mcp"
    version: str = "0.1.0"
    capture_dir: str = "/tmp/wifi-cam-mcp"
    mic_source: str = "camera"  # "camera" (RTSP) or "local" (PC microphone)

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Create config from environment variables."""
        mic_source = os.getenv("MIC_SOURCE", "camera").lower()
        if mic_source not in ("camera", "local"):
            raise ValueError(f"Invalid MIC_SOURCE '{mic_source}'. Must be 'camera' or 'local'.")
        return cls(
            name=os.getenv("MCP_SERVER_NAME", "wifi-cam-mcp"),
            version=os.getenv("MCP_SERVER_VERSION", "0.1.0"),
            capture_dir=os.getenv("CAPTURE_DIR", "/tmp/wifi-cam-mcp"),
            mic_source=mic_source,
        )


@dataclass(frozen=True)
class CameraInventory:
    """Named connections; credentials are excluded from their representation."""

    cameras: dict[str, CameraConfig]
    default_camera: str
    stereo_pair: tuple[str, str] | None = None


def load_camera_inventory() -> CameraInventory:
    """Load project cameras, or preserve the legacy environment-only setup.

    An explicitly selected missing/invalid file is an error, never a fallback.
    The default project file is optional so existing single/stereo setups work.
    """
    override = os.getenv("WIFI_CAMERAS_TOML")
    path = Path(override) if override else Path(__file__).resolve().parents[3] / "wifi-cameras.toml"
    if not override and not path.exists():
        cameras = {"primary": CameraConfig.from_env()}
        right = CameraConfig.right_camera_from_env()
        if right:
            cameras["right"] = right
        return CameraInventory(cameras, "primary", ("primary", "right") if right else None)
    # Credentials can be inline or reference the package's .env/environment.
    with path.open("rb") as file:
        data = tomllib.load(file)
    entries = data.get("cameras")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Camera file must contain at least one [cameras.<id>] table")
    cameras = {}
    allowed = {
        "host",
        "username",
        "password",
        "username_env",
        "password_env",
        "onvif_port",
        "stream_url_env",
        "max_width",
        "max_height",
        "mount_mode",
    }
    for camera_id, entry in entries.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", camera_id):
            raise ValueError("Camera IDs must use letters, digits, underscores or hyphens")
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError(f"Invalid settings for camera {camera_id}")
        host = entry.get("host")
        if not isinstance(host, str) or not host.strip():
            raise ValueError(f"Camera {camera_id} requires host")
        credentials = {}
        for key in ("username", "password"):
            if key in entry:
                value = entry[key]
                if not isinstance(value, str) or not value:
                    raise ValueError(f"Camera {camera_id}: {key} must be a non-empty string")
                credentials[key] = value
                continue
            variable = entry.get(f"{key}_env")
            if not isinstance(variable, str) or not variable:
                raise ValueError(f"Camera {camera_id} requires {key} or {key}_env")
            value = os.getenv(variable)
            if not value:
                raise ValueError(f"Camera {camera_id}: environment variable {variable} is required")
            credentials[key] = value
        mount = entry.get("mount_mode", "normal")
        if mount not in ("normal", "ceiling"):
            raise ValueError(f"Camera {camera_id}: invalid mount_mode")
        dimensions = {}
        for key, default in (("onvif_port", 2020), ("max_width", 1920), ("max_height", 1080)):
            value = entry.get(key, default)
            if type(value) is not int or value < 1 or (key == "onvif_port" and value > 65535):
                raise ValueError(f"Camera {camera_id}: invalid {key}")
            dimensions[key] = value
        stream_variable = entry.get("stream_url_env")
        if stream_variable is not None and (
            not isinstance(stream_variable, str) or not os.getenv(stream_variable)
        ):
            raise ValueError(
                f"Camera {camera_id}: stream_url_env must name a set environment variable"
            )
        cameras[camera_id] = CameraConfig(
            host=host,
            **credentials,
            **dimensions,
            mount_mode=mount,
            stream_url=os.getenv(stream_variable) if stream_variable else None,
            use_behavior_mount=False,
        )
    default = data.get("default_camera", next(iter(cameras)))
    if not isinstance(default, str) or default not in cameras:
        raise ValueError("default_camera must name a configured camera")
    pair = data.get("stereo_pair")
    if pair is not None and (
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(name, str) or name not in cameras for name in pair)
        or pair[0] == pair[1]
    ):
        raise ValueError("stereo_pair must name two distinct configured cameras")
    return CameraInventory(cameras, default, tuple(pair) if pair else None)
