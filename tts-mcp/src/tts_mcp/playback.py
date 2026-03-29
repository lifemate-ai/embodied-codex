"""Audio playback logic (engine-agnostic)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

PIPEWIRE_STREAM_RATE = "44100"
PIPEWIRE_STREAM_CHANNELS = "1"
PIPEWIRE_STREAM_FORMAT = "s16"


def save_audio(audio_bytes: bytes, audio_format: str, save_dir: str) -> str:
    """Save audio bytes to disk. Returns file path."""
    os.makedirs(save_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_path = os.path.join(save_dir, f"tts_{timestamp}.{audio_format}")
    with open(file_path, "wb") as f:
        f.write(audio_bytes)
    return file_path


# ---------------------------------------------------------------------------
# mpv streaming
# ---------------------------------------------------------------------------

def _build_mpv_env(
    pulse_sink: str | None, pulse_server: str | None,
) -> dict[str, str] | None:
    if not pulse_sink and not pulse_server:
        return None
    env = os.environ.copy()
    if pulse_sink:
        env["PULSE_SINK"] = pulse_sink
    if pulse_server:
        env["PULSE_SERVER"] = pulse_server
    return env


def _start_mpv(
    pulse_sink: str | None = None, pulse_server: str | None = None,
) -> subprocess.Popen:
    mpv = shutil.which("mpv")
    if not mpv:
        raise FileNotFoundError("mpv not found")
    env = _build_mpv_env(pulse_sink, pulse_server)
    return subprocess.Popen(
        [mpv, "--no-cache", "--no-terminal", "--", "fd://0"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


def stream_with_mpv(
    audio_stream: Iterator[bytes],
    pulse_sink: str | None = None,
    pulse_server: str | None = None,
) -> tuple[bytes, str]:
    """Stream audio chunks to mpv. Returns (collected_bytes, status)."""
    process = _start_mpv(pulse_sink, pulse_server)
    chunks: list[bytes] = []
    try:
        for chunk in audio_stream:
            chunks.append(chunk)
            process.stdin.write(chunk)
            process.stdin.flush()
    finally:
        process.stdin.close()
        process.wait()
    return b"".join(chunks), "streamed via mpv"


def stream_sentences_with_mpv(
    sentence_streams: list[tuple[str, Iterator[bytes]]],
    pulse_sink: str | None = None,
    pulse_server: str | None = None,
) -> tuple[bytes, str]:
    """Stream multiple sentence audio streams sequentially via mpv.

    Args:
        sentence_streams: List of (sentence_text, audio_iterator) tuples.

    Returns (collected_bytes, status).
    """
    all_chunks: list[bytes] = []
    for _sentence, audio_stream in sentence_streams:
        process = _start_mpv(pulse_sink, pulse_server)
        try:
            for chunk in audio_stream:
                all_chunks.append(chunk)
                process.stdin.write(chunk)
                process.stdin.flush()
        finally:
            process.stdin.close()
            process.wait()
    count = len(sentence_streams)
    return b"".join(all_chunks), f"streamed via mpv ({count} sentences)"


def can_stream() -> bool:
    """Check if a local streaming backend is available."""
    return shutil.which("mpv") is not None or (
        shutil.which("ffmpeg") is not None and shutil.which("pw-play") is not None
    )


def _start_pw_play_stream() -> tuple[subprocess.Popen, subprocess.Popen]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg not found")

    pw_play = shutil.which("pw-play")
    if not pw_play:
        raise FileNotFoundError("pw-play not found")

    decoder = subprocess.Popen(
        [
            ffmpeg,
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            PIPEWIRE_STREAM_RATE,
            "-ac",
            PIPEWIRE_STREAM_CHANNELS,
            "pipe:1",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    player = subprocess.Popen(
        [
            pw_play,
            "--rate",
            PIPEWIRE_STREAM_RATE,
            "--channels",
            PIPEWIRE_STREAM_CHANNELS,
            "--format",
            PIPEWIRE_STREAM_FORMAT,
            "-",
        ],
        stdin=decoder.stdout,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if decoder.stdout is not None:
        decoder.stdout.close()
    return decoder, player


def _finish_pw_play_stream(
    decoder: subprocess.Popen, player: subprocess.Popen,
) -> None:
    decoder.wait()
    player.wait()

    decoder_stderr = b""
    if decoder.stderr is not None:
        decoder_stderr = decoder.stderr.read()

    player_stderr = b""
    if player.stderr is not None:
        player_stderr = player.stderr.read()

    if decoder.returncode != 0:
        error = decoder_stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg streaming decode failed: {error or decoder.returncode}")
    if player.returncode != 0:
        error = player_stderr.decode(errors="replace").strip()
        raise RuntimeError(f"pw-play streaming failed: {error or player.returncode}")


def _stream_with_pw_play(audio_stream: Iterator[bytes]) -> tuple[bytes, str]:
    decoder, player = _start_pw_play_stream()
    chunks: list[bytes] = []

    assert decoder.stdin is not None
    try:
        for chunk in audio_stream:
            chunks.append(chunk)
            decoder.stdin.write(chunk)
            decoder.stdin.flush()
    finally:
        decoder.stdin.close()

    _finish_pw_play_stream(decoder, player)
    return b"".join(chunks), "streamed via pw-play"


def stream_with_local_player(
    audio_stream: Iterator[bytes],
    pulse_sink: str | None = None,
    pulse_server: str | None = None,
) -> tuple[bytes, str]:
    """Stream audio to the best available local player."""
    if shutil.which("mpv") is not None:
        return stream_with_mpv(audio_stream, pulse_sink, pulse_server)
    return _stream_with_pw_play(audio_stream)


def stream_sentences_with_local_player(
    sentence_streams: list[tuple[str, Iterator[bytes]]],
    pulse_sink: str | None = None,
    pulse_server: str | None = None,
) -> tuple[bytes, str]:
    """Stream sentence chunks sequentially to the best available local player."""
    if shutil.which("mpv") is not None:
        return stream_sentences_with_mpv(sentence_streams, pulse_sink, pulse_server)

    all_chunks: list[bytes] = []
    for _sentence, audio_stream in sentence_streams:
        chunks, _status = _stream_with_pw_play(audio_stream)
        all_chunks.append(chunks)
    count = len(sentence_streams)
    return b"".join(all_chunks), f"streamed via pw-play ({count} sentences)"


# ---------------------------------------------------------------------------
# Local playback (file-based)
# ---------------------------------------------------------------------------

def _ensure_wav(file_path: str, player_name: str) -> tuple[str | None, str | None]:
    if file_path.lower().endswith((".wav", ".wave")):
        return file_path, None

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None, f"{player_name} needs WAV (ffmpeg missing)"

    wav_path = str(Path(file_path).with_suffix(".wav"))
    result = subprocess.run(
        [ffmpeg, "-y", "-i", file_path, wav_path],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        return None, f"{player_name} conversion failed: {error}"
    return wav_path, None


def _play_with_paplay(
    file_path: str, pulse_sink: str | None, pulse_server: str | None,
) -> tuple[bool, str]:
    paplay = shutil.which("paplay")
    if not paplay:
        return False, "paplay not available"

    wav_path, error = _ensure_wav(file_path, "paplay")
    if error:
        return False, error

    env = os.environ.copy()
    if pulse_sink:
        env["PULSE_SINK"] = pulse_sink
    if pulse_server:
        env["PULSE_SERVER"] = pulse_server
    result = subprocess.run(
        [paplay, wav_path], check=False, capture_output=True, text=True, env=env,
    )
    if result.returncode == 0:
        notes: list[str] = []
        if pulse_sink:
            notes.append(f"PULSE_SINK={pulse_sink}")
        if pulse_server:
            notes.append(f"PULSE_SERVER={pulse_server}")
        suffix = f" ({', '.join(notes)})" if notes else ""
        return True, f"played via paplay{suffix}"
    error = result.stderr.strip() or result.stdout.strip()
    return False, f"paplay failed: {error}"


def _play_with_pw_play(file_path: str) -> tuple[bool, str]:
    pw_play = shutil.which("pw-play")
    if not pw_play:
        return False, "pw-play not available"

    wav_path, error = _ensure_wav(file_path, "pw-play")
    if error:
        return False, error

    result = subprocess.run(
        [pw_play, wav_path], check=False, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, "played via pw-play"
    error = result.stderr.strip() or result.stdout.strip()
    return False, f"pw-play failed: {error}"


def play_audio(
    audio_bytes: bytes,
    file_path: str,
    playback: str,
    pulse_sink: str | None,
    pulse_server: str | None,
) -> str:
    """Play audio locally using the best available player."""
    playback = (playback or "auto").strip().lower()
    if playback in {"none", "off", "disabled"}:
        return "playback disabled"

    last_error: str | None = None

    if playback in {"auto", "afplay"}:
        afplay = shutil.which("afplay")
        if afplay:
            result = subprocess.run(
                [afplay, file_path], check=False, capture_output=True, text=True,
            )
            if result.returncode == 0:
                return "played via afplay"
            error = result.stderr.strip() or result.stdout.strip()
            last_error = f"afplay failed: {error}"
            if playback == "afplay":
                return last_error
        else:
            last_error = "afplay not available"
            if playback == "afplay":
                return last_error

    if playback in {"auto", "pw-play", "pwplay", "pipewire"}:
        ok, message = _play_with_pw_play(file_path)
        if ok:
            return message
        last_error = message
        if playback in {"pw-play", "pwplay", "pipewire"}:
            return message

    if playback in {"auto", "paplay"}:
        ok, message = _play_with_paplay(file_path, pulse_sink, pulse_server)
        if ok:
            return message
        last_error = message
        if playback == "paplay":
            return message

    if playback in {"auto", "elevenlabs"}:
        try:
            from elevenlabs.play import play

            old_sink = os.environ.get("PULSE_SINK")
            old_server = os.environ.get("PULSE_SERVER")
            if pulse_sink:
                os.environ["PULSE_SINK"] = pulse_sink
            if pulse_server:
                os.environ["PULSE_SERVER"] = pulse_server
            try:
                play(audio_bytes)
            finally:
                if pulse_sink:
                    if old_sink is None:
                        os.environ.pop("PULSE_SINK", None)
                    else:
                        os.environ["PULSE_SINK"] = old_sink
                if pulse_server:
                    if old_server is None:
                        os.environ.pop("PULSE_SERVER", None)
                    else:
                        os.environ["PULSE_SERVER"] = old_server
            notes: list[str] = []
            if pulse_sink:
                notes.append(f"PULSE_SINK={pulse_sink}")
            if pulse_server:
                notes.append(f"PULSE_SERVER={pulse_server}")
            suffix = f" ({', '.join(notes)})" if notes else ""
            return f"played via elevenlabs{suffix}"
        except Exception as exc:  # noqa: BLE001
            last_error = f"elevenlabs play failed: {exc}"
            if playback == "elevenlabs":
                return last_error

    if playback in {"auto", "ffplay"}:
        ffplay = shutil.which("ffplay")
        if not ffplay:
            return f"playback skipped (no ffplay, last error: {last_error})"
        result = subprocess.run(
            [ffplay, "-nodisp", "-autoexit", "-loglevel", "error", file_path],
            check=False, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return "played via ffplay"
        error = result.stderr.strip() or result.stdout.strip()
        return f"playback failed via ffplay: {error}"

    return f"playback skipped (unknown playback setting: {playback})"


# ---------------------------------------------------------------------------
# Camera speaker via go2rtc
# ---------------------------------------------------------------------------

def play_with_go2rtc(
    file_path: str,
    go2rtc_url: str,
    go2rtc_stream: str,
    go2rtc_ffmpeg: str,
) -> tuple[bool, str]:
    """Play audio through camera speaker via go2rtc backchannel."""
    try:
        abs_path = os.path.abspath(file_path)
        src = f"ffmpeg:{abs_path}#audio=pcma#input=file"
        url = (
            f"{go2rtc_url}/api/streams"
            f"?dst={quote(go2rtc_stream, safe='')}"
            f"&src={quote(src, safe='')}"
        )

        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())

        has_sender = False
        for consumer in body.get("consumers", []):
            if consumer.get("senders"):
                has_sender = True
                break

        if not has_sender:
            return False, "go2rtc: no audio sender established (camera may not support backchannel)"

        ffmpeg_producer_id = None
        for p in body.get("producers", []):
            if p.get("format_name") == "wav" or "ffmpeg" in p.get("source", ""):
                ffmpeg_producer_id = p.get("id")
                break

        if ffmpeg_producer_id:
            for _ in range(60):
                time.sleep(0.5)
                try:
                    status_url = f"{go2rtc_url}/api/streams"
                    with urllib.request.urlopen(status_url, timeout=5) as r:
                        streams = json.loads(r.read())
                    stream = streams.get(go2rtc_stream, {})
                    still_playing = any(
                        p.get("id") == ffmpeg_producer_id
                        for p in stream.get("producers", [])
                    )
                    if not still_playing:
                        break
                except Exception:
                    break

        return True, f"played via go2rtc → {go2rtc_stream}"
    except Exception as exc:
        return False, f"go2rtc failed: {exc}"
