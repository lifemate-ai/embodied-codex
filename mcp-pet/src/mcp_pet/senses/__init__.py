"""Sense discovery and registration."""

from __future__ import annotations

from ..config import PETConfig
from .base import Sense
from .vision import VisionSense


def discover_senses(config: PETConfig) -> list[Sense]:
    """Discover and instantiate available senses based on configuration."""
    senses: list[Sense] = []

    # Vision is always instantiated; it handles USB/ONVIF availability internally
    senses.append(VisionSense(config.vision, capture_dir=config.capture_dir))

    return senses
