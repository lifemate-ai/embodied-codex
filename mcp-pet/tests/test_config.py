"""Tests for PET configuration."""

import os

import pytest

from mcp_pet.config import PETConfig, ServerConfig, VisionConfig


class TestVisionConfig:
    def test_defaults(self):
        config = VisionConfig()
        assert config.usb_enabled is True
        assert config.usb_index == 0
        assert config.onvif_host == ""
        assert config.onvif_enabled is False

    def test_onvif_enabled_when_host_set(self):
        config = VisionConfig(onvif_host="192.168.1.100")
        assert config.onvif_enabled is True

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("PET_VISION_USB", "false")
        monkeypatch.setenv("PET_VISION_USB_INDEX", "2")
        monkeypatch.setenv("PET_VISION_ONVIF_HOST", "10.0.0.1")
        monkeypatch.setenv("PET_VISION_ONVIF_USERNAME", "admin")
        monkeypatch.setenv("PET_VISION_ONVIF_PASSWORD", "secret")
        monkeypatch.setenv("PET_VISION_ONVIF_PORT", "8899")
        monkeypatch.setenv("PET_VISION_ONVIF_MOUNT", "ceiling")

        config = VisionConfig.from_env()
        assert config.usb_enabled is False
        assert config.usb_index == 2
        assert config.onvif_host == "10.0.0.1"
        assert config.onvif_username == "admin"
        assert config.onvif_password == "secret"
        assert config.onvif_port == 8899
        assert config.onvif_mount_mode == "ceiling"
        assert config.onvif_enabled is True

    def test_invalid_mount_mode(self, monkeypatch):
        monkeypatch.setenv("PET_VISION_ONVIF_MOUNT", "wall")
        with pytest.raises(ValueError, match="Invalid mount mode"):
            VisionConfig.from_env()


class TestPETConfig:
    def test_defaults(self):
        config = PETConfig()
        assert config.name == "mcp-pet"
        assert config.capture_dir == "/tmp/mcp-pet"
        assert isinstance(config.vision, VisionConfig)

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("PET_CAPTURE_DIR", "/custom/dir")
        monkeypatch.setenv("PET_VISION_USB", "true")
        config = PETConfig.from_env()
        assert config.capture_dir == "/custom/dir"

    def test_server_auto_configures_skyway(self, monkeypatch):
        monkeypatch.setenv("PET_SERVER_PORT", "3000")
        monkeypatch.setenv("PET_CAPTURE_DIR", "/tmp/test-pet")
        config = PETConfig.from_env()
        assert config.server.enabled is True
        assert config.vision.skyway_frame_path == "/tmp/test-pet/latest.jpg"
        assert config.vision.skyway_enabled is True

    def test_server_does_not_override_explicit_skyway(self, monkeypatch):
        monkeypatch.setenv("PET_SERVER_PORT", "3000")
        monkeypatch.setenv("PET_VISION_SKYWAY_FRAME", "/custom/frame.jpg")
        config = PETConfig.from_env()
        assert config.vision.skyway_frame_path == "/custom/frame.jpg"


class TestServerConfig:
    def test_defaults_disabled(self):
        config = ServerConfig()
        assert config.port == 0
        assert config.enabled is False

    def test_enabled_with_port(self):
        config = ServerConfig(port=3000)
        assert config.enabled is True

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("PET_SERVER_PORT", "3000")
        monkeypatch.setenv("PET_SKYWAY_KEY", "abc123")
        monkeypatch.setenv("PET_SKYWAY_ROOM", "my-room")
        monkeypatch.setenv("PET_SAVE_INTERVAL", "5")
        config = ServerConfig.from_env()
        assert config.port == 3000
        assert config.enabled is True
        assert config.skyway_key == "abc123"
        assert config.skyway_room == "my-room"
        assert config.save_interval == 5.0

    def test_from_env_defaults(self):
        config = ServerConfig.from_env()
        assert config.port == 0
        assert config.enabled is False
        assert config.skyway_room == "mcp-pet"
