from starlette.testclient import TestClient

from toio_mcp.server import ToioMCPServer


class _FakeController:
    def __init__(self) -> None:
        self.connected = False
        self.calls: list[str] = []

    def is_connected(self) -> bool:
        return self.connected

    def connect(self):
        self.calls.append("connect")
        self.connected = True
        return {
            "connected": True,
            "pose": {"x": 0.0, "y": 0.0, "theta_deg": 0.0},
            "marker": {"kind": "position_id", "marker_id": "0:0"},
            "battery": {"percent": 99},
        }

    def read_state(self):
        self.calls.append("read_state")
        return {
            "connected": True,
            "pose": {"x": 0.0, "y": 0.0, "theta_deg": 0.0},
            "marker": {"kind": "position_id", "marker_id": "0:0"},
            "battery": {"percent": 99},
        }

    def perform_action(self, name: str):
        self.calls.append(name)
        return {
            "ok": True,
            "action": name,
            "state": {
                "connected": True,
                "pose": {"x": 25.0, "y": 0.0, "theta_deg": 0.0},
                "marker": {"kind": "position_id", "marker_id": "25:0"},
                "battery": {"percent": 99},
            },
        }

    def disconnect(self):
        self.calls.append("disconnect")
        self.connected = False
        return {"ok": True, "connected": False}


def test_server_lists_expected_tools() -> None:
    server = ToioMCPServer()
    names = [tool.name for tool in server._tool_definitions()]
    assert names == [
        "connect_cube",
        "read_state",
        "move_forward_short",
        "move_forward_long",
        "move_backward_short",
        "turn_left_small",
        "turn_right_small",
        "turn_left_large",
        "turn_right_large",
        "stop",
        "disconnect_cube",
    ]


def test_server_auto_connects_for_actions() -> None:
    server = ToioMCPServer()
    fake = _FakeController()
    server._controller = fake

    result = server._execute_tool("move_forward_short", {})

    assert result["ok"] is True
    assert fake.calls == ["connect", "move_forward_short"]


def test_server_builds_action_continuity_event() -> None:
    server = ToioMCPServer()

    event = server._continuity_event_for_tool(
        "move_forward_short",
        {},
        {
            "ok": True,
            "state": {
                "pose": {"x": 25.0, "y": 0.0, "theta_deg": 0.0},
                "marker": {"marker_id": "25:0"},
            },
        },
    )

    assert event == (
        "record-action",
        "move_forward_short x=25.0 y=0.0 theta=0.0 marker=25:0",
    )


def test_server_exposes_http_healthcheck() -> None:
    server = ToioMCPServer()
    app = server.create_http_app()

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "path": "/mcp",
        "transport": "streamable-http",
    }


def test_server_http_app_respects_custom_mount_path() -> None:
    server = ToioMCPServer()
    app = server.create_http_app(path="/toio")

    route_paths = {getattr(route, "path", None) for route in app.routes}

    assert "/healthz" in route_paths
    assert "/toio" in route_paths
