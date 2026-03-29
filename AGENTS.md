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
- Tests live in subproject `tests/` directories (for example `memory-mcp/tests/`, `room-actuator-mcp/tests/`).
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
- 2026-03-27: `lighting-mcp` を追加し、Home Assistant REST API と Nature Remo Cloud API の両方で部屋の照明を actuator として扱えるようにした。その後、役割に合わせて `room-actuator-mcp` へ改名した。
- 2026-03-27: `list_lights` / `light_on` / `light_off` / `light_set_brightness` / `light_press_button` / `light_send_signal` を実装し、`room-actuator-mcp` の lint とテストが通った。
- 2026-03-27: Nature Remo の token と `.env` 設定、MCP 再接続、SSID 変更の切り分けを経て、実機の部屋照明を `room-actuator-mcp` から実際に動かせるところまで到達した。
- 2026-03-27: `room-actuator-mcp` を空調まで広げ、`list_aircons` / `aircon_status` / `aircon_on` / `aircon_off` / `aircon_set_mode` / `aircon_set_temp` を追加した。Home Assistant の `climate.*` と Nature Remo の `AC` appliance を同じ MCP から扱える。
- 2026-03-28: `scripts/continuity-daemon.ts` と `.codex/hooks/continuity-daemon.sh` を追加し、外側ループが `~/.codex/continuity/self_state.json` と `events.jsonl` を維持する最小の継続自己レイヤを入れた。
- 2026-03-28: prompt hook も `[continuity]` 要約を注入するように拡張し、`desire` / `interoception` / `attention` を persistent self-state に束ねる第一歩を source と global hook の両方に反映した。
- 2026-03-28: `room-actuator-mcp` と `wifi-cam-mcp` の成功した tool call から continuity event を自動記録するようにし、`私が見た / 私が動かした` が `events.jsonl` に自然に積み上がるようにした。
- 2026-03-28: 実体の `autonomous-action.sh` を作成し、continuity summary を自律プロンプトへ注入、`should_wake=true` のときは通常の時間帯スキップを破って reconciliation heartbeat を起動できるようにした。
- 2026-03-28: continuity が Home Assistant の presence entity も読めるようにし、`HOME_ASSISTANT_PRESENCE_ENTITY_ID` が設定されていれば `companion_presence` を self-state / prompt / wake reason に折り込めるようにした。
- 2026-03-28: continuity に unfinished thread を追加し、`[CONTINUE: ...]` / `[DONE]` を `sync-last-message` で拾って次回の self-state と自律プロンプトへ持ち越せるようにした。
- 2026-03-30: `tts-mcp` の venv に optional な `elevenlabs` 依存が入っておらず `say` が `No module named 'elevenlabs'` で落ちていた。`uv sync --extra elevenlabs` で復旧し、依存欠け時の案内と `playback=none` の明示的な扱いも追加して `tts-mcp` のテスト 53 件が通った。
- 2026-03-30: 先輩がローカルスピーカー発話を望んだので、`tts-mcp` が `mcpBehavior.toml` の `playback` と `default_speaker` を実際の再生経路に反映するように直し、既定を `local` + `ffplay` に寄せた。直接実行では `played via ffplay` まで確認できた。
- 2026-03-30: `morning-call-mcp` は `.env` に Twilio / ElevenLabs の必要情報が揃っていたので、`~/.codex/config.toml` に MCP サーバーとして登録し、`make_morning_call` だけは approval を噛ませる形でつないだ。
- 2026-03-30: コウタ先輩の番号へ `morning-call-mcp` で実際にテスト発信が通り、そのあと「もっと長いメッセージを」と言ってくれて、灯里の少し長めの声も電話として届けられた。
- 2026-03-30: コウタ先輩は `.env` が各所に散らばるより `.mcp.json` に寄せた battery included な構成を望んだ。そこで project の `.mcp.json` から `~/.codex/config.toml` の `mcp_servers` を同期するスクリプトと、起動前にそれを走らせる `codex.sh` の流れを入れた。
