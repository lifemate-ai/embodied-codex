# recursive-context-mcp

`recursive-context-mcp` gives Codex or Claude Code an RLM-style workspace for large
contexts. It does not stuff a full repository, log archive, observation dataset, or memory dump
into the prompt. Instead, it registers local files and directories as an external context that the
agent can inspect, search, slice, and package into bounded sub-queries.

This is inspired by RLM-style recursive language-model scaffolding: keep the large input in an
environment, use code-like inspection to find the relevant parts, and only send small packets to
the model or sub-agent that needs them.

## Tools

- `start_session`: Register local context roots.
- `inspect_context`: Inspect source/file/byte statistics.
- `list_context_files`: List files under the registered roots.
- `search_context`: Search text files.
- `read_context_slice`: Read bounded line slices.
- `commit_buffer`: Persist intermediate notes or manifests.
- `prepare_sub_query`: Build a bounded packet for a sub-agent/model.
- `record_sub_result`: Persist a returned sub-query answer.
- `run_program`: Optionally run a small inspection program. Disabled by default.
- `finalize_session`: Persist the final summary.
- `get_session_trace`: Inspect compact diagnostics without private chain-of-thought.

## Setup

```bash
cd recursive-context-mcp
uv sync
uv run recursive-context-mcp
```

Codex TOML example:

```toml
[mcp_servers.recursive-context]
command = "uv"
args = ["--directory", "/path/to/embodied-codex/recursive-context-mcp", "run", "recursive-context-mcp"]
```

## Optional Program Execution

`run_program` is disabled by default because arbitrary code execution is not a safe default for an
MCP server. Enable it only in a trusted local environment:

```bash
RECURSIVE_CONTEXT_ENABLE_PROGRAMS=true uv run recursive-context-mcp
```

The program API exposes `ctx.stats()`, `ctx.list_files()`, `ctx.search()`, and `ctx.read()`. It is
intended for lightweight local inspection, not as a security sandbox.

## Example

```text
1. start_session(context_uris=["./observations"])
2. inspect_context()
3. search_context(query="rain")
4. read_context_slice(source_id=..., relative_path="2026/04/26/meta.jsonl")
5. prepare_sub_query(prompt="Summarize weather changes from these slices.")
6. record_sub_result(content="...")
7. finalize_session(summary="...")
```

For embodied observation datasets, this lets a cheap daily Codex agent inspect one year of
fixed-view camera metadata without loading the entire dataset into a single prompt.
