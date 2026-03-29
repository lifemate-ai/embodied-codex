"""MCP server for using a toio cube as a small embodied hand."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .controller import ToioCubeController

logger = logging.getLogger(__name__)

OBSERVATION_TOOLS = {
    "connect_cube",
    "read_state",
    "disconnect_cube",
}

ACTION_TOOLS = {
    "move_forward_short",
    "move_forward_long",
    "move_backward_short",
    "turn_left_small",
    "turn_right_small",
    "turn_left_large",
    "turn_right_large",
    "stop",
}


class ToioMCPServer:
    """MCP server that gives AI a small rolling hand."""

    def __init__(self) -> None:
        self._server = Server("toio-mcp")
        self._controller: ToioCubeController | None = None
        self._continuity_record_script = self._resolve_continuity_record_script()
        self._setup_handlers()

    def _resolve_continuity_record_script(self) -> Path:
        override = os.environ.get("CODEX_CONTINUITY_RECORD_SCRIPT")
        if override:
            return Path(override)
        return Path(__file__).resolve().parents[3] / "scripts" / "continuity-record.sh"

    def _json_text(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)

    def _get_controller(self) -> ToioCubeController:
        if self._controller is None:
            self._controller = ToioCubeController()
        return self._controller

    def _ensure_connected_controller(self) -> ToioCubeController:
        controller = self._get_controller()
        if not controller.is_connected():
            controller.connect()
        return controller

    def _tool_definitions(self) -> list[Tool]:
        return [
            Tool(
                name="connect_cube",
                description=(
                    "Wake and reach for your toio cube hand. "
                    "Returns the current pose, marker, and battery state."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="read_state",
                description=(
                    "Feel where your toio cube hand is right now. "
                    "Returns pose, marker, and battery."
                ),
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="move_forward_short",
                description="Roll your toio hand a short step forward.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="move_forward_long",
                description="Roll your toio hand a longer step forward.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="move_backward_short",
                description="Roll your toio hand a short step backward.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="turn_left_small",
                description="Rotate your toio hand a little to the left.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="turn_right_small",
                description="Rotate your toio hand a little to the right.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="turn_left_large",
                description="Rotate your toio hand strongly to the left.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="turn_right_large",
                description="Rotate your toio hand strongly to the right.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="stop",
                description="Stop your toio hand immediately.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="disconnect_cube",
                description="Let go of your toio hand and disconnect cleanly.",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
        ]

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        del arguments
        if name == "connect_cube":
            return self._get_controller().connect()
        if name == "read_state":
            return self._ensure_connected_controller().read_state()
        if name == "disconnect_cube":
            return self._get_controller().disconnect()
        if name in ACTION_TOOLS:
            return self._ensure_connected_controller().perform_action(name)
        return f"Unknown tool: {name}"

    def _continuity_event_for_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> tuple[str, str] | None:
        del arguments
        if isinstance(result, str):
            return None

        if name in OBSERVATION_TOOLS:
            if name == "disconnect_cube":
                return ("record-observation", "disconnect_cube connected=no")
            pose = result.get("pose", {})
            battery = result.get("battery", {})
            marker = result.get("marker", {})
            detail = (
                f"{name} x={pose.get('x')} y={pose.get('y')} theta={pose.get('theta_deg')} "
                f"marker={marker.get('marker_id')} battery={battery.get('percent')}"
            )
            return ("record-observation", detail)

        if name in ACTION_TOOLS:
            state = result.get("state", {})
            pose = state.get("pose", {})
            marker = state.get("marker", {})
            detail = (
                f"{name} x={pose.get('x')} y={pose.get('y')} theta={pose.get('theta_deg')} "
                f"marker={marker.get('marker_id')}"
            )
            return ("record-action", detail)

        return None

    async def _record_continuity_event(self, command: str, detail: str) -> None:
        script = self._continuity_record_script
        if not script.exists():
            return

        normalized = " ".join(detail.split())
        if len(normalized) > 240:
            normalized = f"{normalized[:237]}..."

        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                str(script),
                command,
                "toio-mcp",
                normalized,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=3)
            if process.returncode != 0:
                logger.warning(
                    "Continuity recorder failed for %s: %s",
                    command,
                    (stderr or b"").decode().strip(),
                )
        except FileNotFoundError:
            logger.warning("Continuity recorder script is not executable: %s", script)
        except asyncio.TimeoutError:
            if process is not None:
                process.kill()
                await process.wait()
            logger.warning("Continuity recorder timed out for %s", command)
        except Exception:
            logger.exception("Failed to record continuity event")

    def _setup_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return self._tool_definitions()

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            try:
                result = await asyncio.to_thread(self._execute_tool, name, arguments)
            except Exception as e:
                logger.exception("Unexpected toio tool failure")
                result = f"Error: {e}"

            event = self._continuity_event_for_tool(name, arguments, result)
            if event is not None:
                await self._record_continuity_event(*event)

            text = result if isinstance(result, str) else self._json_text(result)
            return [TextContent(type="text", text=text)]

    async def run(self) -> None:
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ToioMCPServer().run())


if __name__ == "__main__":
    main()
