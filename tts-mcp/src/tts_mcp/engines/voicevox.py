"""VOICEVOX TTS engine."""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


class VoicevoxEngine:
    """VOICEVOX TTS engine (local HTTP API, no external dependencies)."""

    def __init__(self, url: str = "http://localhost:50021", speaker: int = 3) -> None:
        self._url = url.rstrip("/")
        self._speaker = speaker

    @property
    def engine_name(self) -> str:
        return "voicevox"

    def is_available(self) -> bool:
        """Check if VOICEVOX engine is running."""
        try:
            req = urllib.request.Request(f"{self._url}/version", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                resp.read()
            return True
        except Exception:
            return False

    def synthesize(self, text: str, **kwargs: Any) -> tuple[bytes, str]:
        """Synthesize text using VOICEVOX 2-step API.

        Kwargs:
            speaker: Override speaker ID.
            speed_scale: Speech speed (0.5-2.0).
            pitch_scale: Pitch shift (-0.15 to 0.15).

        Returns:
            Tuple of (wav_bytes, 'wav').
        """
        speaker = kwargs.get("speaker", self._speaker)
        speed_scale = kwargs.get("speed_scale")
        pitch_scale = kwargs.get("pitch_scale")

        # Step 1: Generate audio query
        params = urllib.parse.urlencode({"text": text, "speaker": speaker})
        req = urllib.request.Request(
            f"{self._url}/audio_query?{params}",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            query = json.loads(resp.read())

        # Adjust parameters
        if speed_scale is not None:
            query["speedScale"] = speed_scale
        if pitch_scale is not None:
            query["pitchScale"] = pitch_scale

        # Step 2: Synthesize audio
        req = urllib.request.Request(
            f"{self._url}/synthesis?speaker={speaker}",
            data=json.dumps(query).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            wav_bytes = resp.read()

        return wav_bytes, "wav"
