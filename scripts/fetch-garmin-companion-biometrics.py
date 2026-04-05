#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "garminconnect>=0.2.28",
# ]
# ///

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

from garminconnect import Garmin, GarminConnectConnectionError

REPO_DIR = Path(__file__).resolve().parent.parent
DOTENV_PATH = Path(
    os.getenv("CODEX_ENV_FILE", str(REPO_DIR / ".env"))
).expanduser()


def expand_env_value(value: str) -> str:
    return os.path.expanduser(os.path.expandvars(value))


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = expand_env_value(value)


load_dotenv(DOTENV_PATH)

OUTPUT_PATH = Path(
    os.getenv("CODEX_COMPANION_BIOMETRICS_PATH", "/tmp/companion_biometrics.json")
).expanduser()
TOKENSTORE = Path(
    expand_env_value(
        os.getenv("GARMINTOKENS", os.getenv("GARMIN_TOKENSTORE", "~/.garminconnect"))
    )
).expanduser()
EMAIL = os.getenv("GARMIN_EMAIL", "").strip()
PASSWORD = os.getenv("GARMIN_PASSWORD", "").strip()
SOURCE = os.getenv("CODEX_COMPANION_BIOMETRICS_SOURCE", "garmin-connect").strip()
ALLOW_LEGACY_PASSWORD_LOGIN = (
    os.getenv("CODEX_GARMIN_ALLOW_LEGACY_PASSWORD_LOGIN", "0").strip() == "1"
)
BODY_BATTERY_LOOKBACK_DAYS = max(
    1, int(os.getenv("CODEX_GARMIN_BODY_BATTERY_LOOKBACK_DAYS", "2"))
)
SLEEP_LOOKBACK_DAYS = max(
    1, int(os.getenv("CODEX_GARMIN_SLEEP_LOOKBACK_DAYS", "2"))
)


def parse_date(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.astimezone() if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, dt.date):
        return dt.datetime.combine(
            value, dt.time.min, tzinfo=dt.datetime.now().astimezone().tzinfo
        )
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 1_000_000_000_000:
            number /= 1000.0
        try:
            return dt.datetime.fromtimestamp(number, tz=dt.timezone.utc).astimezone()
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return parse_date(int(text))
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed.astimezone() if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def isoformat_or_none(value: dt.datetime | None) -> str | None:
    return value.astimezone().isoformat() if value is not None else None


def is_bpm(value: Any) -> bool:
    return isinstance(value, (int, float)) and 25 <= float(value) <= 240


def is_percentage(value: Any) -> bool:
    return isinstance(value, (int, float)) and 0 <= float(value) <= 100


def walk(value: Any) -> list[Any]:
    items: list[Any] = [value]
    if isinstance(value, dict):
        for nested in value.values():
            items.extend(walk(nested))
    elif isinstance(value, list):
        for nested in value:
            items.extend(walk(nested))
    return items


def first_path(data: Any, *paths: tuple[Any, ...]) -> Any:
    for path in paths:
        current = data
        try:
            for segment in path:
                if isinstance(current, dict):
                    current = current[segment]
                elif isinstance(current, list) and isinstance(segment, int):
                    current = current[segment]
                else:
                    raise KeyError(segment)
            if current is not None:
                return current
        except (KeyError, IndexError, TypeError):
            continue
    return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def token_cache_exists(path: Path) -> bool:
    return (path / "oauth1_token.json").exists() and (path / "oauth2_token.json").exists()


def looks_like_rate_limit(error: Exception) -> bool:
    return "429" in str(error) or "too many requests" in str(error).lower()


def login() -> Garmin:
    has_token_cache = token_cache_exists(TOKENSTORE)
    if not has_token_cache and not ALLOW_LEGACY_PASSWORD_LOGIN:
        raise SystemExit(
            "Garmin login bootstrap is disabled by default. "
            "As of 2026-03-28, upstream garth reports Garmin auth-flow changes and "
            "new logins may no longer work. Point GARMINTOKENS at an existing Garmin "
            f"token cache (default: {TOKENSTORE}) or set "
            "CODEX_GARMIN_ALLOW_LEGACY_PASSWORD_LOGIN=1 to try the legacy password "
            "flow anyway."
        )
    if not has_token_cache and (not EMAIL or not PASSWORD):
        raise SystemExit(
            "GARMIN_EMAIL / GARMIN_PASSWORD are required until a Garmin token cache exists."
        )

    client = Garmin(EMAIL or None, PASSWORD or None)
    original_tokenstore = os.environ.pop("GARMINTOKENS", None)
    try:
        try:
            client.login(str(TOKENSTORE) if has_token_cache else None)
        except GarminConnectConnectionError as error:
            if not has_token_cache and looks_like_rate_limit(error):
                raise SystemExit(
                    "Garmin SSO rejected the legacy bootstrap login with HTTP 429. "
                    "Given garth's 2026-03-28 deprecation notice, this may not be a "
                    "temporary rate limit at all: new password logins may simply no "
                    "longer work. Prefer an existing Garmin token cache at "
                    f"{TOKENSTORE}, or switch the companion-biometrics pipeline to a "
                    "different source such as Health Sync / Fitbit / Android-side export."
                ) from error
            raise
        if not has_token_cache:
            TOKENSTORE.mkdir(parents=True, exist_ok=True)
            client.garth.dump(str(TOKENSTORE))
    finally:
        if original_tokenstore is not None:
            os.environ["GARMINTOKENS"] = original_tokenstore
    return client


