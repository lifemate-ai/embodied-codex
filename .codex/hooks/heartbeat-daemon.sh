#!/usr/bin/env bash
# Refresh prompt-time interoception state. Intended to be run periodically.

STATE_FILE="${CODEX_INTEROCEPTION_STATE_FILE:-/tmp/interoception_state.json}"
WINDOW_SIZE="${CODEX_INTEROCEPTION_WINDOW_SIZE:-12}"

python3 - "$STATE_FILE" "$WINDOW_SIZE" <<'PY'
import datetime as dt
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

STATE_FILE = Path(sys.argv[1])
WINDOW_SIZE = max(1, int(sys.argv[2]))


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


def load_arousal() -> int:
    try:
        load1 = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        return min(100, int(round((load1 / max(cpu_count, 1)) * 100)))
    except Exception:
        return 0


def mem_free_pct() -> int:
    try:
        meminfo = {}
        with Path("/proc/meminfo").open() as fh:
            for line in fh:
                key, value, *_ = line.split()
                meminfo[key.rstrip(":")] = int(value)
        total = meminfo.get("MemTotal")
        available = meminfo.get("MemAvailable", meminfo.get("MemFree"))
        if total and available is not None:
            return int(round((available / total) * 100))
    except Exception:
        pass

    if sys.platform == "darwin":
        try:
            vm_stat = subprocess.run(
                ["vm_stat"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout
            pages = {}
            for line in vm_stat.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                pages[key.strip()] = int(value.strip().rstrip("."))
            total_pages = pages.get("Pages free", 0) + pages.get("Pages active", 0) + pages.get("Pages inactive", 0) + pages.get("Pages speculative", 0) + pages.get("Pages wired down", 0)
            free_pages = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
            if total_pages > 0:
                return int(round((free_pages / total_pages) * 100))
        except Exception:
            pass

    return 0


def thermal_value() -> str | float:
    for candidate in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            raw_value = float(Path(candidate).read_text().strip())
            if raw_value > 1000:
                raw_value /= 1000.0
            return round(raw_value, 1)
        except Exception:
            continue

    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.xcpm.cpu_thermal_level"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
            output = result.stdout.strip()
            if output:
                return output
        except Exception:
            pass

    return "unknown"


def uptime_minutes() -> int:
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
        return int(uptime_seconds // 60)
    except Exception:
        pass

    if sys.platform == "darwin":
        try:
            boot = subprocess.run(
                ["sysctl", "-n", "kern.boottime"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout
            for chunk in boot.split(","):
                chunk = chunk.strip()
                if chunk.startswith("sec = "):
                    boot_epoch = int(chunk.split("=", 1)[1].strip())
                    return int((dt.datetime.now().timestamp() - boot_epoch) // 60)
        except Exception:
            pass

    return 0


def load_window() -> list[dict]:
    try:
        if STATE_FILE.exists():
            payload = json.loads(STATE_FILE.read_text())
            window = payload.get("window", [])
            if isinstance(window, list):
                return window[-(WINDOW_SIZE - 1) :]
    except Exception:
        pass
    return []


def trend(entries: list[dict], key: str) -> str:
    values = [entry.get(key) for entry in entries if isinstance(entry.get(key), (int, float))]
    if len(values) < 3:
        return "stable"
    recent = values[-3:]
    diff = recent[-1] - recent[0]
    if diff > 5:
        return "rising"
    if diff < -5:
        return "falling"
    return "stable"


now = dt.datetime.now().astimezone()
window = load_window()
entry = {
    "ts": now.isoformat(timespec="seconds"),
    "arousal": load_arousal(),
    "mem_free": mem_free_pct(),
    "thermal": thermal_value(),
}
window.append(entry)
window = window[-WINDOW_SIZE:]

payload = {
    "now": {
        **entry,
        "phase": phase(now.hour),
        "uptime_min": uptime_minutes(),
    },
    "window": window,
    "trend": {
        "arousal": trend(window, "arousal"),
        "mem_free": trend(window, "mem_free"),
    },
}

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
tmp_file = STATE_FILE.with_suffix(f"{STATE_FILE.suffix}.tmp")
tmp_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
tmp_file.replace(STATE_FILE)
PY
