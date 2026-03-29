#!/usr/bin/env python3
"""Sync project .mcp.json entries into ~/.codex/config.toml."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

BEGIN_MARKER = "# BEGIN AUTO-GENERATED MCP SERVERS"
END_MARKER = "# END AUTO-GENERATED MCP SERVERS"
TABLE_HEADER_RE = re.compile(r"^\s*\[(.+?)\]\s*$")
BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Sync MCP server definitions from .mcp.json into Codex config.toml.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=repo_root / ".mcp.json",
        help="Path to the source .mcp.json file.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".codex" / "config.toml",
        help="Path to the target Codex config.toml file.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress success output.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Source MCP config not found: {path}")
    return json.loads(path.read_text())


def load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def parse_table_path(raw: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_quote = False
    escape = False
    for ch in raw:
        if in_quote:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_quote = False
            continue
        if ch == '"':
            in_quote = True
            buf.append(ch)
            continue
        if ch == ".":
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())

    result: list[str] = []
    for part in parts:
        if len(part) >= 2 and part[0] == '"' and part[-1] == '"':
            result.append(json.loads(part))
        else:
            result.append(part)
    return result


def strip_existing_managed_blocks(text: str, managed_names: set[str]) -> tuple[list[str], int | None]:
    lines = text.splitlines()
    kept: list[str] = []
    skip = False
    insert_at: int | None = None
    in_auto_block = False

    for line in lines:
        stripped = line.strip()
        if stripped == BEGIN_MARKER:
            in_auto_block = True
            if insert_at is None:
                insert_at = len(kept)
            continue
        if stripped == END_MARKER:
            in_auto_block = False
            skip = False
            continue
        if in_auto_block:
            continue

        match = TABLE_HEADER_RE.match(line)
        if match:
            path = parse_table_path(match.group(1))
            is_managed = len(path) >= 2 and path[0] == "mcp_servers" and path[1] in managed_names
            if is_managed:
                if insert_at is None:
                    insert_at = len(kept)
                skip = True
                continue
            skip = False

        if not skip:
            kept.append(line)

    return kept, insert_at


def merge_server_config(source: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(existing)

    for key in ("command", "args", "env", "url"):
        merged.pop(key, None)

    if "url" in source:
        merged["url"] = source["url"]
    else:
        if "command" in source:
            merged["command"] = source["command"]
        if "args" in source:
            merged["args"] = source["args"]
        if source.get("env"):
            merged["env"] = source["env"]

    codex_meta = source.get("codex", {})
    if isinstance(codex_meta, dict):
        if "tool_timeout_sec" in codex_meta:
            merged["tool_timeout_sec"] = codex_meta["tool_timeout_sec"]
        if "env" in codex_meta:
            merged["env"] = codex_meta["env"]
        source_tools = codex_meta.get("tools")
        if isinstance(source_tools, dict):
            tools = deepcopy(merged.get("tools", {}))
            for tool_name, tool_cfg in source_tools.items():
                if not isinstance(tool_cfg, dict):
                    continue
                current = deepcopy(tools.get(tool_name, {}))
                current.update(tool_cfg)
                tools[tool_name] = current
            if tools:
                merged["tools"] = tools

    return merged


def format_key(key: str) -> str:
    if BARE_KEY_RE.fullmatch(key):
        return key
    return json.dumps(key, ensure_ascii=False)


def format_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(format_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def render_table_header(*parts: str) -> str:
    return "[" + ".".join(format_key(part) for part in parts) + "]"


def render_server(name: str, config: dict[str, Any]) -> list[str]:
    lines = [render_table_header("mcp_servers", name)]

    for key in ("command", "args", "url", "tool_timeout_sec"):
        if key in config:
            lines.append(f"{key} = {format_value(config[key])}")

    env = config.get("env")
    if isinstance(env, dict) and env:
        lines.append("")
        lines.append(render_table_header("mcp_servers", name, "env"))
        for env_key, env_value in env.items():
            lines.append(f"{format_key(env_key)} = {format_value(env_value)}")

    tools = config.get("tools")
    if isinstance(tools, dict):
        for tool_name, tool_cfg in tools.items():
            if not isinstance(tool_cfg, dict) or not tool_cfg:
                continue
            lines.append("")
            lines.append(render_table_header("mcp_servers", name, "tools", tool_name))
            for cfg_key, cfg_value in tool_cfg.items():
                lines.append(f"{cfg_key} = {format_value(cfg_value)}")

    return lines


def render_auto_block(servers: dict[str, dict[str, Any]], order: list[str]) -> list[str]:
    lines = [
        BEGIN_MARKER,
        "# This block is generated from project .mcp.json.",
        "# Edit .mcp.json, then rerun scripts/sync_mcp_to_codex_config.py.",
        "",
    ]
    first = True
    for name in order:
        if not first:
            lines.append("")
        lines.extend(render_server(name, servers[name]))
        first = False
    lines.append(END_MARKER)
    return lines


def merge_text(base_lines: list[str], insert_at: int | None, auto_lines: list[str]) -> str:
    if insert_at is None:
        insert_at = len(base_lines)

    before = base_lines[:insert_at]
    after = base_lines[insert_at:]

    merged: list[str] = []
    merged.extend(before)
    if merged and merged[-1].strip():
        merged.append("")
    merged.extend(auto_lines)
    if after:
        if auto_lines and auto_lines[-1].strip():
            merged.append("")
        merged.extend(after)

    while merged and not merged[-1].strip():
        merged.pop()
    return "\n".join(merged) + "\n"


def main() -> int:
    args = parse_args()

    try:
        source = load_json(args.source)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 0

    source_servers = source.get("mcpServers", {})
    if not isinstance(source_servers, dict):
        raise SystemExit("Invalid .mcp.json: expected top-level 'mcpServers' object")

    existing_data = load_toml(args.target)
    existing_servers = existing_data.get("mcp_servers", {})
    if not isinstance(existing_servers, dict):
        existing_servers = {}

    merged_servers: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for name, server_cfg in source_servers.items():
        if not isinstance(server_cfg, dict):
            continue
        merged_servers[name] = merge_server_config(
            server_cfg,
            existing_servers.get(name, {}) if isinstance(existing_servers.get(name, {}), dict) else {},
        )
        order.append(name)

    target_text = args.target.read_text() if args.target.exists() else ""
    stripped_lines, insert_at = strip_existing_managed_blocks(target_text, set(order))
    auto_lines = render_auto_block(merged_servers, order)
    merged_text = merge_text(stripped_lines, insert_at, auto_lines)

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(merged_text)

    if not args.quiet:
        print(f"Synced {len(order)} MCP servers from {args.source} to {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
