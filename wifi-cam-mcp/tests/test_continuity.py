"""Continuity recording tests for wifi-cam MCP."""

from __future__ import annotations

import asyncio

import pytest

from wifi_cam_mcp.camera import AudioResult, CaptureResult, Direction, MoveResult
from wifi_cam_mcp.server import CameraMCPServer


def test_capture_and_move_details():
    server = CameraMCPServer()

    capture = CaptureResult(
        image_base64="abc",
        file_path="/tmp/capture.jpg",
        timestamp="2026-03-28T01:23:45Z",
        width=1920,
        height=1080,
    )
    move = MoveResult(
        direction=Direction.LEFT,
        degrees=30,
        success=True,
        message="Moved left by 30 degrees",
    )

    assert (
        server._capture_detail("see", capture)
        == "see timestamp=2026-03-28T01:23:45Z size=1920x1080 file=/tmp/capture.jpg"
    )
    assert (
        server._move_detail("look_left", move)
        == "look_left direction=left degrees=30 success=yes"
    )


def test_audio_detail_truncates_transcript():
    server = CameraMCPServer()
    audio = AudioResult(
        audio_base64="abc",
        file_path="/tmp/audio.wav",
        timestamp="2026-03-28T01:23:45Z",
        duration=5.0,
        transcript=" ".join(["quiet"] * 40),
    )

    detail = server._audio_detail(audio)

    assert detail.startswith(
        "listen duration=5.0s timestamp=2026-03-28T01:23:45Z file=/tmp/audio.wav transcript="
    )
    assert detail.endswith("...")


@pytest.mark.asyncio
async def test_record_continuity_event_invokes_wrapper(monkeypatch, tmp_path):
    script = tmp_path / "continuity-record.sh"
    script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("CODEX_CONTINUITY_RECORD_SCRIPT", str(script))

    called: dict[str, object] = {}

    class DummyProcess:
        returncode = 0

        async def communicate(self):
            return (b"", b"")

    async def fake_create_subprocess_exec(*args, **kwargs):
        called["args"] = args
        called["kwargs"] = kwargs
        return DummyProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    server = CameraMCPServer()
    await server._record_continuity_event("record-observation", "see file=/tmp/capture.jpg")

    assert called["args"] == (
        str(script),
        "record-observation",
        "wifi-cam",
        "see file=/tmp/capture.jpg",
    )
