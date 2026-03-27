"""Tests for room-actuator config parsing."""

from __future__ import annotations

from room_actuator_mcp.config import HomeAssistantConfig, NatureRemoConfig, ServerConfig


def test_server_config_defaults_to_home_assistant(monkeypatch):
    monkeypatch.delenv("ROOM_ACTUATOR_BACKEND", raising=False)
    monkeypatch.delenv("LIGHTING_BACKEND", raising=False)
    monkeypatch.delenv("NATURE_REMO_ACCESS_TOKEN", raising=False)
    config = ServerConfig.from_env()
    assert config.backend == "home_assistant"


def test_server_config_prefers_nature_remo_when_token_is_present(monkeypatch):
    monkeypatch.delenv("ROOM_ACTUATOR_BACKEND", raising=False)
    monkeypatch.delenv("LIGHTING_BACKEND", raising=False)
    monkeypatch.setenv("NATURE_REMO_ACCESS_TOKEN", "token")

    config = ServerConfig.from_env()

    assert config.backend == "nature_remo"


def test_server_config_prefers_room_actuator_backend_env(monkeypatch):
    monkeypatch.setenv("ROOM_ACTUATOR_BACKEND", "nature_remo")
    monkeypatch.setenv("LIGHTING_BACKEND", "home_assistant")

    config = ServerConfig.from_env()

    assert config.backend == "nature_remo"


def test_home_assistant_config_from_env(monkeypatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://ha.local:8123/")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("HOME_ASSISTANT_VERIFY_SSL", "false")

    config = HomeAssistantConfig.from_env()

    assert config.url == "http://ha.local:8123"
    assert config.token == "secret"
    assert config.verify_ssl is False


def test_nature_remo_config_from_env(monkeypatch):
    monkeypatch.setenv("NATURE_REMO_ACCESS_TOKEN", "token")
    monkeypatch.setenv("NATURE_REMO_API_BASE_URL", "https://api.nature.global/")

    config = NatureRemoConfig.from_env()

    assert config.access_token == "token"
    assert config.api_base_url == "https://api.nature.global"
