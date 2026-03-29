"""Tests for TTS engines."""

import importlib.machinery
import json
from unittest.mock import MagicMock, patch

from tts_mcp import playback as playback_module
from tts_mcp.engines.elevenlabs import ElevenLabsEngine, _split_sentences
from tts_mcp.engines.voicevox import VoicevoxEngine
from tts_mcp.playback import play_audio


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
        with patch(
            "tts_mcp.engines.elevenlabs.importlib.util.find_spec",
            return_value=importlib.machinery.ModuleSpec("elevenlabs", loader=None),
        ):
            assert engine.is_available() is True

    def test_is_available_without_key(self):
        engine = ElevenLabsEngine(api_key="")
        assert engine.is_available() is False

    def test_is_available_false_when_package_missing(self):
        engine = ElevenLabsEngine(api_key="test-key")
        with patch("tts_mcp.engines.elevenlabs.importlib.util.find_spec", return_value=None):
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

    def test_get_client_raises_helpful_error_when_package_missing(self):
        engine = ElevenLabsEngine(api_key="test")
        with patch(
            "tts_mcp.engines.elevenlabs.importlib.import_module",
            side_effect=ModuleNotFoundError("No module named 'elevenlabs'"),
        ):
            try:
                engine._get_client()
                assert False, "Should have raised RuntimeError"
            except RuntimeError as exc:
                assert "uv sync --extra elevenlabs" in str(exc)


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


class TestPlayback:
    """Tests for playback behavior."""

    def test_play_audio_disabled(self):
        result = play_audio(b"audio", "/tmp/test.mp3", "none", None, None)
        assert result == "playback disabled"

    @patch("tts_mcp.playback.subprocess.run")
    @patch("tts_mcp.playback.shutil.which")
    def test_play_audio_pw_play_success(self, mock_which, mock_run):
        def fake_which(name):
            if name == "pw-play":
                return "/usr/bin/pw-play"
            return None

        mock_which.side_effect = fake_which
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = play_audio(b"audio", "/tmp/test.wav", "pw-play", None, None)
        assert result == "played via pw-play"
        mock_run.assert_called_once_with(
            ["/usr/bin/pw-play", "/tmp/test.wav"],
            check=False,
            capture_output=True,
            text=True,
        )

    @patch("tts_mcp.playback.subprocess.run")
    @patch("tts_mcp.playback.shutil.which")
    def test_play_audio_auto_prefers_pw_play(self, mock_which, mock_run):
        def fake_which(name):
            if name == "pw-play":
                return "/usr/bin/pw-play"
            return None

        mock_which.side_effect = fake_which
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        result = play_audio(b"audio", "/tmp/test.wav", "auto", None, None)
        assert result == "played via pw-play"

    @patch("tts_mcp.playback.shutil.which")
    def test_can_stream_with_pipewire_backend(self, mock_which):
        def fake_which(name):
            if name in {"ffmpeg", "pw-play"}:
                return f"/usr/bin/{name}"
            return None

        mock_which.side_effect = fake_which
        assert playback_module.can_stream() is True

    @patch("tts_mcp.playback._stream_with_pw_play")
    @patch("tts_mcp.playback.shutil.which")
    def test_stream_with_local_player_prefers_pw_play_when_mpv_missing(
        self,
        mock_which,
        mock_stream_with_pw_play,
    ):
        def fake_which(name):
            if name == "mpv":
                return None
            if name in {"ffmpeg", "pw-play"}:
                return f"/usr/bin/{name}"
            return None

        mock_which.side_effect = fake_which
        mock_stream_with_pw_play.return_value = (b"audio", "streamed via pw-play")

        result = playback_module.stream_with_local_player(iter([b"chunk"]))
        assert result == (b"audio", "streamed via pw-play")
        mock_stream_with_pw_play.assert_called_once()