def parse_latest_heart_rate(heart_data: dict[str, Any]) -> tuple[int | None, str | None]:
    samples: list[tuple[dt.datetime, int]] = []

    values = heart_data.get("heartRateValues")
    if isinstance(values, dict):
        for timestamp, value in values.items():
            when = parse_date(timestamp)
            bpm = None
            if is_bpm(value):
                bpm = int(round(float(value)))
            elif isinstance(value, list):
                for candidate in value:
                    if is_bpm(candidate):
                        bpm = int(round(float(candidate)))
                        break
            if when and bpm is not None:
                samples.append((when, bpm))

    values_array = heart_data.get("heartRateValuesArray")
    if isinstance(values_array, list):
        for row in values_array:
            if not isinstance(row, list) or len(row) < 2:
                continue
            when = parse_date(row[0])
            bpm = int(round(float(row[1]))) if is_bpm(row[1]) else None
            if when and bpm is not None:
                samples.append((when, bpm))

    for node in walk(heart_data):
        if not isinstance(node, dict):
            continue
        when = first_path(
            node,
            ("measurementTimeLocal",),
            ("measurementTimeGMT",),
            ("startTimeLocal",),
            ("startTimeGMT",),
            ("time",),
            ("timestamp",),
        )
        bpm_value = first_path(node, ("heartRate",), ("bpm",), ("value",))
        when_dt = parse_date(when)
        if when_dt is None or not is_bpm(bpm_value):
            continue
        samples.append((when_dt, int(round(float(bpm_value)))))

    if not samples:
        return None, None

    latest = max(samples, key=lambda item: item[0])
    return latest[1], isoformat_or_none(latest[0])


def parse_sleep_metric(sleep_data: dict[str, Any]) -> tuple[int | None, str | None]:
    score = first_path(
        sleep_data,
        ("dailySleepDTO", "sleepScores", "overall", "value"),
        ("dailySleepDTO", "sleepScores", "overallSleepScore", "value"),
        ("dailySleepDTO", "sleepScores", "overallScore", "value"),
        ("dailySleepDTO", "overallSleepScore", "value"),
        ("dailySleepDTO", "sleepScore"),
        ("sleepScore",),
    )
    measured_at = first_path(
        sleep_data,
        ("dailySleepDTO", "calendarDate"),
        ("dailySleepDTO", "sleepStartTimestampLocal"),
        ("dailySleepDTO", "sleepStartTimestampGMT"),
    )

    if not is_percentage(score):
        return None, isoformat_or_none(parse_date(measured_at))

    return int(round(float(score))), isoformat_or_none(parse_date(measured_at))


def parse_body_battery_metric(body_battery_data: Any) -> tuple[int | None, str | None]:
    samples: list[tuple[dt.datetime, int]] = []

    values_dict = first_path(
        body_battery_data,
        ("bodyBatteryValues",),
        ("bodyBatteryValueMap",),
    )
    if isinstance(values_dict, dict):
        for timestamp, value in values_dict.items():
            when = parse_date(timestamp)
            if when and is_percentage(value):
                samples.append((when, int(round(float(value)))))

    values_array = first_path(
        body_battery_data,
        ("bodyBatteryValuesArray",),
        ("bodyBatteryValueArray",),
    )
    if isinstance(values_array, list):
        for row in values_array:
            if not isinstance(row, list) or len(row) < 2:
                continue
            when = parse_date(row[0])
            value = row[1]
            if when and is_percentage(value):
                samples.append((when, int(round(float(value)))))

    for node in walk(body_battery_data):
        if not isinstance(node, dict):
            continue
        value = first_path(
            node,
            ("bodyBatteryMostRecent",),
            ("mostRecent",),
            ("bodyBatteryLevel",),
            ("bodyBattery",),
            ("value",),
        )
        when = first_path(
            node,
            ("calendarDate",),
            ("measurementTimeLocal",),
            ("measurementTimeGMT",),
            ("timestamp",),
            ("time",),
        )
        when_dt = parse_date(when)
        if when_dt and is_percentage(value):
            samples.append((when_dt, int(round(float(value)))))

    if not samples:
        return None, None

    latest = max(samples, key=lambda item: item[0])
    return latest[1], isoformat_or_none(latest[0])


def load_latest_sleep_data(client: Garmin, today: dt.date) -> dict[str, Any]:
    for offset in range(SLEEP_LOOKBACK_DAYS):
        candidate = (today - dt.timedelta(days=offset)).isoformat()
        payload = client.get_sleep_data(candidate)
        if isinstance(payload, dict) and payload:
            return payload
    return {}


def main() -> int:
    client = login()
    now = dt.datetime.now().astimezone()
    today = now.date()

    heart_data = client.get_heart_rates(today.isoformat()) or {}
    latest_hr, latest_hr_at = parse_latest_heart_rate(heart_data)
    resting_hr = heart_data.get("restingHeartRate")

    sleep_data = load_latest_sleep_data(client, today)
    sleep_score, sleep_at = parse_sleep_metric(sleep_data)

    bb_start = (today - dt.timedelta(days=BODY_BATTERY_LOOKBACK_DAYS - 1)).isoformat()
    body_battery_data = client.get_body_battery(bb_start, today.isoformat())
    body_battery, body_battery_at = parse_body_battery_metric(body_battery_data)

    payload = {
        "source": SOURCE or "garmin-connect",
        "updated_at": now.isoformat(),
        "heart_rate_bpm": latest_hr,
        "heart_rate_measured_at": latest_hr_at,
        "resting_heart_rate_bpm": (
            int(round(float(resting_hr))) if is_bpm(resting_hr) else None
        ),
        "sleep_score": sleep_score,
        "sleep_measured_at": sleep_at,
        "body_battery": body_battery,
        "body_battery_measured_at": body_battery_at,
    }
    write_json(OUTPUT_PATH, payload)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
