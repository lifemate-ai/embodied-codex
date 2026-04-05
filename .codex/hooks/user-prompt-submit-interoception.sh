#!/usr/bin/env bash
# Inject prompt-time interoception into Codex via the experimental UserPromptSubmit hook.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
REPO_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
STATE_FILE="${CODEX_INTEROCEPTION_STATE_FILE:-/tmp/interoception_state.json}"

LOW_LEVEL_CONTEXT="$(python3 - "$STATE_FILE" <<'PY'
import datetime as dt
import json
import os
import sys
from pathlib import Path

STATE_FILE = Path(sys.argv[1])


def phase(hour: int) -> str:
    if 5 <= hour < 10:
        return "morning"
    if 10 <= hour < 12:
        return "late_morning"
    if 12 <= hour < 14:
        return "midday"
    if 14 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 20:
        return "evening"
    if 20 <= hour < 23:
        return "night"
    return "late_night"


def current_snapshot() -> str:
    now = dt.datetime.now().astimezone()
    parts = [
        f"time={now.strftime('%H:%M:%S')}",
        f"day={now.strftime('%a')}",
        f"date={now.strftime('%Y-%m-%d')}",
        f"phase={phase(now.hour)}",
    ]

    try:
        load1 = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        arousal = min(100, int(round((load1 / max(cpu_count, 1)) * 100)))
        parts.append(f"arousal={arousal}%")
    except Exception:
        pass

    try:
        meminfo = {}
        with Path("/proc/meminfo").open() as fh:
            for line in fh:
                key, value, *_ = line.split()
                meminfo[key.rstrip(":")] = int(value)
        total = meminfo.get("MemTotal")
        available = meminfo.get("MemAvailable", meminfo.get("MemFree"))
        if total and available is not None:
            mem_free = int(round((available / total) * 100))
            parts.append(f"mem_free={mem_free}%")
    except Exception:
        pass

    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
        parts.append(f"uptime={int(uptime_seconds // 60)}min")
    except Exception:
        pass

    return "[interoception] " + " ".join(parts) + " (prompt-time snapshot)"


def state_snapshot() -> str | None:
    if not STATE_FILE.exists():
        return None

    try:
        payload = json.loads(STATE_FILE.read_text())
        now_data = payload.get("now", {})
        trend = payload.get("trend", {})
        window = payload.get("window", [])

        timestamp = now_data.get("ts")
        try:
            observed_at = dt.datetime.fromisoformat(timestamp) if timestamp else dt.datetime.now().astimezone()
        except Exception:
            observed_at = dt.datetime.now().astimezone()

        arrows = {"rising": "↑", "falling": "↓", "stable": "→"}
        arousal_arrow = arrows.get(trend.get("arousal"), "→")
        mem_arrow = arrows.get(trend.get("mem_free"), "→")

        return (
            "[interoception] "
            f"time={observed_at.strftime('%H:%M:%S')} "
            f"day={observed_at.strftime('%a')} "
            f"date={observed_at.strftime('%Y-%m-%d')} "
            f"phase={now_data.get('phase', phase(observed_at.hour))} "
            f"arousal={now_data.get('arousal', '?')}%({arousal_arrow}) "
            f"thermal={now_data.get('thermal', '?')} "
            f"mem_free={now_data.get('mem_free', '?')}%({mem_arrow}) "
            f"uptime={now_data.get('uptime_min', '?')}min "
            f"heartbeats={len(window)}"
        )
    except Exception:
        return None


print(state_snapshot() or current_snapshot())
PY
)"

HIGH_LEVEL_CONTEXT=""
if command -v bun >/dev/null 2>&1; then
  HIGH_LEVEL_CONTEXT="$(cd "$REPO_DIR" && bun run ./scripts/interoception.ts 2>/dev/null || true)"
fi

ATTENTION_CONTEXT=""
if command -v bun >/dev/null 2>&1; then
  ATTENTION_CONTEXT="$(cd "$REPO_DIR" && bun run ./scripts/attention-state.ts 2>/dev/null || true)"
fi

CONTINUITY_CONTEXT=""
if command -v bun >/dev/null 2>&1; then
  CONTINUITY_CONTEXT="$(cd "$REPO_DIR" && bun run ./scripts/continuity-daemon.ts summary 2>/dev/null || true)"
fi

HOOK_OUTPUT="$(python3 - "$LOW_LEVEL_CONTEXT" "$HIGH_LEVEL_CONTEXT" "$ATTENTION_CONTEXT" "$CONTINUITY_CONTEXT" <<'PY'
import json
import sys

parts = [part.strip() for part in sys.argv[1:] if part.strip()]
if not parts:
    sys.exit(0)

print(
    json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": "\n".join(parts),
            }
        },
        ensure_ascii=False,
    )
)
PY
)"

if [ -n "$HOOK_OUTPUT" ]; then
  printf '%s\n' "$HOOK_OUTPUT"
fi

exit 0
