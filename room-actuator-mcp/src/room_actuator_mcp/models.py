"""Shared data structures for room-environment backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LightSummary:
    id: str
    name: str
    provider: str
    supports_brightness: bool
    buttons: list[str] = field(default_factory=list)
    signals: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "supports_brightness": self.supports_brightness,
        }
        if self.buttons:
            data["buttons"] = list(self.buttons)
        if self.signals:
            data["signals"] = list(self.signals)
        return data


@dataclass(frozen=True)
class LightStatus:
    id: str
    name: str
    provider: str
    power: str
    brightness_pct: int | None = None
    last_action: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "power": self.power,
        }
        if self.brightness_pct is not None:
            data["brightness_pct"] = self.brightness_pct
        if self.last_action:
            data["last_action"] = self.last_action
        if self.raw:
            data["raw"] = dict(self.raw)
        return data


@dataclass(frozen=True)
class AirconSummary:
    id: str
    name: str
    provider: str
    modes: list[str] = field(default_factory=list)
    temp_unit: str | None = None
    min_temp: int | float | None = None
    max_temp: int | float | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
        }
        if self.modes:
            data["modes"] = list(self.modes)
        if self.temp_unit:
            data["temp_unit"] = self.temp_unit
        if self.min_temp is not None:
            data["min_temp"] = self.min_temp
        if self.max_temp is not None:
            data["max_temp"] = self.max_temp
        if self.capabilities:
            data["capabilities"] = dict(self.capabilities)
        return data


@dataclass(frozen=True)
class AirconStatus:
    id: str
    name: str
    provider: str
    power: str
    mode: str | None = None
    target_temperature: int | float | str | None = None
    temp_unit: str | None = None
    current_temperature: int | float | None = None
    air_volume: str | None = None
    air_direction: str | None = None
    air_direction_h: str | None = None
    updated_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "power": self.power,
        }
        if self.mode is not None:
            data["mode"] = self.mode
        if self.target_temperature is not None:
            data["target_temperature"] = self.target_temperature
        if self.temp_unit:
            data["temp_unit"] = self.temp_unit
        if self.current_temperature is not None:
            data["current_temperature"] = self.current_temperature
        if self.air_volume is not None:
            data["air_volume"] = self.air_volume
        if self.air_direction is not None:
            data["air_direction"] = self.air_direction
        if self.air_direction_h is not None:
            data["air_direction_h"] = self.air_direction_h
        if self.updated_at:
            data["updated_at"] = self.updated_at
        if self.raw:
            data["raw"] = dict(self.raw)
        return data
