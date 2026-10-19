"""Named camera configuration and routing without physical hardware."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from wifi_cam_mcp.config import load_camera_inventory
from wifi_cam_mcp.server import CameraMCPServer


@pytest.fixture
def camera_file(tmp_path, monkeypatch):
    path = tmp_path / "cameras.toml"
    path.write_text(
        """default_camera = "inside"
stereo_pair = ["inside", "bedside"]
[cameras.outside]
host = "192.0.2.1"
username_env = "CAM_USER"
password_env = "CAM_PASS"
[cameras.inside]
host = "192.0.2.2"
username_env = "CAM_USER"
password_env = "CAM_PASS"
mount_mode = "ceiling"
[cameras.bedside]
host = "192.0.2.3"
username_env = "CAM_USER"
password_env = "CAM_PASS"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("WIFI_CAMERAS_TOML", str(path))
    monkeypatch.setenv("CAM_USER", "user")
    monkeypatch.setenv("CAM_PASS", "secret")
    return path


def test_named_inventory(camera_file):
    inventory = load_camera_inventory()
    assert list(inventory.cameras) == ["outside", "inside", "bedside"]
    assert inventory.default_camera == "inside"
    assert inventory.stereo_pair == ("inside", "bedside")
    assert inventory.cameras["inside"].mount_mode == "ceiling"
    assert inventory.cameras["outside"].mount_mode == "normal"
    assert inventory.cameras["inside"].use_behavior_mount is False
    assert "secret" not in repr(inventory)


@pytest.mark.parametrize(
    "replacement",
    [
        ('default_camera = "inside"', 'default_camera = "missing"'),
        ("[cameras.outside]", '[cameras."../outside"]'),
        ('mount_mode = "ceiling"', 'mount_mode = "sideways"'),
        ('stereo_pair = ["inside", "bedside"]', 'stereo_pair = ["inside", "inside"]'),
        ('host = "192.0.2.1"', 'host = ""'),
    ],
)
def test_invalid_inventory(camera_file, replacement):
    text = camera_file.read_text(encoding="utf-8")
    camera_file.write_text(text.replace(*replacement), encoding="utf-8")
    with pytest.raises(ValueError):
        load_camera_inventory()


def test_missing_credentials_are_explicit(camera_file, monkeypatch):
    monkeypatch.delenv("CAM_PASS")
    with pytest.raises(ValueError, match="CAM_PASS"):
        load_camera_inventory()


def test_inline_credentials_take_precedence(camera_file, monkeypatch):
    text = camera_file.read_text(encoding="utf-8")
    text = text.replace(
        'username_env = "CAM_USER"',
        'username = "local-user"\nusername_env = "CAM_USER"',
    ).replace(
        'password_env = "CAM_PASS"',
        'password = "local-secret"\npassword_env = "CAM_PASS"',
    )
    camera_file.write_text(text, encoding="utf-8")
    monkeypatch.delenv("CAM_USER")
    monkeypatch.delenv("CAM_PASS")
    inventory = load_camera_inventory()
    assert inventory.cameras["outside"].username == "local-user"
    assert inventory.cameras["outside"].password == "local-secret"
    assert "local-secret" not in repr(inventory)


