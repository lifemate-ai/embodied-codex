from __future__ import annotations

import math
import os
import platform
from abc import ABC, abstractmethod
from typing import Any, Callable

from .schema import ActionCommand, BatteryState, CubeState, MarkerObservation, Pose

try:
    from toio.simple import Direction as ToioDirection
    from toio.simple import SimpleCube
except ImportError:  # pragma: no cover - exercised via graceful fallback
    SimpleCube = None
    ToioDirection = None


def _normalize_theta(theta_deg: float) -> float:
    value = theta_deg % 360.0
    if value > 180.0:
        value -= 360.0
    return value


def _patch_bleak_winrt_raw_adv_data_compat() -> None:
    """
    Bridge toio-py's old WinRT expectation to newer bleak releases.

    toio-py 1.1.0 imports the private symbol `_RawAdvData`, while newer
    bleak exposes the same named tuple as `RawAdvData`.
    """

    if platform.system() != "Windows":
        return

    try:
        from bleak.backends.winrt import scanner as winrt_scanner
    except Exception:
        return

    if hasattr(winrt_scanner, "_RawAdvData"):
        return

    raw_adv_data = getattr(winrt_scanner, "RawAdvData", None)
    if raw_adv_data is not None:
        setattr(winrt_scanner, "_RawAdvData", raw_adv_data)


