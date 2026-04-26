"""MCP server for recursive-context-mcp."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import RecursiveContextConfig
from .service import RecursiveContextService
from .store import RecursiveContextStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _tool_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


class RecursiveContextMCPServer:
    """Expose RLM-style context inspection tools over MCP."""

    def __init__(self) -> None:
        self._server = Server("recursive-context-mcp")
        self._config = RecursiveContextConfig.from_env()
        self._store: RecursiveContextStore | None = None
        self._service: RecursiveContextService | None = None
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="start_session",
                    description="Register local files/directories as an external recursive context.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "context_uris": {"type": "array", "items": {"type": "string"}},
                            "name": {"type": "string", "default": ""},
                            "description": {"type": "string", "default": ""},
                            "metadata": {"type": "object", "default": {}},
                        },
                        "required": ["context_uris"],
                    },
                ),
                Tool(
                    name="inspect_context",
                    description="Return source, file, and byte statistics for a context session.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "max_files": {"type": "integer", "minimum": 0, "maximum": 500, "default": 30},
                        },
                        "required": ["session_id"],
                    },
                ),
                Tool(
                    name="list_context_files",
                    description="List files available inside the registered context.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "glob": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
                        },
                        "required": ["session_id"],
                    },
                ),
                Tool(
                    name="search_context",
                    description="Search text files in the registered context.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "query": {"type": "string"},
                            "regex": {"type": "boolean", "default": False},
                            "glob": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
                        },
                        "required": ["session_id", "query"],
                    },
                ),
                Tool(
                    name="read_context_slice",
                    description="Read a bounded text slice from a registered source.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "source_id": {"type": "string"},
                            "relative_path": {"type": "string"},
                            "start_line": {"type": "integer", "minimum": 1, "default": 1},
                            "max_lines": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 80},
                        },
                        "required": ["session_id", "source_id"],
                    },
                ),
                Tool(
                    name="commit_buffer",
                    description="Persist a derived note, manifest, or intermediate artifact.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                            "kind": {
                                "type": "string",
                                "enum": ["note", "manifest", "sub_query", "sub_result", "program_result", "final"],
                                "default": "note",
                            },
                            "metadata": {"type": "object", "default": {}},
                        },
                        "required": ["session_id", "name", "content"],
                    },
                ),
                Tool(
                    name="get_buffer",
                    description="Retrieve a persisted buffer by id or latest name.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "buffer_id": {"type": "string"},
                            "name": {"type": "string"},
                        },
                        "required": ["session_id"],
                    },
                ),
                Tool(
                    name="list_buffers",
                    description="List persisted buffers for a context session.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "kind": {"type": "string"},
                        },
                        "required": ["session_id"],
                    },
                ),
                Tool(
                    name="prepare_sub_query",
                    description="Build a bounded packet for a sub-agent/model without calling it directly.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "prompt": {"type": "string"},
                            "slice_refs": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "source_id": {"type": "string"},
                                        "relative_path": {"type": "string"},
                                        "start_line": {"type": "integer", "minimum": 1, "default": 1},
                                        "max_lines": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 80},
                                    },
                                    "required": ["source_id"],
                                },
                                "default": [],
                            },
                            "buffer_names": {"type": "array", "items": {"type": "string"}, "default": []},
                            "name": {"type": "string", "default": "sub-query"},
                        },
                        "required": ["session_id", "prompt"],
                    },
                ),
                Tool(
                    name="record_sub_result",
                    description="Persist the answer returned by a sub-agent/model.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "sub_query_buffer_id": {"type": "string"},
                            "content": {"type": "string"},
                            "name": {"type": "string", "default": "sub-result"},
                            "metadata": {"type": "object", "default": {}},
                        },
                        "required": ["session_id", "sub_query_buffer_id", "content"],
                    },
                ),
                Tool(
                    name="run_program",
                    description="Optionally run a small context inspection program. Disabled by default.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "code": {"type": "string"},
                        },
                        "required": ["session_id", "code"],
                    },
                ),
                Tool(
                    name="finalize_session",
                    description="Persist a final summary for a recursive context session.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "summary": {"type": "string"},
                            "buffer_names": {"type": "array", "items": {"type": "string"}, "default": []},
                        },
                        "required": ["session_id", "summary"],
                    },
                ),
                Tool(
                    name="get_session_trace",
                    description="Inspect compact session diagnostics without private chain-of-thought.",
                    inputSchema={
                        "type": "object",
                        "properties": {"session_id": {"type": "string"}},
                        "required": ["session_id"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if self._service is None:
                return _tool_text({"error": "service not initialized"})

            try:
                match name:
                    case "start_session":
                        return _tool_text(self._service.start_session(**arguments))
                    case "inspect_context":
                        return _tool_text(self._service.inspect_context(**arguments))
                    case "list_context_files":
                        return _tool_text(self._service.list_context_files(**arguments))
                    case "search_context":
                        return _tool_text(self._service.search_context(**arguments))
                    case "read_context_slice":
                        return _tool_text(self._service.read_context_slice(**arguments))
                    case "commit_buffer":
                        return _tool_text(self._service.commit_buffer(**arguments))
                    case "get_buffer":
                        return _tool_text(self._service.get_buffer(**arguments))
                    case "list_buffers":
                        return _tool_text(self._service.list_buffers(**arguments))
                    case "prepare_sub_query":
                        return _tool_text(self._service.prepare_sub_query(**arguments))
                    case "record_sub_result":
                        return _tool_text(self._service.record_sub_result(**arguments))
                    case "run_program":
                        return _tool_text(self._service.run_program(**arguments))
                    case "finalize_session":
                        return _tool_text(self._service.finalize_session(**arguments))
                    case "get_session_trace":
                        return _tool_text(self._service.get_session_trace(**arguments))
                    case _:
                        return _tool_text({"error": f"Unknown tool: {name}"})
            except Exception as exc:
                logger.exception("Tool failed: %s", name)
                return _tool_text({"error": str(exc)})

    async def run(self) -> None:
        store = RecursiveContextStore(self._config.resolved_db_path)
        self._store = store
        self._service = RecursiveContextService(store, self._config)
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self._server.run(read_stream, write_stream, self._server.create_initialization_options())
        finally:
            store.close()


def main() -> None:
    asyncio.run(RecursiveContextMCPServer().run())
