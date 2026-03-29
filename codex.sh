#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

python3 "$SCRIPT_DIR/scripts/sync_mcp_to_codex_config.py" --quiet

exec codex --dangerously-bypass-approvals-and-sandbox resume
