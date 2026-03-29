from __future__ import annotations

import logging
import os
import platform
from typing import Any, Callable

try:
    from toio.simple import Direction as ToioDirection
    from toio.simple import SimpleCube
except ImportError:  # pragma: no cover - exercised via graceful fallback
    SimpleCube = None
    ToioDirection = None


logger = logging.getLogger(__name__)


def _normalize_theta(theta_deg: float | None) -> float | None:
    if theta_deg is None:
        return None
    value = theta_deg % 360.0
    if value > 180.0:
        value -= 360.0
    return value


def patch_bleak_winrt_raw_adv_data_compat() -> None:
    """
    Bridge toio-py's old WinRT expectation to newer bleak releases.

    toio-py 1.1.0 imports the private symbol `_RawAdvData`, while newer bleak
    exposes the same named tuple as `RawAdvData`.
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


class ToioCubeController:
    """Thin stateful wrapper around toio.py's SimpleCube surface."""

    DEFAULT_SPEED = 80
    DEFAULT_TIMEOUT = 5

    ACTION_STEPS = {
        "move_forward_short": 25,
        "move_forward_long": 50,
        "move_backward_short": 25,
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
        self._last_battery_percent: int | None = None

    def _default_cube_factory(self, **kwargs: Any) -> Any:
        if SimpleCube is None:
            raise RuntimeError(
                "toio-py is not installed. Run `uv sync --extra dev` in toio-mcp."
            )
        patch_bleak_winrt_raw_adv_data_compat()
        return SimpleCube(**kwargs)

    def is_connected(self) -> bool:
        return self._cube is not None

    def connect(self) -> dict[str, Any]:
        if self._cube is None:
            kwargs: dict[str, Any] = {"timeout": self.timeout}
            if self.name:
                kwargs["name"] = self.name
            self._cube = self._cube_factory(**kwargs)
        return self.read_state()

    def disconnect(self) -> dict[str, Any]:
        if self._cube is not None:
            disconnect = getattr(self._cube, "disconnect", None)
            if callable(disconnect):
                disconnect()
            self._cube = None
        return {"ok": True, "connected": False}

    def ensure_connected(self) -> None:
        if not self.is_connected():
            self.connect()

    def read_state(self) -> dict[str, Any]:
        self.ensure_connected()
        return self._read_state_from_cube()

    def perform_action(self, name: str) -> dict[str, Any]:
        self.ensure_connected()
        if name in self.ACTION_STEPS:
            self._apply_discrete_move(name)
        elif name in self.ACTION_TURNS:
            self._cube.turn(self.speed, self.ACTION_TURNS[name])
        elif name == "stop":
            self._cube.stop_motor()
        else:
            raise ValueError(f"Unsupported toio action: {name}")
        return {
            "ok": True,
            "action": name,
            "state": self.read_state(),
        }

    def _apply_discrete_move(self, action_name: str) -> None:
        if self._direction_enum is None:
            raise RuntimeError("toio Direction enum is unavailable; install toio-py.")
        if action_name == "move_backward_short":
            direction = self._direction_enum.Backward
        else:
            direction = self._direction_enum.Forward
        self._cube.move_steps(direction, self.speed, self.ACTION_STEPS[action_name])

    def _read_state_from_cube(self) -> dict[str, Any]:
        position = self._cube.get_current_position()
        orientation = self._cube.get_orientation()
        battery_level = self._read_battery_level()
        touched_card = self._cube.get_touched_card()

        return {
            "connected": True,
            "pose": {
                "x": float(position[0]) if position is not None else None,
                "y": float(position[1]) if position is not None else None,
                "theta_deg": _normalize_theta(float(orientation))
                if orientation is not None
                else None,
            },
            "marker": {
                "kind": "standard_id" if touched_card is not None else "position_id",
                "marker_id": str(touched_card)
                if touched_card is not None
                else (
                    f"{position[0]}:{position[1]}"
                    if position is not None
                    else None
                ),
            },
            "battery": {
                "percent": int(battery_level) if battery_level is not None else None,
            },
        }

    def _read_battery_level(self) -> int | None:
        try:
            battery_level = self._cube.get_battery_level()
        except OSError as exc:
            logger.warning(
                "Failed to read toio battery level; continuing with last known value: %s",
                exc,
            )
            return self._last_battery_percent

        if battery_level is None:
            return self._last_battery_percent

        self._last_battery_percent = int(battery_level)
        return self._last_battery_percent
