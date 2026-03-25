"""Tests for TTS engines."""

import json
from unittest.mock import MagicMock, patch

from tts_mcp.engines.elevenlabs import ElevenLabsEngine, _split_sentences
from tts_mcp.engines.voicevox import VoicevoxEngine


class TestSplitSentences:
    """Tests for sentence splitting."""

    def test_japanese_sentences(self):
        text = "こんにちは。元気ですか？はい！"
        result = _split_sentences(text)
        assert result == ["こんにちは。", "元気ですか？", "はい！"]

    def test_english_sentences(self):
        text = "Hello world. How are you? Great!"
        result = _split_sentences(text)
        assert result == ["Hello world.", "How are you?", "Great!"]

    def test_single_sentence(self):
        text = "Hello"
        result = _split_sentences(text)
        assert result == ["Hello"]

    def test_empty_string(self):
        result = _split_sentences("")
        assert result == []


class TestElevenLabsEngine:
    """Tests for ElevenLabs engine."""

    def test_engine_name(self):
        engine = ElevenLabsEngine(api_key="test")
        assert engine.engine_name == "elevenlabs"

    def test_is_available_with_key(self):
        engine = ElevenLabsEngine(api_key="test-key")
        assert engine.is_available() is True

    def test_is_available_without_key(self):
        engine = ElevenLabsEngine(api_key="")
        assert engine.is_available() is False

    def test_synthesize_calls_client(self):
        engine = ElevenLabsEngine(api_key="test")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = b"fake-audio"
        engine._client = mock_client

        audio_bytes, fmt = engine.synthesize("hello")
        assert audio_bytes == b"fake-audio"
        assert fmt == "mp3"
        mock_client.text_to_speech.convert.assert_called_once()

    def test_synthesize_with_overrides(self):
        engine = ElevenLabsEngine(api_key="test")
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = b"audio"
        engine._client = mock_client

        engine.synthesize("hello", voice_id="custom", model_id="v2")
        call_kwargs = mock_client.text_to_speech.convert.call_args
        assert call_kwargs.kwargs["voice_id"] == "custom"
        assert call_kwargs.kwargs["model_id"] == "v2"


class TestVoicevoxEngine:
    """Tests for VOICEVOX engine."""

    def test_engine_name(self):
        engine = VoicevoxEngine()
        assert engine.engine_name == "voicevox"

    def test_default_url_and_speaker(self):
        engine = VoicevoxEngine()
        assert engine._url == "http://localhost:50021"
        assert engine._speaker == 3

    def test_url_trailing_slash_stripped(self):
        engine = VoicevoxEngine(url="http://localhost:50021/")
        assert engine._url == "http://localhost:50021"

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_is_available_true(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b'"0.14.0"'
        mock_urlopen.return_value = mock_resp

        engine = VoicevoxEngine()
        assert engine.is_available() is True

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_is_available_false_on_error(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Connection refused")
        engine = VoicevoxEngine()
        assert engine.is_available() is False

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_synthesize(self, mock_urlopen):
        query_resp = MagicMock()
        query_resp.__enter__ = MagicMock(return_value=query_resp)
        query_resp.__exit__ = MagicMock(return_value=False)
        query_resp.read.return_value = json.dumps({"speedScale": 1.0}).encode()

        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"RIFF-fake-wav"

        mock_urlopen.side_effect = [query_resp, synth_resp]

        engine = VoicevoxEngine(speaker=1)
        audio_bytes, fmt = engine.synthesize("テスト")

        assert audio_bytes == b"RIFF-fake-wav"
        assert fmt == "wav"
        assert mock_urlopen.call_count == 2

    @patch("tts_mcp.engines.voicevox.urllib.request.urlopen")
    def test_synthesize_with_speed_scale(self, mock_urlopen):
        query_resp = MagicMock()
        query_resp.__enter__ = MagicMock(return_value=query_resp)
        query_resp.__exit__ = MagicMock(return_value=False)
        query_resp.read.return_value = json.dumps(
            {"speedScale": 1.0, "pitchScale": 0.0}
        ).encode()

        synth_resp = MagicMock()
        synth_resp.__enter__ = MagicMock(return_value=synth_resp)
        synth_resp.__exit__ = MagicMock(return_value=False)
        synth_resp.read.return_value = b"wav-data"

        mock_urlopen.side_effect = [query_resp, synth_resp]

        engine = VoicevoxEngine()
        engine.synthesize("テスト", speed_scale=1.5, pitch_scale=0.1)

        # Check that the synthesis request body has modified speedScale
        synth_call = mock_urlopen.call_args_list[1]
        req = synth_call[0][0]
        body = json.loads(req.data)
        assert body["speedScale"] == 1.5
        assert body["pitchScale"] == 0.1
