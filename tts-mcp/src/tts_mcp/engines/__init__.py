"""TTS engine abstraction."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TTSEngine(Protocol):
    """Protocol for TTS engines."""

    @property
    def engine_name(self) -> str:
        """Return the engine name (e.g. 'elevenlabs', 'voicevox')."""
        ...

    def is_available(self) -> bool:
        """Check if the engine is available and configured."""
        ...

    def synthesize(self, text: str, **kwargs: Any) -> tuple[bytes, str]:
        """Synthesize text to audio bytes.

        Returns:
            Tuple of (audio_bytes, audio_format) where format is e.g. 'mp3', 'wav'.
        """
        ...
