# toio-mcp

MCP server that lets Codex use a `toio` cube as a small rolling hand.

It is intentionally minimal:

- connect to one cube
- feel the current pose / marker / battery
- roll forward or backward in short discrete steps
- turn left or right in small or large increments
- stop and disconnect cleanly

The first goal is not autonomy. It is to make the cube available as a reliable tool.

## Tools

- `connect_cube`
- `read_state`
- `move_forward_short`
- `move_forward_long`
- `move_backward_short`
- `turn_left_small`
- `turn_right_small`
- `turn_left_large`
- `turn_right_large`
- `stop`
- `disconnect_cube`

All motion tools auto-connect if the cube is not connected yet.

## Environment

- `TOIO_CUBE_NAME`: optional cube name filter
- `TOIO_SCAN_TIMEOUT`: scan timeout in seconds (default `5`)
- `TOIO_SPEED`: default movement speed (default `80`)
- `CODEX_CONTINUITY_RECORD_SCRIPT`: optional override for continuity recorder

## Setup

```bash
cd toio-mcp
uv sync --extra dev
```

Run locally:

```bash
uv run toio-mcp
```

Register with Codex CLI:

```bash
codex mcp add toio --env TOIO_SCAN_TIMEOUT=10 -- \
  uv --directory "$(pwd)/toio-mcp" run toio-mcp
```

## Windows note

`toio-py 1.1.0` still expects Bleak's old private WinRT name `_RawAdvData`.
This server applies a small compatibility shim so it also works with newer `bleak`
releases that expose the same object as `RawAdvData`.

`cmd.exe` can also truncate the trailing `run ...` part of `codex mcp add`.
If Codex shows `Tools: (none)`, use the checked-in launcher instead:

```bat
cd C:\Users\Mizushima\repo\embodied-codex\toio-mcp
uv sync --extra dev
run-toio-mcp.cmd
codex mcp remove toio
codex mcp add toio --env TOIO_SCAN_TIMEOUT=10 --env TOIO_SPEED=60 -- C:\Users\Mizushima\repo\embodied-codex\toio-mcp\run-toio-mcp.cmd
codex mcp get toio
```

The final `codex mcp get toio` output should show:

```text
command: C:\Users\Mizushima\repo\embodied-codex\toio-mcp\run-toio-mcp.cmd
```

## Tests

```bash
uv run pytest
uv run ruff check .
```
