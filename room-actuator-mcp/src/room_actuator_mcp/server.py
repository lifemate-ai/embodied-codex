"""MCP server for room-environment control."""

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

from .backends import (
    HomeAssistantLightingBackend,
    LightingBackend,
    LightingError,
    NatureRemoLightingBackend,
    UnsupportedOperationError,
)
from .config import HomeAssistantConfig, NatureRemoConfig, ServerConfig

logger = logging.getLogger(__name__)

CONTINUITY_ACTION_TOOLS = {
    "light_on",
    "light_off",
    "light_set_brightness",
    "light_press_button",
    "light_send_signal",
    "aircon_on",
    "aircon_off",
    "aircon_set_mode",
    "aircon_set_temp",
}

CONTINUITY_OBSERVATION_TOOLS = {
    "list_lights",
    "light_status",
    "list_light_signals",
    "list_aircons",
    "aircon_status",
    "list_room_sensors",
    "room_sensor_status",
}


class LightingMCPServer:
    """MCP server that gives AI hands for room environment control."""

    def __init__(self) -> None:
        self._server_config = ServerConfig.from_env()
        self._server = Server(self._server_config.name)
        self._backend: LightingBackend | None = None
        self._continuity_record_script = self._resolve_continuity_record_script()
        self._setup_handlers()

    def _ensure_backend(self) -> LightingBackend:
        if self._backend is None:
            if self._server_config.backend == "home_assistant":
                self._backend = HomeAssistantLightingBackend(HomeAssistantConfig.from_env())
            elif self._server_config.backend == "nature_remo":
                self._backend = NatureRemoLightingBackend(NatureRemoConfig.from_env())
            else:
                raise ValueError(f"Unsupported backend: {self._server_config.backend}")
        return self._backend

    def _json_text(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)

    def _resolve_continuity_record_script(self) -> Path:
        override = os.environ.get("CODEX_CONTINUITY_RECORD_SCRIPT")
        if override:
            return Path(override)
        return Path(__file__).resolve().parents[3] / "scripts" / "continuity-record.sh"

    def _format_light_status(self, status: dict[str, Any]) -> str:
        parts = [
            f"id={status.get('id', '?')}",
            f"power={status.get('power', 'unknown')}",
        ]
        brightness = status.get("brightness_pct")
        if brightness is not None:
            parts.append(f"brightness={brightness}")
        last_action = status.get("last_action")
        if last_action:
            parts.append(f"last_action={last_action}")
        return " ".join(parts)

    def _format_aircon_status(self, status: dict[str, Any]) -> str:
        parts = [
            f"id={status.get('id', '?')}",
            f"power={status.get('power', 'unknown')}",
        ]
        mode = status.get("mode")
        if mode:
            parts.append(f"mode={mode}")
        target = status.get("target_temperature")
        if target is not None:
            unit = status.get("temp_unit") or ""
            parts.append(f"target={target}{unit}")
        return " ".join(parts)

    def _format_room_sensor_status(self, status: dict[str, Any]) -> str:
        parts = [f"id={status.get('id', '?')}"]
        if status.get("temperature_c") is not None:
            parts.append(f"temp={status['temperature_c']}C")
        if status.get("humidity_pct") is not None:
            parts.append(f"humidity={status['humidity_pct']}%")
        if status.get("illuminance") is not None:
            parts.append(f"illuminance={status['illuminance']}")
        if status.get("motion") is not None:
            parts.append(f"motion={'on' if status['motion'] else 'off'}")
        return " ".join(parts)

    def _continuity_event_for_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        result: Any,
    ) -> tuple[str, str] | None:
        if isinstance(result, str):
            return None
        if name not in CONTINUITY_ACTION_TOOLS | CONTINUITY_OBSERVATION_TOOLS:
            return None

        if name == "list_lights" and isinstance(result, list):
            return ("record-observation", f"list_lights count={len(result)}")
        if name == "light_status" and isinstance(result, dict):
            return ("record-observation", f"light_status {self._format_light_status(result)}")
        if name == "list_light_signals" and isinstance(result, list):
            light_id = arguments.get("light_id", "?")
            return (
                "record-observation",
                f"list_light_signals light_id={light_id} count={len(result)}",
            )
        if name == "list_aircons" and isinstance(result, list):
            return ("record-observation", f"list_aircons count={len(result)}")
        if name == "aircon_status" and isinstance(result, dict):
            return ("record-observation", f"aircon_status {self._format_aircon_status(result)}")
        if name == "list_room_sensors" and isinstance(result, list):
            return ("record-observation", f"list_room_sensors count={len(result)}")
        if name == "room_sensor_status" and isinstance(result, dict):
            return (
                "record-observation",
                f"room_sensor_status {self._format_room_sensor_status(result)}",
            )

        detail_parts = [name]
        target_id = (
            arguments.get("light_id")
            or arguments.get("aircon_id")
            or arguments.get("signal_id")
            or (result.get("light_id") if isinstance(result, dict) else None)
            or (result.get("aircon_id") if isinstance(result, dict) else None)
            or (result.get("signal_id") if isinstance(result, dict) else None)
        )
        if target_id:
            detail_parts.append(f"id={target_id}")
        if name == "light_set_brightness":
            detail_parts.append(f"brightness={arguments.get('brightness_pct')}")
        if name == "aircon_set_mode":
            detail_parts.append(f"mode={arguments.get('mode')}")
        if name == "aircon_set_temp":
            detail_parts.append(f"target={arguments.get('temperature')}")
        if isinstance(result, dict):
            button = result.get("button")
            if button:
                detail_parts.append(f"button={button}")
            status = result.get("status")
            if isinstance(status, dict):
                if "power" in status:
                    detail_parts.append(f"power={status['power']}")
                if status.get("brightness_pct") is not None:
                    detail_parts.append(f"brightness={status['brightness_pct']}")
                if status.get("mode"):
                    detail_parts.append(f"mode={status['mode']}")
                if status.get("target_temperature") is not None:
                    unit = status.get("temp_unit") or ""
                    detail_parts.append(
                        f"target={status['target_temperature']}{unit}"
                    )
            else:
                if "power" in result:
                    detail_parts.append(f"power={result['power']}")
                if result.get("mode"):
                    detail_parts.append(f"mode={result['mode']}")
                if result.get("target_temperature") is not None:
                    unit = result.get("temp_unit") or ""
                    detail_parts.append(
                        f"target={result['target_temperature']}{unit}"
                    )
        return ("record-action", " ".join(str(part) for part in detail_parts if part))

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
                "room-actuator",
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
            return [
                Tool(
                    name="list_lights",
                    description=(
                        "List available room lights or light-like actuators. "
                        "Use this first to discover controllable IDs and capabilities."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="light_status",
                    description="Get the current status of a light.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "light_id": {
                                "type": "string",
                                "description": "The light ID / entity ID returned by list_lights.",
                            }
                        },
                        "required": ["light_id"],
                    },
                ),
                Tool(
                    name="light_on",
                    description=(
                        "Turn a light on. Home Assistant backend also accepts brightness_pct. "
                        "Nature Remo may need a learned ON button."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "light_id": {
                                "type": "string",
                                "description": "The light ID / entity ID returned by list_lights.",
                            },
                            "brightness_pct": {
                                "type": "integer",
                                "description": (
                                    "Brightness percentage (0-100). "
                                    "Only supported on backends with real dimming APIs."
                                ),
                                "minimum": 0,
                                "maximum": 100,
                            },
                        },
                        "required": ["light_id"],
                    },
                ),
                Tool(
                    name="light_off",
                    description="Turn a light off.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "light_id": {
                                "type": "string",
                                "description": "The light ID / entity ID returned by list_lights.",
                            }
                        },
                        "required": ["light_id"],
                    },
                ),
                Tool(
                    name="light_set_brightness",
                    description=(
                        "Set a light brightness percentage. "
                        "Use only on backends that expose real brightness control."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "light_id": {
                                "type": "string",
                                "description": "The light ID / entity ID returned by list_lights.",
                            },
                            "brightness_pct": {
                                "type": "integer",
                                "description": "Brightness percentage (0-100).",
                                "minimum": 0,
                                "maximum": 100,
                            },
                        },
                        "required": ["light_id", "brightness_pct"],
                    },
                ),
                Tool(
                    name="light_press_button",
                    description=(
                        "Press a backend-specific light button. "
                        "Especially useful for Nature Remo IR light appliances."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "light_id": {
                                "type": "string",
                                "description": "The light ID returned by list_lights.",
                            },
                            "button": {
                                "type": "string",
                                "description": "Button name as reported by list_lights.",
                            },
                        },
                        "required": ["light_id", "button"],
                    },
                ),
                Tool(
                    name="list_light_signals",
                    description=(
                        "List learned signals associated with a Nature Remo light appliance. "
                        "Unsupported on some backends."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "light_id": {
                                "type": "string",
                                "description": "The light ID returned by list_lights.",
                            }
                        },
                        "required": ["light_id"],
                    },
                ),
                Tool(
                    name="light_send_signal",
                    description=(
                        "Send a learned Nature Remo signal directly by signal ID. "
                        "Unsupported on some backends."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "signal_id": {
                                "type": "string",
                                "description": "Signal ID returned by list_light_signals.",
                            }
                        },
                        "required": ["signal_id"],
                    },
                ),
                Tool(
                    name="list_room_sensors",
                    description=(
                        "List available room sensors such as temperature, humidity, "
                        "illuminance, or motion. Unsupported on some backends."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="room_sensor_status",
                    description=(
                        "Get the current status of a room sensor. Unsupported on some backends."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "sensor_id": {
                                "type": "string",
                                "description": (
                                    "The room sensor ID returned by list_room_sensors."
                                ),
                            }
                        },
                        "required": ["sensor_id"],
                    },
                ),
                Tool(
                    name="list_aircons",
                    description=(
                        "List available air conditioners or climate actuators. "
                        "Use this first to discover controllable IDs and capabilities."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                ),
                Tool(
                    name="aircon_status",
                    description="Get the current status of an air conditioner.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "aircon_id": {
                                "type": "string",
                                "description": (
                                    "The air conditioner ID / entity ID "
                                    "returned by list_aircons."
                                ),
                            }
                        },
                        "required": ["aircon_id"],
                    },
                ),
                Tool(
                    name="aircon_on",
                    description="Power an air conditioner on using its current settings.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "aircon_id": {
                                "type": "string",
                                "description": (
                                    "The air conditioner ID / entity ID "
                                    "returned by list_aircons."
                                ),
                            }
                        },
                        "required": ["aircon_id"],
                    },
                ),
                Tool(
                    name="aircon_off",
                    description="Power an air conditioner off.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "aircon_id": {
                                "type": "string",
                                "description": (
                                    "The air conditioner ID / entity ID "
                                    "returned by list_aircons."
                                ),
                            }
                        },
                        "required": ["aircon_id"],
                    },
                ),
                Tool(
                    name="aircon_set_mode",
                    description=(
                        "Set an air conditioner mode such as cool, warm, "
                        "dry, auto, or blow."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "aircon_id": {
                                "type": "string",
                                "description": (
                                    "The air conditioner ID / entity ID "
                                    "returned by list_aircons."
                                ),
                            },
                            "mode": {
                                "type": "string",
                                "description": (
                                    "Mode name as reported by list_aircons "
                                    "or the backend."
                                ),
                            },
                        },
                        "required": ["aircon_id", "mode"],
                    },
                ),
                Tool(
                    name="aircon_set_temp",
                    description="Set the target temperature of an air conditioner.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "aircon_id": {
                                "type": "string",
                                "description": (
                                    "The air conditioner ID / entity ID "
                                    "returned by list_aircons."
                                ),
                            },
                            "temperature": {
                                "type": "number",
                                "description": (
                                    "Target temperature. Use values "
                                    "supported by the backend."
                                ),
                            },
                        },
                        "required": ["aircon_id", "temperature"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            backend = self._ensure_backend()

            try:
                if name == "list_lights":
                    result = await asyncio.to_thread(backend.list_lights)
                elif name == "light_status":
                    result = await asyncio.to_thread(backend.get_status, arguments["light_id"])
                elif name == "light_on":
                    result = await asyncio.to_thread(
                        backend.turn_on,
                        arguments["light_id"],
                        arguments.get("brightness_pct"),
                    )
                elif name == "light_off":
                    result = await asyncio.to_thread(backend.turn_off, arguments["light_id"])
                elif name == "light_set_brightness":
                    result = await asyncio.to_thread(
                        backend.set_brightness,
                        arguments["light_id"],
                        arguments["brightness_pct"],
                    )
                elif name == "light_press_button":
                    result = await asyncio.to_thread(
                        backend.press_button,
                        arguments["light_id"],
                        arguments["button"],
                    )
                elif name == "list_light_signals":
                    result = await asyncio.to_thread(
                        backend.list_signals,
                        arguments["light_id"],
                    )
                elif name == "light_send_signal":
                    result = await asyncio.to_thread(
                        backend.send_signal,
                        arguments["signal_id"],
                    )
                elif name == "list_aircons":
                    result = await asyncio.to_thread(backend.list_aircons)
                elif name == "list_room_sensors":
                    result = await asyncio.to_thread(backend.list_room_sensors)
                elif name == "room_sensor_status":
                    result = await asyncio.to_thread(
                        backend.get_room_sensor_status,
                        arguments["sensor_id"],
                    )
                elif name == "aircon_status":
                    result = await asyncio.to_thread(
                        backend.get_aircon_status,
                        arguments["aircon_id"],
                    )
                elif name == "aircon_on":
                    result = await asyncio.to_thread(
                        backend.turn_aircon_on,
                        arguments["aircon_id"],
                    )
                elif name == "aircon_off":
                    result = await asyncio.to_thread(
                        backend.turn_aircon_off,
                        arguments["aircon_id"],
                    )
                elif name == "aircon_set_mode":
                    result = await asyncio.to_thread(
                        backend.set_aircon_mode,
                        arguments["aircon_id"],
                        arguments["mode"],
                    )
                elif name == "aircon_set_temp":
                    result = await asyncio.to_thread(
                        backend.set_aircon_temperature,
                        arguments["aircon_id"],
                        arguments["temperature"],
                    )
                else:
                    result = f"Unknown tool: {name}"
            except UnsupportedOperationError as e:
                result = f"Error: {e}"
            except LightingError as e:
                logger.error("Lighting tool %s failed: %s", name, e)
                result = f"Error: {e}"
            except Exception as e:
                logger.exception("Unexpected lighting tool failure")
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
    asyncio.run(LightingMCPServer().run())


if __name__ == "__main__":
    main()
