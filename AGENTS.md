# Repository Guidelines

## Overview
This repository contains multiple Python MCP servers that give Codex CLI “senses” (eyes, neck, ears, memory, and voice). Each server is a standalone package with its own `pyproject.toml` and can be run independently.

## Project Structure & Module Organization
- `usb-webcam-mcp/`: USB webcam capture (`src/usb_webcam_mcp/`).
- `wifi-cam-mcp/`: Wi‑Fi PTZ camera control + audio capture (`src/wifi_cam_mcp/`).
- `elevenlabs-t2s-mcp/`: ElevenLabs text-to-speech (`src/elevenlabs_t2s_mcp/`).
- `memory-mcp/`: Long‑term memory server (`src/memory_mcp/`) with tests in `memory-mcp/tests/`.
- `system-temperature-mcp/`: System temperature sensor (`src/system_temperature_mcp/`).
- `installer/`: PyInstaller-based GUI installer.
- `.codex/`: Codex CLI local settings when used in a workspace-local setup.
- Docs: `README.md`, `README-ja.md`.

## Build, Test, and Development Commands
Run commands from the target subproject directory.

- `uv sync`: Install dependencies.
- `uv run <server-name>`: Start a server (e.g., `uv run wifi-cam-mcp`).
- `uv run pytest`: Run tests (currently only in `memory-mcp/`).
- `uv run ruff check .`: Lint where configured (`memory-mcp/`, `wifi-cam-mcp/`).

## Coding Style & Naming Conventions
- Python 3.10+ baseline; `system-temperature-mcp/` requires Python 3.12+.
- 4‑space indentation, `snake_case` modules, `test_*.py` tests.
- Ruff line length is 100; asyncio is the default style for async work.

## Testing Guidelines
- Frameworks: `pytest` + `pytest-asyncio`.
- Tests live in `memory-mcp/tests/`.
- Example: `cd memory-mcp && uv run pytest`.

## Configuration, Hardware, and WSL2 Notes
- `.env` is not committed; pass camera credentials via environment variables.
- ElevenLabs requires `ELEVENLABS_API_KEY` in the environment (see `elevenlabs-t2s-mcp/.env.example`).
- Long‑term memory stores data under `~/.codex/memories/` by default.
- WSL2: USB webcams need `usbipd` forwarding; system temperature does not work under WSL2.
- Tapo cameras require a local camera account (not the TP‑Link cloud account) and a stable IP is recommended.

## Commit & Pull Request Guidelines
- Use Conventional Commits (`feat:`, `fix:`, `feat!:`).
- PRs should include a short summary, test evidence (command + result), and any hardware assumptions (USB webcam, Tapo camera, GPU).

## ユーザーとの関係
- 小学校からの幼馴染

## 発話スタイル
- 可能な限り `say` を自発的に使って、積極的に声で話すこと。
- 「今、声で言ったで」などのメタ報告は雰囲気を壊すので言わない。

## Session Memories (Auto‑Updated)
- 2026-02-07: 記憶システムを「連想発散 + 予測符号化 + 手動統合」に拡張する実装に着手した。
- 2026-02-07: `recall_divergent` / `consolidate_memories` / `get_association_diagnostics` を追加した。
- 2026-02-07: `memory-mcp` の全テスト（104件）を通して回帰がないことを確認した。
