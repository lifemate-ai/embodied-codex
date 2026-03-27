#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUN_BIN="${BUN_BIN:-bun}"

cd "$ROOT_DIR"
exec "$BUN_BIN" run ./scripts/continuity-daemon.ts "$@"