@pytest.mark.parametrize("value", ['""', "123", "false"])
def test_invalid_inline_password_does_not_fall_back(camera_file, value):
    text = camera_file.read_text(encoding="utf-8")
    camera_file.write_text(
        text.replace('password_env = "CAM_PASS"', f'password = {value}\npassword_env = "CAM_PASS"'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="password"):
        load_camera_inventory()


def test_explicit_missing_file_does_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setenv("WIFI_CAMERAS_TOML", str(tmp_path / "missing.toml"))
    with pytest.raises(FileNotFoundError):
        load_camera_inventory()


@pytest.mark.asyncio
async def test_routing_failures_and_cleanup(camera_file, monkeypatch, tmp_path):
    from wifi_cam_mcp import server as module

    instances = {}

    class FakeCamera:
        def __init__(self, config, capture_dir):
            self.config = config
            self.capture_dir = capture_dir
            self.get_device_info = AsyncMock(return_value={"host": config.host})
            self.disconnect = AsyncMock()
            instances[config.host] = self

        async def connect(self):
            if self.config.host.endswith(".1"):
                raise RuntimeError("rtsp://user:secret@host")

    monkeypatch.setattr(module, "TapoCamera", FakeCamera)
    monkeypatch.setenv("CAPTURE_DIR", str(tmp_path / "captures"))
    server = CameraMCPServer()
    await server.connect_camera()
    tools = {tool.name: tool for tool in await server._list_tools()}
    assert "camera_list" in tools
    assert "camera_capture" in tools
    assert "camera_id" in tools["see"].inputSchema["properties"]
    assert "left_camera_id" in tools["see_both"].inputSchema["properties"]

    listed = json.loads((await server._call_tool("camera_list", {}))[0].text)
    assert listed["default_camera"] == "inside"
    assert listed["cameras"][0]["connected"] is False
    assert "secret" not in json.dumps(listed)
    await server._call_tool("camera_info", {"camera_id": "bedside"})
    instances["192.0.2.3"].get_device_info.assert_awaited_once()
    await server._call_tool("camera_info", {})
    instances["192.0.2.2"].get_device_info.assert_awaited_once()
    error = await server._call_tool("camera_info", {"camera_id": "unknown"})
    assert "unknown" in error[0].text.lower()
    error = await server._call_tool("camera_info", {"camera_id": "outside"})
    assert "offline" in error[0].text.lower()
    assert "secret" not in error[0].text
    assert len({camera.capture_dir for camera in instances.values()}) == 3
    await server.disconnect_camera()
    for camera in instances.values():
        camera.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_concurrent_calls_do_not_change_selected_camera(camera_file, monkeypatch):
    from wifi_cam_mcp import server as module

    class FakeCamera:
        def __init__(self, config, capture_dir):
            self.host = config.host

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def get_device_info(self):
            await asyncio.sleep(0)
            return {"host": self.host}

    monkeypatch.setattr(module, "TapoCamera", FakeCamera)
    server = CameraMCPServer()
    await server.connect_camera()
    results = await asyncio.gather(
        *(
            server._call_tool("camera_info", {"camera_id": name})
            for name in ("outside", "bedside", "inside")
        )
    )
    for result, host in zip(results, ("192.0.2.1", "192.0.2.3", "192.0.2.2")):
        assert host in result[0].text
    await server.disconnect_camera()


def test_legacy_single_and_stereo(monkeypatch, tmp_path):
    from wifi_cam_mcp import config as module

    # Relocate the default project path so a user's local inventory cannot interfere.
    monkeypatch.delenv("WIFI_CAMERAS_TOML", raising=False)
    monkeypatch.setattr(module, "__file__", str(tmp_path / "pkg/src/wifi_cam_mcp/config.py"))
    monkeypatch.setenv("TAPO_CAMERA_HOST", "192.0.2.10")
    monkeypatch.setenv("TAPO_USERNAME", "user")
    monkeypatch.setenv("TAPO_PASSWORD", "secret")
    monkeypatch.delenv("TAPO_RIGHT_CAMERA_HOST", raising=False)
    inventory = load_camera_inventory()
    assert inventory.default_camera == "primary"
    assert inventory.stereo_pair is None
    monkeypatch.setenv("TAPO_RIGHT_CAMERA_HOST", "192.0.2.11")
    inventory = load_camera_inventory()
    assert inventory.stereo_pair == ("primary", "right")
    assert inventory.cameras["right"].password == "secret"


@pytest.mark.asyncio
async def test_pair_aliases_and_continuity(camera_file, monkeypatch):
    from wifi_cam_mcp import server as module
    from wifi_cam_mcp.camera import CaptureResult, Direction, MoveResult

    instances = {}

    class FakeCamera:
        def __init__(self, config, capture_dir):
            self.connect = AsyncMock()
            self.disconnect = AsyncMock()
            self.capture_image = AsyncMock(
                return_value=CaptureResult(
                    image_base64="YWJj",
                    file_path=None,
                    timestamp="now",
                    width=1,
                    height=1,
                )
            )
            self.pan_left = AsyncMock(
                return_value=MoveResult(
                    direction=Direction.LEFT,
                    degrees=30,
                    success=True,
                    message="moved",
                )
            )
            instances[config.host] = self

    monkeypatch.setattr(module, "TapoCamera", FakeCamera)
    server = CameraMCPServer()
    server._record_continuity_event = AsyncMock()
    await server.connect_camera()
    result = await server._call_tool("see_both", {})
    assert sum(item.type == "image" for item in result) == 2
    instances["192.0.2.2"].capture_image.assert_awaited_once()
    instances["192.0.2.3"].capture_image.assert_awaited_once()
    await server._call_tool("camera_pan_left", {"camera_id": "outside"})
    instances["192.0.2.1"].pan_left.assert_awaited_once_with(30)
    assert "camera_id=outside" in server._record_continuity_event.call_args.args[1]
    await server._call_tool(
        "see_both",
        {
            "left_camera_id": "outside",
            "right_camera_id": "inside",
        },
    )
    instances["192.0.2.1"].capture_image.assert_awaited_once()
    error = await server._call_tool(
        "see_both",
        {
            "left_camera_id": "outside",
            "right_camera_id": "outside",
        },
    )
    assert "distinct" in error[0].text
    instances["192.0.2.1"].capture_image.side_effect = ValueError("rtsp://secret@host")
    error = await server._call_tool("see", {"camera_id": "outside"})
    assert "secret" not in error[0].text
    await server.disconnect_camera()


@pytest.mark.asyncio
async def test_named_mount_and_collision_free_capture(monkeypatch, tmp_path):
    import io

    from PIL import Image

    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig

    camera = TapoCamera(
        CameraConfig(
            host="192.0.2.1",
            username="user",
            password="secret",
            use_behavior_mount=False,
        ),
        str(tmp_path),
    )
    monkeypatch.setattr("wifi_cam_mcp.camera.get_behavior", lambda *args: "ceiling")
    assert camera._mount_mode() == "normal"
    image = io.BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="JPEG")
    camera._try_onvif_snapshot = AsyncMock(return_value=image.getvalue())
    captures = await asyncio.gather(
        camera._capture_image_impl(True),
        camera._capture_image_impl(True),
    )
    assert captures[0].file_path != captures[1].file_path
    assert len(list(tmp_path.glob("*.jpg"))) == 2


