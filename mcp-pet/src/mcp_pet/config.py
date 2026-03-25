"""Configuration for mcp-pet."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VisionConfig:
    """Vision sense configuration."""

    # USB webcam
    usb_enabled: bool = True
    usb_index: int = 0

    # ONVIF PTZ camera (optional)
    onvif_host: str = ""
    onvif_username: str = ""
    onvif_password: str = ""
    onvif_port: int = 2020
    onvif_mount_mode: str = "normal"  # "normal" or "ceiling"
    onvif_stream_url: str = ""

    # SkyWay remote camera (reads latest frame from disk)
    skyway_frame_path: str = ""

    # Capture settings
    capture_max_width: int = 1920
    capture_max_height: int = 1080

    @property
    def onvif_enabled(self) -> bool:
        return bool(self.onvif_host)

    @property
    def skyway_enabled(self) -> bool:
        return bool(self.skyway_frame_path)

    @classmethod
    def from_env(cls) -> VisionConfig:
        """Create from PET_ prefixed environment variables."""
        onvif_mount = os.getenv("PET_VISION_ONVIF_MOUNT", "normal").lower()
        if onvif_mount not in ("normal", "ceiling"):
            raise ValueError(f"Invalid mount mode '{onvif_mount}'. Must be 'normal' or 'ceiling'.")

        return cls(
            usb_enabled=os.getenv("PET_VISION_USB", "true").lower() in ("true", "1", "yes"),
            usb_index=int(os.getenv("PET_VISION_USB_INDEX", "0")),
            onvif_host=os.getenv("PET_VISION_ONVIF_HOST", ""),
            onvif_username=os.getenv("PET_VISION_ONVIF_USERNAME", ""),
            onvif_password=os.getenv("PET_VISION_ONVIF_PASSWORD", ""),
            onvif_port=int(os.getenv("PET_VISION_ONVIF_PORT", "2020")),
            onvif_mount_mode=onvif_mount,
            onvif_stream_url=os.getenv("PET_VISION_ONVIF_STREAM_URL", ""),
            skyway_frame_path=os.getenv("PET_VISION_SKYWAY_FRAME", ""),
            capture_max_width=int(os.getenv("PET_CAPTURE_MAX_WIDTH", "1920")),
            capture_max_height=int(os.getenv("PET_CAPTURE_MAX_HEIGHT", "1080")),
        )


@dataclass(frozen=True)
class ServerConfig:
    """Built-in web server configuration (optional)."""

    port: int = 0  # 0 = disabled
    host: str = "0.0.0.0"
    skyway_key: str = ""
    skyway_room: str = "mcp-pet"
    save_interval: float = 10.0  # seconds between frame saves

    @property
    def enabled(self) -> bool:
        return self.port > 0

    @classmethod
    def from_env(cls) -> ServerConfig:
        return cls(
            port=int(os.getenv("PET_SERVER_PORT", "0")),
            host=os.getenv("PET_SERVER_HOST", "0.0.0.0"),
            skyway_key=os.getenv("PET_SKYWAY_KEY", ""),
            skyway_room=os.getenv("PET_SKYWAY_ROOM", "mcp-pet"),
            save_interval=float(os.getenv("PET_SAVE_INTERVAL", "10")),
        )


@dataclass(frozen=True)
class PETConfig:
    """Top-level PET configuration."""

    name: str = "mcp-pet"
    version: str = "0.1.0"
    capture_dir: str = "/tmp/mcp-pet"
    vision: VisionConfig = VisionConfig()
    server: ServerConfig = ServerConfig()

    @classmethod
    def from_env(cls) -> PETConfig:
        """Create from environment variables."""
        vision = VisionConfig.from_env()
        server = ServerConfig.from_env()
        capture_dir = os.getenv("PET_CAPTURE_DIR", "/tmp/mcp-pet")

        # Auto-configure: if server is enabled and no skyway path set,
        # point to our own frames directory
        if server.enabled and not vision.skyway_frame_path:
            vision = VisionConfig(
                usb_enabled=vision.usb_enabled,
                usb_index=vision.usb_index,
                onvif_host=vision.onvif_host,
                onvif_username=vision.onvif_username,
                onvif_password=vision.onvif_password,
                onvif_port=vision.onvif_port,
                onvif_mount_mode=vision.onvif_mount_mode,
                onvif_stream_url=vision.onvif_stream_url,
                skyway_frame_path=os.path.join(capture_dir, "latest.jpg"),
                capture_max_width=vision.capture_max_width,
                capture_max_height=vision.capture_max_height,
            )

        return cls(
            name=os.getenv("PET_NAME", "mcp-pet"),
            version=os.getenv("PET_VERSION", "0.1.0"),
            capture_dir=capture_dir,
            vision=vision,
            server=server,
        )
