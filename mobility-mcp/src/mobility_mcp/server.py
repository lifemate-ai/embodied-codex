"""MCP Server for Robot Vacuum Mobility Control - Let AI walk!"""

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import TuyaCloudConfig, get_max_move_duration
from .vacuum import VacuumMobilityController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MobilityMCPServer:
    """MCP Server that gives AI legs to move around the room."""

    def __init__(self):
        self._server = Server("mobility-mcp")
        self._controller: VacuumMobilityController | None = None
        self._setup_handlers()

    def _ensure_controller(self) -> VacuumMobilityController:
        """Get or create the vacuum controller."""
        if self._controller is None:
            config = TuyaCloudConfig.from_env()
            self._controller = VacuumMobilityController(config)
        return self._controller

    def _clamp_duration(self, duration: float | None) -> float | None:
        """Clamp duration to safe range."""
        if duration is None:
            return None
        return max(0.1, min(duration, get_max_move_duration()))

    def _setup_handlers(self) -> None:
        """Set up MCP tool handlers."""

        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available mobility tools."""
            max_dur = get_max_move_duration()
            duration_schema = {
                "type": "number",
                "description": (
                    "How long to move in seconds (default: continuous until stop). "
                    f"Max: {max_dur}s."
                ),
                "minimum": 0.1,
                "maximum": max_dur,
            }
            return [
                Tool(
                    name="move_forward",
                    description=(
                        "Move your body forward. Use this when you want to go "
                        "toward something you see in front of you. Optionally "
                        "specify duration in seconds."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {"duration": duration_schema},
                        "required": [],
                    },
                ),
                Tool(
                    name="move_backward",
                    description=(
                        "Move your body backward. Use this to back away from "
                        "something. Optionally specify duration in seconds."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {"duration": duration_schema},
                        "required": [],
                    },
                ),
                Tool(
                    name="turn_left",
                    description=(
                        "Turn your body to the left. This rotates your entire "
                        "body (not just your head/camera). Optionally specify "
                        "duration in seconds."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {"duration": duration_schema},
                        "required": [],
                    },
                ),
                Tool(
                    name="turn_right",
                    description=(
                        "Turn your body to the right. This rotates your entire "
                        "body (not just your head/camera). Optionally specify "
                        "duration in seconds."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {"duration": duration_schema},
                        "required": [],
                    },
                ),
                Tool(
                    name="stop_moving",
                    description=(
                        "Stop all body movement immediately. Use this to halt "
                        "when you've reached where you want to be."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="body_status",
                    description=(
                        "Check the status of your body (robot vacuum). Shows "
                        "battery level and current state."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="start_cleaning",
                    description=(
                        "Start smart cleaning mode. Use this to make the robot "
                        "leave the charging dock and begin cleaning."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="stop_cleaning",
                    description=(
                        "Stop the current cleaning session and enter manual-ready standby. "
                        "Call this after start_cleaning to switch from auto-cleaning to "
                        "manual movement mode. After this, move_forward/turn_left etc. "
                        "work without the robot resuming auto-cleaning."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="return_to_dock",
                    description=(
                        "Return your body (robot vacuum) to the charging dock. "
                        "Use this when the battery is low or you are done moving."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            """Handle tool calls."""
            controller = self._ensure_controller()

            try:
                if name == "move_forward":
                    duration = self._clamp_duration(arguments.get("duration"))
                    result = await controller.move_forward(duration)

                elif name == "move_backward":
                    duration = self._clamp_duration(arguments.get("duration"))
                    result = await controller.move_backward(duration)

                elif name == "turn_left":
                    duration = self._clamp_duration(arguments.get("duration"))
                    result = await controller.turn_left(duration)

                elif name == "turn_right":
                    duration = self._clamp_duration(arguments.get("duration"))
                    result = await controller.turn_right(duration)

                elif name == "stop_moving":
                    result = await controller.stop()

                elif name == "body_status":
                    status = await controller.get_status()
                    result = f"Device status: {status}"

                elif name == "start_cleaning":
                    result = await controller.start_cleaning()

                elif name == "stop_cleaning":
                    result = await controller.stop_cleaning()

                elif name == "return_to_dock":
                    result = await controller.return_to_dock()

                else:
                    result = f"Unknown tool: {name}"

            except Exception as e:
                logger.error("Tool %s failed: %s", name, e)
                result = f"Error: {e}"

            return [TextContent(type="text", text=result)]

    async def run(self) -> None:
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            try:
                await self._server.run(
                    read_stream,
                    write_stream,
                    self._server.create_initialization_options(),
                )
            finally:
                if self._controller:
                    self._controller.disconnect()


def main():
    """Entry point."""
    try:
        import jurigged
        jurigged.watch(pattern="src/**/*.py", logger=None)
    except ImportError:
        pass
    server = MobilityMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
