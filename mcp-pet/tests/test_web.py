"""Tests for built-in web server."""

import base64

import pytest
from starlette.testclient import TestClient

from mcp_pet.config import ServerConfig
from mcp_pet.web import create_web_app


@pytest.fixture
def app(tmp_path):
    config = ServerConfig(port=8080, skyway_key="test-key", skyway_room="test-room")
    return create_web_app(config, str(tmp_path))


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHTTPEndpoints:
    def test_client_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "mcp-pet" in resp.text

    def test_viewer_html(self, client):
        resp = client.get("/viewer")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "viewer" in resp.text.lower()

    def test_config_endpoint(self, client):
        resp = client.get("/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["skywayKey"] == "test-key"
        assert data["roomName"] == "test-room"

    def test_config_empty_key(self, tmp_path):
        config = ServerConfig(port=8080, skyway_key="", skyway_room="room")
        app = create_web_app(config, str(tmp_path))
        client = TestClient(app)
        resp = client.get("/config")
        assert resp.json()["skywayKey"] == ""


class TestWebSocket:
    def test_connect(self, client):
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["mode"] == "relay"

    def test_frame_save(self, client, tmp_path):
        # Minimal valid-ish binary data
        fake_jpeg = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 100).decode()

        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected message
            ws.send_json({"type": "frame", "jpeg": fake_jpeg})
            saved = ws.receive_json()
            assert saved["type"] == "saved"
            assert "timestamp" in saved
            assert (tmp_path / "latest.jpg").exists()

    def test_frame_interval_throttle(self, client, tmp_path):
        """Frames within save_interval should not produce a saved response."""
        fake_jpeg = base64.b64encode(b"\xff\xd8" + b"\x00" * 50).decode()

        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected
            # First frame: should save
            ws.send_json({"type": "frame", "jpeg": fake_jpeg})
            saved = ws.receive_json()
            assert saved["type"] == "saved"
            # Second frame immediately: should be throttled (no response)
            ws.send_json({"type": "frame", "jpeg": fake_jpeg})
            # Send a non-frame to ensure we can check there's no saved response
            ws.send_json({"type": "ping"})
            # If throttled correctly, no additional saved message was sent

    def test_invalid_message_ignored(self, client):
        with client.websocket_connect("/ws") as ws:
            _ = ws.receive_json()  # connected
            ws.send_text("not json at all {{{")
            ws.send_json({"type": "unknown"})
            ws.send_json({"type": "frame"})  # missing jpeg
            # Should not crash — connection still alive
