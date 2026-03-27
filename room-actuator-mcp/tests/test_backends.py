"""Tests for room-actuator backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import requests

from room_actuator_mcp.backends import (
    HomeAssistantLightingBackend,
    NatureRemoLightingBackend,
    UnsupportedOperationError,
)
from room_actuator_mcp.config import HomeAssistantConfig, NatureRemoConfig


@dataclass
class FakeResponse:
    status_code: int = 200
    json_data: Any = None
    text: str = ""

    def __post_init__(self) -> None:
        if not self.text and self.json_data is not None:
            self.text = str(self.json_data)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)

    def json(self) -> Any:
        return self.json_data


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fake responses left")
        return self._responses.pop(0)


def test_home_assistant_list_lights_filters_light_entities():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "entity_id": "light.ceiling",
                        "state": "on",
                        "attributes": {
                            "friendly_name": "Ceiling",
                            "brightness": 128,
                        },
                    },
                    {
                        "entity_id": "switch.not_a_light",
                        "state": "on",
                        "attributes": {"friendly_name": "Not a light"},
                    },
                ]
            )
        ]
    )
    backend = HomeAssistantLightingBackend(
        HomeAssistantConfig(url="http://ha.local:8123", token="token"),
        session=session,
    )

    lights = backend.list_lights()

    assert lights == [
        {
            "id": "light.ceiling",
            "name": "Ceiling",
            "provider": "home_assistant",
            "supports_brightness": True,
        }
    ]


def test_home_assistant_turn_on_uses_light_service_and_returns_status():
    session = FakeSession(
        [
            FakeResponse(json_data=[{"entity_id": "light.ceiling", "state": "on"}]),
            FakeResponse(
                json_data={
                    "entity_id": "light.ceiling",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Ceiling",
                        "brightness": 255,
                    },
                }
            ),
        ]
    )
    backend = HomeAssistantLightingBackend(
        HomeAssistantConfig(url="http://ha.local:8123", token="token"),
        session=session,
    )

    result = backend.turn_on("light.ceiling", brightness_pct=42)

    assert result["ok"] is True
    assert result["status"]["brightness_pct"] == 100
    assert session.calls[0]["url"].endswith("/api/services/light/turn_on")
    assert session.calls[0]["json"]["brightness_pct"] == 42


def test_home_assistant_list_aircons_filters_climate_entities():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "entity_id": "climate.bedroom",
                        "state": "heat",
                        "attributes": {
                            "friendly_name": "Bedroom AC",
                            "hvac_modes": ["off", "heat", "cool", "dry"],
                            "temperature_unit": "C",
                            "min_temp": 16,
                            "max_temp": 30,
                            "fan_modes": ["auto", "low"],
                        },
                    },
                    {
                        "entity_id": "light.ceiling",
                        "state": "on",
                        "attributes": {"friendly_name": "Ceiling"},
                    },
                ]
            )
        ]
    )
    backend = HomeAssistantLightingBackend(
        HomeAssistantConfig(url="http://ha.local:8123", token="token"),
        session=session,
    )

    aircons = backend.list_aircons()

    assert aircons == [
        {
            "id": "climate.bedroom",
            "name": "Bedroom AC",
            "provider": "home_assistant",
            "modes": ["off", "heat", "cool", "dry"],
            "temp_unit": "C",
            "min_temp": 16,
            "max_temp": 30,
            "capabilities": {"fan_modes": ["auto", "low"]},
        }
    ]


def test_home_assistant_set_aircon_temperature_uses_climate_service():
    session = FakeSession(
        [
            FakeResponse(json_data=[{"entity_id": "climate.bedroom", "state": "heat"}]),
            FakeResponse(
                json_data={
                    "entity_id": "climate.bedroom",
                    "state": "heat",
                    "attributes": {
                        "friendly_name": "Bedroom AC",
                        "hvac_mode": "heat",
                        "temperature": 23,
                        "temperature_unit": "C",
                        "current_temperature": 21,
                        "fan_mode": "auto",
                    },
                }
            ),
        ]
    )
    backend = HomeAssistantLightingBackend(
        HomeAssistantConfig(url="http://ha.local:8123", token="token"),
        session=session,
    )

    result = backend.set_aircon_temperature("climate.bedroom", 23)

    assert result["ok"] is True
    assert result["status"]["target_temperature"] == 23
    assert session.calls[0]["url"].endswith("/api/services/climate/set_temperature")
    assert session.calls[0]["json"]["temperature"] == 23


def test_nature_remo_list_lights_exposes_buttons_and_signals():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "id": "appliance-1",
                        "nickname": "Room Light",
                        "light": {
                            "buttons": [
                                {"name": "on", "label": "On", "image": "on"},
                                {"name": "off", "label": "Off", "image": "off"},
                            ],
                            "state": {"power": "on", "brightness": "50", "last_button": "on"},
                        },
                        "signals": [
                            {"id": "sig-1", "name": "night"},
                        ],
                    }
                ]
            )
        ]
    )
    backend = NatureRemoLightingBackend(
        NatureRemoConfig(access_token="token"),
        session=session,
    )

    lights = backend.list_lights()

    assert lights == [
        {
            "id": "appliance-1",
            "name": "Room Light",
            "provider": "nature_remo",
            "supports_brightness": False,
            "buttons": ["on", "off"],
            "signals": [{"id": "sig-1", "name": "night"}],
        }
    ]


def test_nature_remo_press_button_posts_form_and_returns_status():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "id": "appliance-1",
                        "nickname": "Room Light",
                        "light": {
                            "buttons": [
                                {"name": "on", "label": "On", "image": "on"},
                                {"name": "off", "label": "Off", "image": "off"},
                            ],
                            "state": {"power": "off", "brightness": "0", "last_button": "off"},
                        },
                        "signals": [],
                    }
                ]
            ),
            FakeResponse(json_data={"power": "on", "brightness": "100", "last_button": "on"}),
            FakeResponse(
                json_data=[
                    {
                        "id": "appliance-1",
                        "nickname": "Room Light",
                        "light": {
                            "buttons": [
                                {"name": "on", "label": "On", "image": "on"},
                                {"name": "off", "label": "Off", "image": "off"},
                            ],
                            "state": {"power": "on", "brightness": "100", "last_button": "on"},
                        },
                        "signals": [],
                    }
                ]
            ),
        ]
    )
    backend = NatureRemoLightingBackend(
        NatureRemoConfig(access_token="token"),
        session=session,
    )

    result = backend.press_button("appliance-1", "on")

    assert result["ok"] is True
    assert result["status"]["power"] == "on"
    assert session.calls[1]["url"].endswith("/1/appliances/appliance-1/light")
    assert session.calls[1]["data"] == {"button": "on"}


def test_nature_remo_list_aircons_exposes_mode_capabilities():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "id": "aircon-1",
                        "nickname": "Bedroom AC",
                        "type": "AC",
                        "settings": {
                            "temp": "21",
                            "temp_unit": "c",
                            "mode": "warm",
                            "vol": "auto",
                            "dir": "auto",
                            "dirh": "",
                            "button": "power-off",
                            "updated_at": "2026-03-27T00:00:00Z",
                        },
                        "aircon": {
                            "tempUnit": "c",
                            "range": {
                                "modes": {
                                    "cool": {
                                        "temp": ["18", "19", "20"],
                                        "vol": ["1", "auto"],
                                        "dir": ["auto"],
                                        "dirh": [""],
                                    },
                                    "warm": {
                                        "temp": ["20", "21", "22", "23"],
                                        "vol": ["1", "auto"],
                                        "dir": ["auto"],
                                        "dirh": [""],
                                    },
                                },
                                "fixedButtons": ["power-off"],
                            },
                        },
                    }
                ]
            )
        ]
    )
    backend = NatureRemoLightingBackend(
        NatureRemoConfig(access_token="token"),
        session=session,
    )

    aircons = backend.list_aircons()

    assert aircons == [
        {
            "id": "aircon-1",
            "name": "Bedroom AC",
            "provider": "nature_remo",
            "modes": ["cool", "warm"],
            "temp_unit": "c",
            "min_temp": 18,
            "max_temp": 23,
            "capabilities": {
                "modes": {
                    "cool": {
                        "temperatures": [18, 19, 20],
                        "air_volumes": ["1", "auto"],
                        "air_directions": ["auto"],
                        "air_direction_h": [],
                    },
                    "warm": {
                        "temperatures": [20, 21, 22, 23],
                        "air_volumes": ["1", "auto"],
                        "air_directions": ["auto"],
                        "air_direction_h": [],
                    },
                },
                "fixed_buttons": ["power-off"],
            },
        }
    ]


def test_nature_remo_set_aircon_temperature_posts_aircon_settings():
    session = FakeSession(
        [
            FakeResponse(
                json_data=[
                    {
                        "id": "aircon-1",
                        "nickname": "Bedroom AC",
                        "type": "AC",
                        "settings": {
                            "temp": "21",
                            "temp_unit": "c",
                            "mode": "warm",
                            "vol": "auto",
                            "dir": "auto",
                            "dirh": "",
                            "button": "power-off",
                            "updated_at": "2026-03-27T00:00:00Z",
                        },
                        "aircon": {
                            "tempUnit": "c",
                            "range": {
                                "modes": {
                                    "warm": {
                                        "temp": ["20", "21", "22", "23"],
                                        "vol": ["1", "auto"],
                                        "dir": ["auto"],
                                        "dirh": [""],
                                    }
                                }
                            },
                        },
                    }
                ]
            ),
            FakeResponse(
                json_data={
                    "temp": "23",
                    "temp_unit": "c",
                    "mode": "warm",
                    "vol": "auto",
                    "dir": "auto",
                    "dirh": "",
                    "button": "",
                    "updated_at": "2026-03-27T00:05:00Z",
                }
            ),
            FakeResponse(
                json_data=[
                    {
                        "id": "aircon-1",
                        "nickname": "Bedroom AC",
                        "type": "AC",
                        "settings": {
                            "temp": "23",
                            "temp_unit": "c",
                            "mode": "warm",
                            "vol": "auto",
                            "dir": "auto",
                            "dirh": "",
                            "button": "",
                            "updated_at": "2026-03-27T00:05:00Z",
                        },
                        "aircon": {
                            "tempUnit": "c",
                            "range": {
                                "modes": {
                                    "warm": {
                                        "temp": ["20", "21", "22", "23"],
                                        "vol": ["1", "auto"],
                                        "dir": ["auto"],
                                        "dirh": [""],
                                    }
                                }
                            },
                        },
                    }
                ]
            ),
        ]
    )
    backend = NatureRemoLightingBackend(
        NatureRemoConfig(access_token="token"),
        session=session,
    )

    result = backend.set_aircon_temperature("aircon-1", 23)

    assert result["ok"] is True
    assert result["status"]["power"] == "on"
    assert result["status"]["target_temperature"] == 23
    assert session.calls[1]["url"].endswith("/1/appliances/aircon-1/aircon_settings")
    assert session.calls[1]["data"] == {
        "operation_mode": "warm",
        "temperature": "23",
        "temperature_unit": "c",
        "air_volume": "auto",
        "air_direction": "auto",
        "air_direction_h": "",
        "button": "",
    }


def test_nature_remo_set_brightness_is_not_supported():
    backend = NatureRemoLightingBackend(
        NatureRemoConfig(access_token="token"),
        session=FakeSession([]),
    )

    with pytest.raises(UnsupportedOperationError):
        backend.set_brightness("appliance-1", 50)
