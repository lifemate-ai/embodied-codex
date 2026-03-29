import sys
import types
from unittest.mock import patch

from toio_mcp.controller import ToioCubeController, patch_bleak_winrt_raw_adv_data_compat


class _FakeDirection:
    Forward = "forward"
    Backward = "backward"


class _FakeCube:
    def __init__(self, **_: object) -> None:
        self.x = 0
        self.y = 0
        self.theta = 0
        self.battery = 97
        self.card = None
        self.connected = True
        self.stopped = False

    def disconnect(self) -> None:
        self.connected = False

    def get_current_position(self) -> tuple[int, int]:
        return (self.x, self.y)

    def get_orientation(self) -> int:
        return self.theta

    def get_battery_level(self) -> int:
        return self.battery

    def get_touched_card(self):
        return self.card

    def move_steps(self, direction: str, speed: int, step: int) -> bool:
        del speed
        if direction == _FakeDirection.Forward:
            self.x += step
        else:
            self.x -= step
        return True

    def turn(self, speed: int, degrees: int) -> bool:
        del speed
        self.theta += degrees
        return True

    def stop_motor(self) -> None:
        self.stopped = True


def test_controller_connects_reads_and_moves() -> None:
    controller = ToioCubeController(
        cube_factory=_FakeCube,
        direction_enum=_FakeDirection,
        speed=90,
    )

    initial = controller.connect()
    assert initial["connected"] is True
    assert initial["pose"]["x"] == 0.0

    post = controller.perform_action("move_forward_long")
    assert post["ok"] is True
    assert post["state"]["pose"]["x"] == 50.0


def test_controller_turns_and_disconnects() -> None:
    controller = ToioCubeController(
        cube_factory=_FakeCube,
        direction_enum=_FakeDirection,
    )
    controller.connect()
    controller.perform_action("turn_left_small")
    state = controller.read_state()
    assert state["pose"]["theta_deg"] == 30.0

    cube = controller._cube
    result = controller.disconnect()
    assert result == {"ok": True, "connected": False}
    assert cube.connected is False


def test_controller_stop_action() -> None:
    controller = ToioCubeController(
        cube_factory=_FakeCube,
        direction_enum=_FakeDirection,
    )
    controller.connect()
    cube = controller._cube

    result = controller.perform_action("stop")

    assert result["ok"] is True
    assert cube.stopped is True


def test_winrt_raw_adv_data_compat_aliases_public_name() -> None:
    scanner = types.ModuleType("bleak.backends.winrt.scanner")

    class RawAdvData:
        pass

    scanner.RawAdvData = RawAdvData
    with patch("toio_mcp.controller.platform.system", return_value="Windows"):
        with patch.dict(sys.modules, {"bleak.backends.winrt.scanner": scanner}, clear=False):
            patch_bleak_winrt_raw_adv_data_compat()

    assert scanner._RawAdvData is RawAdvData
