# latent-loop-mcp

`latent-loop-mcp` gives Codex a recurrent-style reasoning workspace.

It does not modify model weights. Instead, it externalizes loop state so Codex can repeatedly
apply the same reasoning block to memory, social state, and structured facts until adaptive
halting says to stop.

## What It Does

- persists loop traces and per-iteration state
- normalizes candidate answer distributions
- computes halting metrics such as KL-like delta, entropy, margin, and novelty
- detects overthinking and returns `HALT_AT_BEST`
- stores reusable atomic fact edges with provenance
- composes deterministic multi-hop fact paths

## Setup

```bash
cd latent-loop-mcp
uv sync --extra dev
```

Behavior defaults are read from the repo root `mcpBehavior.toml` under `[latent_loop]`.
Environment variables override those values.

## Run

```bash
uv run latent-loop-mcp
```

## Tools

- `start_loop`
- `commit_iteration`
- `finalize_loop`
- `get_loop_trace`
- `upsert_fact`
- `search_facts`
- `compose_path`
- `suggest_next_loop_action`
- `get_loop_stats`

## Example

User: `Who is the spouse of the performer of Imagine?`

1. `start_loop`
2. recall or add facts:
   - `Imagine --performer--> John Lennon`
   - `John Lennon --spouse--> Yoko Ono`
3. `compose_path(start="Imagine", relations=["performer", "spouse"])`
4. `commit_iteration`
5. `finalize_loop`

Answer: `Yoko Ono`

## Tests

```bash
uv run pytest -v
uv run ruff check .
```
