"""Sense plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mcp.types import ImageContent, TextContent, Tool

from ..types import SenseStatus


class Sense(ABC):
    """Abstract base class for a PET sense.

    Each sense represents a category of perception (vision, hearing, etc.)
    and exposes MCP tools dynamically based on available hardware.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Sense identifier (e.g. 'vision', 'hearing')."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize hardware connections.

        Must NOT raise on failure — a sense that fails to initialize
        simply reports itself as unavailable via get_status().
        """
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Release hardware resources."""
        ...

    @abstractmethod
    def get_tools(self) -> list[Tool]:
        """Return tools available given current hardware state.

        The list may change after initialize() completes (e.g. PTZ tools
        appear only when an ONVIF camera is connected).
        """
        ...

    @abstractmethod
    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[TextContent | ImageContent] | None:
        """Execute a tool by name.

        Returns:
            Tool output, or None if this sense does not own the tool.
        """
        ...

    @abstractmethod
    def get_status(self) -> SenseStatus:
        """Return diagnostic status for this sense."""
        ...
