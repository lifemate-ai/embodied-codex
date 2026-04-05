"""PETServer — Unified MCP server that gives AI its senses."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import ImageContent, TextContent, Tool

from .config import PETConfig
from .senses import discover_senses
from .senses.base import Sense

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PETServer:
    """PErsonal Terminal — the unified MCP that provides AI with senses."""

    def __init__(self, config: PETConfig | None = None) -> None:
        self._config = config or PETConfig.from_env()
        self._server = Server(self._config.name)
        self._senses: list[Sense] = []
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            tools: list[Tool] = []
            for sense in self._senses:
                tools.extend(sense.get_tools())

            # Meta tool: pet_status
            tools.append(
                Tool(
                    name="pet_status",
                    description="Show PET status — which senses are available and their state.",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                )
            )
            return tools

        @self._server.call_tool()
        async def call_tool(
            name: str, arguments: dict[str, Any]
        ) -> list[TextContent | ImageContent]:
            # Meta tool
            if name == "pet_status":
                return self._handle_status()

            # Dispatch to senses
            for sense in self._senses:
                result = await sense.call_tool(name, arguments)
                if result is not None:
                    return result

            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    def _handle_status(self) -> list[TextContent | ImageContent]:
        lines = [f"PET ({self._config.name} v{self._config.version})"]
        lines.append("")

        if not self._senses:
            lines.append("No senses configured.")
        else:
            for sense in self._senses:
                status = sense.get_status()
                state = "available" if status.available else "unavailable"
                lines.append(f"[{sense.name}] {state}")
                for key, value in status.details.items():
                    lines.append(f"  {key}: {value}")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _initialize_senses(self) -> None:
        self._senses = discover_senses(self._config)
        results = await asyncio.gather(
            *(s.initialize() for s in self._senses),
            return_exceptions=True,
        )
        for sense, result in zip(self._senses, results):
            if isinstance(result, Exception):
                logger.error("Failed to initialize %s: %s", sense.name, result)

    async def _shutdown_senses(self) -> None:
        await asyncio.gather(
            *(s.shutdown() for s in self._senses),
            return_exceptions=True,
        )

    async def run(self) -> None:
        """Run the PET MCP server."""
        try:
            await self._initialize_senses()
            logger.info("PET started with %d sense(s)", len(self._senses))

            if self._config.server.enabled:
                # Run MCP stdio + web server concurrently
                await asyncio.gather(
                    self._run_stdio(),
                    self._run_web_server(),
                )
            else:
                await self._run_stdio()
        finally:
            await self._shutdown_senses()

    async def _run_stdio(self) -> None:
        """Run the MCP stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )

    async def _run_web_server(self) -> None:
        """Run the built-in web server for frame relay."""
        from .web import run_web_server

        logger.info(
            "Built-in web server starting on %s:%d",
            self._config.server.host,
            self._config.server.port,
        )
        await run_web_server(self._config.server, self._config.capture_dir)


def main() -> None:
    """Entry point."""
    server = PETServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