class BaseController(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_state(self) -> CubeState:
        raise NotImplementedError

    @abstractmethod
    def apply_action(self, action: ActionCommand) -> CubeState:
        raise NotImplementedError


class MockController(BaseController):
    """Simple deterministic controller for dataset plumbing and tests."""

    def __init__(self) -> None:
        self._state = CubeState(
            pose=Pose(x=0.0, y=0.0, theta_deg=0.0),
            marker=MarkerObservation(kind="position_id", marker_id="origin"),
            battery=BatteryState(percent=100),
        )

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def read_state(self) -> CubeState:
        return CubeState.model_validate(self._state.model_dump())

    def apply_action(self, action: ActionCommand) -> CubeState:
        pose = self._state.pose
        theta = pose.theta_deg or 0.0
        x = pose.x or 0.0
        y = pose.y or 0.0

        if action.type in {"forward_short", "forward_long", "backward_short"}:
            distance = {
                "forward_short": 25.0,
                "forward_long": 50.0,
                "backward_short": -25.0,
            }[action.type]
            rad = math.radians(theta)
            x += math.cos(rad) * distance
            y += math.sin(rad) * distance
        elif action.type in {
            "turn_left_small",
            "turn_right_small",
            "turn_left_large",
            "turn_right_large",
        }:
            delta = {
                "turn_left_small": 30.0,
                "turn_right_small": -30.0,
                "turn_left_large": 90.0,
                "turn_right_large": -90.0,
            }[action.type]
            theta = _normalize_theta(theta + delta)
        elif action.type == "move":
            left = action.left or 0
            right = action.right or 0
            duration_ms = action.duration_ms or 0
            average_speed = (left + right) / 2.0
            distance = average_speed * duration_ms / 1000.0
            rad = math.radians(theta)
            x += math.cos(rad) * distance
            y += math.sin(rad) * distance
            theta = _normalize_theta(theta + (right - left) * duration_ms * 0.02)
        elif action.type == "turn":
            theta = _normalize_theta(theta + (action.degrees or 0.0))
        elif action.type == "stop":
            pass
        else:
            raise ValueError(f"Unsupported mock action type: {action.type}")

        marker_id = f"{round(x)}:{round(y)}"
        self._state = CubeState(
            pose=Pose(x=round(x, 3), y=round(y, 3), theta_deg=round(theta, 3)),
            marker=MarkerObservation(kind="position_id", marker_id=marker_id),
            battery=self._state.battery,
        )
        return self.read_state()


class ToioController(BaseController):
    """Real controller backed by toio.py's SimpleCube API when available."""

    DEFAULT_SPEED = 80
    DEFAULT_TIMEOUT = 5
    ACTION_STEPS = {
        "forward_short": 25,
        "forward_long": 50,
        "backward_short": 25,
    }
    ACTION_TURNS = {
        "turn_left_small": 30,
        "turn_right_small": -30,
        "turn_left_large": 90,
        "turn_right_large": -90,
    }

    def __init__(
        self,
        *,
        name: str | None = None,
        timeout: int | None = None,
        speed: int | None = None,
        cube_factory: Callable[..., Any] | None = None,
        direction_enum: Any | None = None,
    ) -> None:
        self.name = name or os.getenv("TOIO_CUBE_NAME")
        self.timeout = timeout or int(os.getenv("TOIO_SCAN_TIMEOUT", str(self.DEFAULT_TIMEOUT)))
        self.speed = speed or int(os.getenv("TOIO_SPEED", str(self.DEFAULT_SPEED)))
        self._cube_factory = cube_factory or self._default_cube_factory
        self._direction_enum = direction_enum or ToioDirection
        self._cube: Any | None = None
        self._last_state = CubeState(
            pose=Pose(),
            marker=MarkerObservation(),
            battery=BatteryState(),
        )

    def _default_cube_factory(self, **kwargs: Any) -> Any:
        if SimpleCube is None:
            raise RuntimeError(
                "toio-py is not installed. Run `uv sync` to install hardware dependencies."
            )
        _patch_bleak_winrt_raw_adv_data_compat()
        return SimpleCube(**kwargs)

    def connect(self) -> None:
        if self._cube is not None:
            return None
        kwargs: dict[str, Any] = {"timeout": self.timeout}
        if self.name:
            kwargs["name"] = self.name
        self._cube = self._cube_factory(**kwargs)
        self._last_state = self._read_state_from_cube()
        return None

    def disconnect(self) -> None:
        if self._cube is None:
            return None
        disconnect = getattr(self._cube, "disconnect", None)
        if callable(disconnect):
            disconnect()
        self._cube = None
        return None

    def read_state(self) -> CubeState:
        self._ensure_connected()
        self._last_state = self._read_state_from_cube()
        return CubeState.model_validate(self._last_state.model_dump())

    def apply_action(self, action: ActionCommand) -> CubeState:
        self._ensure_connected()
        if action.type in self.ACTION_STEPS:
            self._apply_discrete_move(action.type)
        elif action.type in self.ACTION_TURNS:
            self._cube.turn(self.speed, self.ACTION_TURNS[action.type])
        elif action.type == "move":
            duration = max((action.duration_ms or 0) / 1000.0, 0.0)
            self._cube.run_motor(action.left or 0, action.right or 0, duration)
        elif action.type == "turn":
            self._cube.turn(self.speed, round(action.degrees or 0.0))
        elif action.type == "stop":
            self._cube.stop_motor()
        else:
            raise ValueError(f"Unsupported toio action type: {action.type}")
        return self.read_state()

    def _ensure_connected(self) -> None:
        if self._cube is None:
            raise RuntimeError("Cube is not connected. Call connect() first.")

    def _apply_discrete_move(self, action_type: str) -> None:
        if self._direction_enum is None:
            raise RuntimeError("toio Direction enum is unavailable; install toio-py.")
        if action_type == "backward_short":
            direction = self._direction_enum.Backward
        else:
            direction = self._direction_enum.Forward
        self._cube.move_steps(direction, self.speed, self.ACTION_STEPS[action_type])

    def _read_state_from_cube(self) -> CubeState:
        self._ensure_connected()
        position = self._cube.get_current_position()
        orientation = self._cube.get_orientation()
        battery_level = self._cube.get_battery_level()
        touched_card = self._cube.get_touched_card()

        pose = Pose(
            x=float(position[0]) if position is not None else self._last_state.pose.x,
            y=float(position[1]) if position is not None else self._last_state.pose.y,
            theta_deg=(
                _normalize_theta(float(orientation))
                if orientation is not None
                else self._last_state.pose.theta_deg
            ),
        )
        marker = self._marker_from_cube(position=position, touched_card=touched_card)
        battery = BatteryState(
            percent=int(battery_level)
            if battery_level is not None
            else self._last_state.battery.percent
        )
        return CubeState(pose=pose, marker=marker, battery=battery)

    def _marker_from_cube(
        self,
        *,
        position: tuple[int, int] | None,
        touched_card: int | None,
    ) -> MarkerObservation:
        if touched_card is not None:
            return MarkerObservation(kind="standard_id", marker_id=str(touched_card))
        if position is not None:
            return MarkerObservation(kind="position_id", marker_id=f"{position[0]}:{position[1]}")
        return MarkerObservation.model_validate(self._last_state.marker.model_dump())
