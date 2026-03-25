"""Tests for VisionSense."""

import pytest

from mcp_pet.config import VisionConfig
from mcp_pet.senses.vision import VisionSense
from mcp_pet.types import SenseStatus


class TestVisionSense:
    def test_name(self):
        config = VisionConfig(usb_enabled=False)
        sense = VisionSense(config)
        assert sense.name == "vision"

    def test_get_tools_usb_only(self):
        config = VisionConfig(usb_enabled=True)
        sense = VisionSense(config)
        # Before initialize, no ONVIF tools
        tools = sense.get_tools()
        tool_names = [t.name for t in tools]
        assert "see" in tool_names
        assert "list_cameras" in tool_names
        assert "look" not in tool_names
        assert "look_around" not in tool_names

    def test_get_status_no_hardware(self):
        config = VisionConfig(usb_enabled=False)
        sense = VisionSense(config)
        status = sense.get_status()
        assert status.name == "vision"
        assert status.available is False

    @pytest.mark.asyncio
    async def test_see_no_camera_returns_error(self):
        config = VisionConfig(usb_enabled=False)
        sense = VisionSense(config)
        await sense.initialize()
        result = await sense.call_tool("see", {})
        assert result is not None
        assert len(result) == 1
        assert "No camera available" in result[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_none(self):
        config = VisionConfig(usb_enabled=False)
        sense = VisionSense(config)
        result = await sense.call_tool("nonexistent_tool", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self):
        config = VisionConfig(usb_enabled=False)
        sense = VisionSense(config)
        await sense.shutdown()
        await sense.shutdown()  # Should not raise