@pytest.mark.asyncio
async def test_mcp_protocol_stays_available_when_all_cameras_offline(camera_file, monkeypatch):
    from mcp.shared.memory import create_connected_server_and_client_session

    from wifi_cam_mcp import server as module

    gate = asyncio.Event()

    class OfflineCamera:
        def __init__(self, config, capture_dir):
            pass

        async def connect(self):
            await gate.wait()
            raise ConnectionError("unreachable")

        async def disconnect(self):
            pass

    monkeypatch.setattr(module, "TapoCamera", OfflineCamera)
    server = CameraMCPServer()
    async with server.run_context():
        async with create_connected_server_and_client_session(server._server) as client:
            tools = await client.list_tools()
            assert "camera_list" in {tool.name for tool in tools.tools}
            result = await client.call_tool("camera_list", {})
            assert not result.isError
            listed = json.loads(result.content[0].text)
            assert len(listed["cameras"]) == 3
            assert all(not camera["connected"] for camera in listed["cameras"])
            assert all(camera["status"] == "connecting" for camera in listed["cameras"])
            result = await client.call_tool("see", {"camera_id": "inside"})
            assert "connecting" in result.content[0].text
            gate.set()
            await server._connection_task
            result = await client.call_tool("see", {"camera_id": "inside"})
            assert "offline" in result.content[0].text


def test_transport_errors_redact_credentials():
    from wifi_cam_mcp.camera import TapoCamera
    from wifi_cam_mcp.config import CameraConfig

    camera = TapoCamera(
        CameraConfig(
            host="192.0.2.1",
            username="camera-user",
            password="secret@pass",
        )
    )
    message = camera._safe_error(
        "rtsp://camera-user:secret%40pass@192.0.2.1/stream1 failed: secret@pass"
    )
    assert "secret" not in message
    assert "camera-user" not in message
    assert "192.0.2.1" in message


@pytest.mark.asyncio
async def test_shutdown_cleans_up_connecting_cameras(camera_file, monkeypatch):
    from wifi_cam_mcp import server as module

    started = asyncio.Event()
    instances = []

    class ConnectingCamera:
        def __init__(self, config, capture_dir):
            self.disconnect = AsyncMock()
            instances.append(self)

        async def connect(self):
            started.set()
            await asyncio.Event().wait()

    monkeypatch.setattr(module, "TapoCamera", ConnectingCamera)
    server = CameraMCPServer()
    async with server.run_context():
        await started.wait()
    for camera in instances:
        camera.disconnect.assert_awaited_once()
