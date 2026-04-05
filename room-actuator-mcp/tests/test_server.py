"""Tests for room-actuator MCP server."""

from room_actuator_mcp.server import LightingMCPServer


def test_server_creation(monkeypatch):
    monkeypatch.setenv("ROOM_ACTUATOR_BACKEND", "home_assistant")
    server = LightingMCPServer()
    assert server._server is not None
    assert server._backend is None


def test_light_action_continuity_event(monkeypatch):
    monkeypatch.setenv("ROOM_ACTUATOR_BACKEND", "home_assistant")
    server = LightingMCPServer()

    event = server._continuity_event_for_tool(
        "light_press_button",
        {"light_id": "bedroom-light", "button": "night"},
        {
            "ok": True,
            "button": "night",
            "status": {
                "id": "bedroom-light",
                "power": "on",
                "brightness_pct": 18,
            },
        },
    )

    assert event == (
        "record-action",
        "light_press_button id=bedroom-light button=night power=on brightness=18",
    )


def test_aircon_observation_continuity_event(monkeypatch):
    monkeypatch.setenv("ROOM_ACTUATOR_BACKEND", "nature_remo")
    server = LightingMCPServer()

    event = server._continuity_event_for_tool(
        "aircon_status",
        {"aircon_id": "bedroom-ac"},
        {
            "id": "bedroom-ac",
            "power": "on",
            "mode": "warm",
            "target_temperature": 21,
            "temp_unit": "C",
        },
    )

    assert event == (
        "record-observation",
        "aircon_status id=bedroom-ac power=on mode=warm target=21C",
    )


def test_room_sensor_observation_continuity_event(monkeypatch):
    monkeypatch.setenv("ROOM_ACTUATOR_BACKEND", "nature_remo")
    server = LightingMCPServer()

    event = server._continuity_event_for_tool(
        "room_sensor_status",
        {"sensor_id": "remo-bedroom"},
        {
            "id": "remo-bedroom",
            "temperature_c": 26.8,
            "humidity_pct": 34,
            "illuminance": 87,
            "motion": True,
        },
    )

    assert event == (
        "record-observation",
        "room_sensor_status id=remo-bedroom temp=26.8C humidity=34% illuminance=87 motion=on",
    )
