"""MCP server for latent-loop-mcp."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import LatentLoopConfig, ServerConfig
from .service import LatentLoopService
from .store import LatentLoopStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _tool_text(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


class LatentLoopMCPServer:
    """MCP server that exposes latent-loop tools."""

    def __init__(self) -> None:
        self._server = Server("latent-loop-mcp")
        self._server_config = ServerConfig.from_env()
        self._config = LatentLoopConfig.from_env()
        self._store: LatentLoopStore | None = None
        self._service: LatentLoopService | None = None
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        @self._server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="start_loop",
                    description="Start a recurrent-style reasoning loop.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "mode": {"type": "string", "enum": ["fixed", "dynamic", "adaptive"], "default": "adaptive"},
                            "min_iterations": {"type": "integer", "minimum": 1, "maximum": 20, "default": 2},
                            "max_iterations": {"type": "integer", "minimum": 1, "maximum": 50, "default": 8},
                            "complexity_hint": {
                                "type": "string",
                                "enum": ["unknown", "low", "medium", "high", "very_high"],
                                "default": "unknown",
                            },
                            "initial_subgoals": {
                                "type": "array",
                                "items": {"type": "string"},
                                "default": [],
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="commit_iteration",
                    description="Commit one loop iteration and receive a halting decision.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "loop_id": {"type": "string"},
                            "compact_trace": {"type": "string", "default": ""},
                            "candidates": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "answer": {"type": "string"},
                                        "score": {"type": "number", "minimum": 0},
                                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                        "evidence_ids": {"type": "array", "items": {"type": "string"}, "default": []},
                                        "fact_ids": {"type": "array", "items": {"type": "string"}, "default": []},
                                        "summary": {"type": "string", "default": ""},
                                        "status": {
                                            "type": "string",
                                            "enum": ["active", "rejected", "verified", "tentative"],
                                            "default": "active",
                                        },
                                    },
                                    "required": ["answer", "score"],
                                },
                            },
                            "facts_used": {"type": "array", "items": {"type": "string"}, "default": []},
                            "facts_added": {"type": "array", "items": {"type": "string"}, "default": []},
                            "open_subgoals": {
                                "type": "array",
                                "default": [],
                                "items": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "description": {"type": "string"},
                                                "kind": {
                                                    "type": "string",
                                                    "enum": [
                                                        "retrieve_fact",
                                                        "compose_path",
                                                        "verify_candidate",
                                                        "resolve_reference",
                                                        "ask_user",
                                                        "retrieve_social_state",
                                                        "check_boundary",
                                                        "self_consistency",
                                                    ],
                                                    "default": "retrieve_fact",
                                                },
                                                "priority": {
                                                    "type": "integer",
                                                    "minimum": 1,
                                                    "maximum": 5,
                                                    "default": 3,
                                                },
                                                "status": {
                                                    "type": "string",
                                                    "enum": ["open", "done", "blocked", "deferred"],
                                                    "default": "open",
                                                },
                                                "related_fact_ids": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                    "default": [],
                                                },
                                            },
                                            "required": ["description"],
                                        },
                                    ]
                                },
                            },
                            "closed_subgoals": {"type": "array", "items": {"type": "string"}, "default": []},
                            "contradictions": {"type": "array", "items": {"type": "string"}, "default": []},
                        },
                        "required": ["loop_id", "candidates"],
                    },
                ),
                Tool(
                    name="finalize_loop",
                    description="Return the best candidate and compact trace for a loop.",
                    inputSchema={
                        "type": "object",
                        "properties": {"loop_id": {"type": "string"}},
                        "required": ["loop_id"],
                    },
                ),
                Tool(
                    name="get_loop_trace",
                    description="Inspect an existing loop trace without exposing private chain-of-thought.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "loop_id": {"type": "string"},
                            "include_iterations": {"type": "boolean", "default": True},
                        },
                        "required": ["loop_id"],
                    },
                ),
                Tool(
                    name="upsert_fact",
                    description="Insert or update an atomic fact edge with provenance.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "relation": {"type": "string"},
                            "object": {"type": "string"},
                            "source": {"type": "string"},
                            "source_type": {
                                "type": "string",
                                "enum": ["memory", "observation", "user", "inferred", "manual", "test", "sociality"],
                            },
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 1.0},
                            "metadata": {"type": "object", "default": {}},
                        },
                        "required": ["subject", "relation", "object", "source", "source_type"],
                    },
                ),
                Tool(
                    name="search_facts",
                    description="Search structured fact edges.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "relation": {"type": "string"},
                            "object": {"type": "string"},
                            "query": {"type": "string"},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                        },
                    },
                ),
                Tool(
                    name="compose_path",
                    description="Deterministically compose a multi-hop path through atomic facts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "start": {"type": "string"},
                            "relations": {"type": "array", "items": {"type": "string"}},
                            "max_paths": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                            "min_confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                        },
                        "required": ["start", "relations"],
                    },
                ),
                Tool(
                    name="suggest_next_loop_action",
                    description="Suggest the next retrieval or verification step for a loop.",
                    inputSchema={
                        "type": "object",
                        "properties": {"loop_id": {"type": "string"}},
                        "required": ["loop_id"],
                    },
                ),
                Tool(
                    name="get_loop_stats",
                    description="Return aggregate latent-loop statistics.",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if self._service is None:
                return _tool_text({"error": "latent-loop service is not initialized"})

            try:
                match name:
                    case "start_loop":
                        return _tool_text(self._service.start_loop(**arguments))
                    case "commit_iteration":
                        return _tool_text(self._service.commit_iteration(**arguments))
                    case "finalize_loop":
                        return _tool_text(self._service.finalize_loop(**arguments))
                    case "get_loop_trace":
                        return _tool_text(self._service.get_loop_trace(**arguments))
                    case "upsert_fact":
                        return _tool_text(self._service.upsert_fact(**arguments))
                    case "search_facts":
                        return _tool_text(self._service.search_facts(**arguments))
                    case "compose_path":
                        return _tool_text(self._service.compose_path(**arguments))
                    case "suggest_next_loop_action":
                        return _tool_text(self._service.suggest_next_loop_action(**arguments))
                    case "get_loop_stats":
                        return _tool_text(self._service.get_loop_stats())
                    case _:
                        return _tool_text({"error": f"Unknown tool: {name}"})
            except Exception as exc:  # pragma: no cover - surfaced via tests at service level
                logger.exception("Tool failed: %s", name)
                return _tool_text({"error": str(exc)})

    async def run(self) -> None:
        self._store = LatentLoopStore(self._config.db_path)
        self._service = LatentLoopService(self._config, self._store)
        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )


def main() -> None:
    asyncio.run(LatentLoopMCPServer().run())
