from toio_world.controller import ToioController
from toio_world.schema import ActionCommand


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
        self.last_run_motor = None
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
        if direction == _FakeDirection.Forward:
            self.x += step
        else:
            self.x -= step
        return True

    def turn(self, speed: int, degrees: int) -> bool:
        self.theta += degrees
        return True

    def run_motor(self, left: int, right: int, duration: float) -> None:
        self.last_run_motor = (left, right, duration)
        self.x += int((left + right) / 2.0 * duration)

    def stop_motor(self) -> None:
        self.stopped = True


def test_toio_controller_reads_and_updates_pose() -> None:
    controller = ToioController(
        cube_factory=_FakeCube,
        direction_enum=_FakeDirection,
        speed=90,
    )
    controller.connect()
    initial = controller.read_state()
    assert initial.pose.x == 0.0
    post = controller.apply_action(ActionCommand(type="forward_long"))
    assert post.pose.x == 50.0
    assert post.marker.kind == "position_id"
    assert post.battery.percent == 97


def test_toio_controller_supports_motor_and_stop_actions() -> None:
    controller = ToioController(
        cube_factory=_FakeCube,
        direction_enum=_FakeDirection,
    )
    controller.connect()
    cube = controller._cube
    controller.apply_action(ActionCommand(type="move", left=40, right=40, duration_ms=500))
    assert cube.last_run_motor == (40, 40, 0.5)
    controller.apply_action(ActionCommand(type="stop"))
    assert cube.stopped is True


def test_toio_controller_disconnects_cube() -> None:
    controller = ToioController(
        cube_factory=_FakeCube,
        direction_enum=_FakeDirection,
    )
    controller.connect()
    cube = controller._cube
    controller.disconnect()
    assert cube.connected is False
