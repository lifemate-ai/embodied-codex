"""Shared types for mcp-pet."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Direction(str, Enum):
    """Pan/Tilt directions."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class CaptureResult:
    """Result of image capture."""

    image_base64: str
    timestamp: str
    width: int
    height: int
    source: str = "usb"  # "usb" or "onvif"
    file_path: str | None = None


@dataclass(frozen=True)
class MoveResult:
    """Result of camera movement."""

    direction: Direction
    degrees: int
    success: bool
    message: str


@dataclass(frozen=True)
class SenseStatus:
    """Status of a single sense."""

    name: str
    available: bool
    details: dict[str, str] = field(default_factory=dict)
