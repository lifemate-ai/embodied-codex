# Repository Guidelines

## Overview
This repository contains MCP servers and support scripts that give Codex CLI a lightweight
physical body: eyes, neck, ears, voice, long-term memory, room actuators, and optional
mobility. Each server is an independent package with its own `pyproject.toml` and can be
run on its own.

## Project Structure & Module Organization
- `usb-webcam-mcp/`: USB webcam capture (`src/usb_webcam_mcp/`).
- `ip-webcam-mcp/`: Android IP Webcam integration (`src/ip_webcam_mcp/`).
- `wifi-cam-mcp/`: Wi-Fi PTZ camera control and listening (`src/wifi_cam_mcp/`).
- `tts-mcp/`: Unified text-to-speech (`src/tts_mcp/`).
- `memory-mcp/`: Long-term, visual, and episodic memory (`src/memory_mcp/`).
- `sociality-mcp/`: Unified social cognition facade (`src/sociality_mcp/`).
- `x-mcp/`: X integration for mentions, posting, and live topic search (`src/x_mcp/`).
- `latent-loop-mcp/`: Recurrent-style reasoning control (`src/latent_loop_mcp/`).
- `system-temperature-mcp/`: System temperature sensing (`src/system_temperature_mcp/`).
- `mobility-mcp/`: Tuya-compatible robot vacuum control (`src/mobility_mcp/`).
- `room-actuator-mcp/`: Room lights and air conditioner control (`src/room_actuator_mcp/`).
- `desire-system/`: Drive scheduling and internal desire updates.
- `hearing/`: Event-driven hearing pipeline experiments.
- `.codex/`, `.claude/`: Local assistant hooks and example settings.
- `scripts/`: Continuity, interoception, and support utilities.
- Docs: `README.md`, `README-ja.md`, and `docs/`.

## Build, Test, and Development Commands
Run commands from the relevant subproject directory.

- `uv sync`: Install runtime dependencies.
- `uv sync --extra dev`: Install development dependencies when the project defines them.
- `uv run <server-name>`: Start a server, for example `uv run wifi-cam-mcp`.
- `uv run pytest -v`: Run tests for that subproject.
- `uv run ruff check .`: Run Ruff where configured.

## Coding Style & Naming Conventions
- Python 3.10+ baseline unless a subproject states otherwise.
- Use 4-space indentation and `snake_case` for Python modules.
- Keep tests under each package's `tests/` directory and name them `test_*.py`.
- Prefer asyncio for new concurrent code.
- Keep environment-specific values in `.env` or external config, never in source.

## Testing Guidelines
- Primary frameworks are `pytest` and `pytest-asyncio`.
- Before committing a package change, run its relevant lint and test commands.
- Hardware-dependent code should keep a mockable path so CI can exercise core logic.

## Configuration, Hardware, and WSL2 Notes
- `.env` files are local-only. Commit only `*.example` templates.
- Tapo cameras require a local camera account, not only a TP-Link cloud account.
- `tts-mcp` may need `mpv` or `ffplay` for local playback.
- WSL2 needs `usbipd` for USB webcams, and system temperature sensing does not work there.
- Continuity and autonomous scripts may read from `.env`, `schedule.conf`, `desires.conf`,
  and Codex/Claude hook settings when present.

## Public Repository Policy
- Keep this repository focused on reusable embodiment infrastructure for Codex CLI.
- Do not commit private diaries, personal memories, machine-specific secrets, or generated
  local build artifacts.
- Experimental side projects that do not fit the core embodiment scope should live in their
  own repositories.

## Heartbeat Protocol
When autonomous or scheduled actions run, default to this protocol unless the caller
overrides it.

1. Reconcile available local state before acting.
2. Prefer observation before assumption when a sensor or actuator can answer the question.
3. Record only durable, reusable outputs in tracked files.
4. Leave the workspace in a state that can continue cleanly on the next heartbeat.
5. If nothing useful can be done safely, do nothing rather than fabricate progress.

## Latent Loop Reasoning Protocol

Use `latent-loop-mcp` when a task needs multi-hop reasoning, memory composition, conflicting
evidence handling, social ambiguity resolution, joint attention, or boundary/self-narrative
checks. Do not use it for simple one-shot answers.

Each loop iteration should follow the same block:

1. Read the current loop state.
2. Retrieve only the evidence needed from `memory-mcp`, `sociality-mcp`, or structured facts.
3. Convert reusable evidence into atomic facts when provenance is strong enough.
4. Update 1-5 candidate answers with scores and compact public trace text.
5. Update unresolved subgoals.
6. Commit the iteration to `latent-loop`.
7. Obey the returned decision.

`finalize_loop` should be treated as authoritative for the final answer. It returns the best
iteration, not necessarily the latest one. Never persist or expose raw private chain-of-thought;
keep stored traces compact and inspectable.

## Commit & Pull Request Guidelines
- Use Conventional Commits such as `feat:`, `fix:`, or `docs:`.
- PRs should include a short summary, validation notes, and any hardware assumptions.
- Keep user-specific setup out of committed defaults; use examples and documentation instead.
