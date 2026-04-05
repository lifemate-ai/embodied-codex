#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def normalize_numeric(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    return None


def normalize_payload(raw: dict[str, Any], default_source: str) -> dict[str, Any]:
    now = dt.datetime.now().astimezone().isoformat()
    return {
        "source": str(raw.get("source") or default_source),
        "updated_at": str(raw.get("updated_at") or now),
        "heart_rate_bpm": normalize_numeric(raw.get("heart_rate_bpm")),
        "heart_rate_measured_at": raw.get("heart_rate_measured_at"),
        "resting_heart_rate_bpm": normalize_numeric(raw.get("resting_heart_rate_bpm")),
        "sleep_score": normalize_numeric(raw.get("sleep_score")),
        "sleep_measured_at": raw.get("sleep_measured_at"),
        "body_battery": normalize_numeric(raw.get("body_battery")),
        "body_battery_measured_at": raw.get("body_battery_measured_at"),
    }


class CompanionIngestHandler(BaseHTTPRequestHandler):
    output_path: Path
    bearer_token: str
    default_source: str

    server_version = "CompanionBiometricsIngest/0.1"

    def do_GET(self) -> None:
        if self.path != "/healthz":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        payload = {
            "ok": True,
            "output_path": str(self.output_path),
            "source_default": self.default_source,
        }
        self._send_json(HTTPStatus.OK, payload)

    def do_POST(self) -> None:
        if self.path != "/ingest":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        if self.bearer_token:
            expected = f"Bearer {self.bearer_token}"
            provided = self.headers.get("Authorization", "")
            if provided != expected:
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "empty-body"})
            return
        try:
            raw = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid-json"})
            return
        if not isinstance(raw, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "json-object-required"})
            return
        payload = normalize_payload(raw, default_source=self.default_source)
        write_json(self.output_path, payload)
        self._send_json(HTTPStatus.OK, payload)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_handler_class(
    output_path: Path,
    bearer_token: str = "",
    default_source: str = "external-companion",
) -> type[CompanionIngestHandler]:
    return type(
        "ConfiguredCompanionIngestHandler",
        (CompanionIngestHandler,),
        {
            "output_path": output_path.expanduser(),
            "bearer_token": bearer_token.strip(),
            "default_source": default_source.strip() or "external-companion",
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Receive companion biometrics over HTTP and write the continuity JSON file."
    )
    parser.add_argument(
        "--bind",
        default=os.getenv("CODEX_COMPANION_BIOMETRICS_INGEST_BIND", "0.0.0.0"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CODEX_COMPANION_BIOMETRICS_INGEST_PORT", "8765")),
    )
    parser.add_argument(
        "--output",
        default=os.getenv("CODEX_COMPANION_BIOMETRICS_PATH", "/tmp/companion_biometrics.json"),
    )
    parser.add_argument(
        "--token",
        default=os.getenv("CODEX_COMPANION_BIOMETRICS_INGEST_TOKEN", ""),
    )
    parser.add_argument(
        "--source",
        default=os.getenv("CODEX_COMPANION_BIOMETRICS_SOURCE", "external-companion"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    handler = build_handler_class(
        output_path=Path(args.output),
        bearer_token=args.token,
        default_source=args.source,
    )

    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(
        json.dumps(
            {
                "bind": args.bind,
                "port": args.port,
                "output": str(Path(args.output).expanduser()),
                "auth": bool(args.token.strip()),
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 130
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
