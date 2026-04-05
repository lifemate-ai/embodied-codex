from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("companion-biometrics-ingest.py")
SPEC = importlib.util.spec_from_file_location("companion_biometrics_ingest", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IngestServerHarness:
    def __init__(self, output_path: Path, token: str = "", source: str = "external-companion"):
        handler = MODULE.build_handler_class(
            output_path=output_path,
            bearer_token=token,
            default_source=source,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self.thread.start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class CompanionBiometricsIngestTests(unittest.TestCase):
    def test_normalize_payload_applies_default_source_and_rounds_numbers(self) -> None:
        payload = MODULE.normalize_payload(
            {
                "heart_rate_bpm": 72.4,
                "resting_heart_rate_bpm": True,
                "sleep_score": 84.2,
            },
            default_source="external-companion",
        )

        self.assertEqual(payload["source"], "external-companion")
        self.assertEqual(payload["heart_rate_bpm"], 72)
        self.assertIsNone(payload["resting_heart_rate_bpm"])
        self.assertEqual(payload["sleep_score"], 84)
        self.assertIn("updated_at", payload)

    def test_healthz_reports_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness = IngestServerHarness(Path(tmp) / "companion.json")
            harness.start()
            try:
                with urllib.request.urlopen(f"{harness.base_url}/healthz") as response:
                    payload = json.loads(response.read())
            finally:
                harness.close()

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["output_path"].endswith("companion.json"))
        self.assertEqual(payload["source_default"], "external-companion")

    def test_post_requires_bearer_token_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness = IngestServerHarness(Path(tmp) / "companion.json", token="secret-token")
            harness.start()
            try:
                request = urllib.request.Request(
                    f"{harness.base_url}/ingest",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
            finally:
                harness.close()

        self.assertEqual(error.exception.code, 401)
        error.exception.close()

    def test_post_writes_normalized_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "companion.json"
            harness = IngestServerHarness(output_path, source="external-companion")
            harness.start()
            try:
                request = urllib.request.Request(
                    f"{harness.base_url}/ingest",
                    data=json.dumps(
                        {
                            "heart_rate_bpm": 71.6,
                            "heart_rate_measured_at": "2026-03-29T05:00:00+09:00",
                            "body_battery": 64,
                        }
                    ).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request) as response:
                    payload = json.loads(response.read())
            finally:
                harness.close()

            written = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["heart_rate_bpm"], 72)
        self.assertEqual(payload["body_battery"], 64)
        self.assertEqual(written["heart_rate_measured_at"], "2026-03-29T05:00:00+09:00")
        self.assertEqual(written["source"], "external-companion")


if __name__ == "__main__":
    unittest.main()
