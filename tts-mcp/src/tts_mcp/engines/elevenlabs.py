"""ElevenLabs TTS engine."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for stable TTS generation."""
    parts = re.split(r'(?<=[。！？!?.])\s*', text)
    return [p.strip() for p in parts if p.strip()]


def _collect_audio_bytes(audio: Any) -> bytes:
    if isinstance(audio, (bytes, bytearray)):
        return bytes(audio)
    if hasattr(audio, "__iter__"):
        return b"".join(audio)
    raise TypeError("Unsupported audio payload")


class ElevenLabsEngine:
    """ElevenLabs TTS engine with optional streaming support."""

    def __init__(
        self,
        api_key: str,
        voice_id: str = "uYp2UUDeS74htH10iY2e",
        model_id: str = "eleven_v3",
        output_format: str = "mp3_44100_128",
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_format = output_format
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            from elevenlabs.client import ElevenLabs

            self._client = ElevenLabs(api_key=self._api_key)
        return self._client

    @property
    def engine_name(self) -> str:
        return "elevenlabs"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def synthesize(self, text: str, **kwargs: Any) -> tuple[bytes, str]:
        """Synthesize text to audio bytes.

        Kwargs:
            voice_id: Override voice ID.
            model_id: Override model ID.
            output_format: Override output format.

        Returns:
            Tuple of (audio_bytes, audio_format).
        """
        client = self._get_client()
        voice_id = kwargs.get("voice_id") or self._voice_id
        model_id = kwargs.get("model_id") or self._model_id
        output_format = kwargs.get("output_format") or self._output_format

        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
        )
        audio_bytes = _collect_audio_bytes(audio)
        fmt = output_format.split("_", 1)[0] if output_format else "mp3"
        return audio_bytes, fmt

    def stream(self, text: str, **kwargs: Any) -> Any:
        """Get a streaming audio iterator from ElevenLabs.

        Returns an iterator of audio chunks.
        """
        client = self._get_client()
        voice_id = kwargs.get("voice_id") or self._voice_id
        model_id = kwargs.get("model_id") or self._model_id
        output_format = kwargs.get("output_format") or self._output_format

        return client.text_to_speech.stream(
            text=text,
            voice_id=voice_id,
            model_id=model_id,
            output_format=output_format,
        )

    def stream_sentences(self, text: str, **kwargs: Any) -> list[str]:
        """Split text into sentences for streaming."""
        return _split_sentences(text)
