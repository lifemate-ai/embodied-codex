"""Configuration for room-actuator MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SUPPORTED_BACKENDS = {"home_assistant", "nature_remo"}


def _parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ServerConfig:
    backend: str
    name: str = "room-actuator-mcp"

    @classmethod
    def from_env(cls) -> ServerConfig:
        backend = os.getenv("ROOM_ACTUATOR_BACKEND", "").strip().lower()
        if not backend:
            backend = os.getenv("LIGHTING_BACKEND", "").strip().lower()
        if not backend:
            if os.getenv("NATURE_REMO_ACCESS_TOKEN", "").strip():
                backend = "nature_remo"
            else:
                backend = "home_assistant"
        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unsupported ROOM_ACTUATOR_BACKEND/LIGHTING_BACKEND={backend!r}. "
                f"Expected one of {sorted(SUPPORTED_BACKENDS)}"
            )
        return cls(backend=backend)


@dataclass(frozen=True)
class HomeAssistantConfig:
    url: str
    token: str
    verify_ssl: bool = True

    @classmethod
    def from_env(cls) -> HomeAssistantConfig:
        url = os.getenv("HOME_ASSISTANT_URL", "").strip().rstrip("/")
        token = os.getenv("HOME_ASSISTANT_TOKEN", "").strip()
        verify_ssl = _parse_bool(os.getenv("HOME_ASSISTANT_VERIFY_SSL"), True)

        if not url:
            raise ValueError("HOME_ASSISTANT_URL environment variable is required")
        if not token:
            raise ValueError("HOME_ASSISTANT_TOKEN environment variable is required")

        return cls(url=url, token=token, verify_ssl=verify_ssl)


@dataclass(frozen=True)
class NatureRemoConfig:
    access_token: str
    api_base_url: str = "https://api.nature.global"

    @classmethod
    def from_env(cls) -> NatureRemoConfig:
        access_token = os.getenv("NATURE_REMO_ACCESS_TOKEN", "").strip()
        api_base_url = (
            os.getenv("NATURE_REMO_API_BASE_URL", "https://api.nature.global").strip().rstrip("/")
        )

        if not access_token:
            raise ValueError("NATURE_REMO_ACCESS_TOKEN environment variable is required")

        return cls(access_token=access_token, api_base_url=api_base_url)
