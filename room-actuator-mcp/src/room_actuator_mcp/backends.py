"""Room-environment backends for Home Assistant and Nature Remo."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

import requests

from .config import HomeAssistantConfig, NatureRemoConfig
from .models import AirconStatus, AirconSummary, LightStatus, LightSummary

REQUEST_TIMEOUT_SECONDS = 10


class LightingError(RuntimeError):
    """Base error for lighting control failures."""


class UnsupportedOperationError(LightingError):
    """Raised when the current backend cannot perform a requested operation."""


class LightNotFoundError(LightingError):
    """Raised when a requested light cannot be found."""


class SignalNotFoundError(LightingError):
    """Raised when a requested signal cannot be found."""


class AirconNotFoundError(LightingError):
    """Raised when a requested air conditioner cannot be found."""


class LightingBackend(ABC):
    """Abstract base class for room-environment backends."""

    provider_name: str

    @abstractmethod
    def list_lights(self) -> list[dict[str, Any]]:
        """List available light-like actuators."""

    @abstractmethod
    def get_status(self, light_id: str) -> dict[str, Any]:
        """Get current light status."""

    @abstractmethod
    def turn_on(self, light_id: str, brightness_pct: int | None = None) -> dict[str, Any]:
        """Turn light on."""

    @abstractmethod
    def turn_off(self, light_id: str) -> dict[str, Any]:
        """Turn light off."""

    @abstractmethod
    def set_brightness(self, light_id: str, brightness_pct: int) -> dict[str, Any]:
        """Set light brightness percentage."""

    @abstractmethod
    def press_button(self, light_id: str, button: str) -> dict[str, Any]:
        """Press a backend-specific light button."""

    @abstractmethod
    def list_aircons(self) -> list[dict[str, Any]]:
        """List available air conditioners / climate actuators."""

    @abstractmethod
    def get_aircon_status(self, aircon_id: str) -> dict[str, Any]:
        """Get current air conditioner status."""

    @abstractmethod
    def turn_aircon_on(self, aircon_id: str) -> dict[str, Any]:
        """Power an air conditioner on."""

    @abstractmethod
    def turn_aircon_off(self, aircon_id: str) -> dict[str, Any]:
        """Power an air conditioner off."""

    @abstractmethod
    def set_aircon_mode(self, aircon_id: str, mode: str) -> dict[str, Any]:
        """Set the operation mode of an air conditioner."""

    @abstractmethod
    def set_aircon_temperature(
        self,
        aircon_id: str,
        temperature: int | float | str,
    ) -> dict[str, Any]:
        """Set the target temperature of an air conditioner."""

    def list_signals(self, light_id: str) -> list[dict[str, Any]]:
        raise UnsupportedOperationError("Current backend does not expose learned signals.")

    def send_signal(self, signal_id: str) -> dict[str, Any]:
        raise UnsupportedOperationError("Current backend does not support sending learned signals.")


def _normalize_pct(value: int) -> int:
    return max(0, min(int(value), 100))


def _safe_json(response: requests.Response) -> Any:
    body = response.text.strip()
    if not body:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"text": body}


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _coerce_scalar(value: Any) -> Any:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        if re.fullmatch(r"-?\d+", value):
            return int(value)
        if re.fullmatch(r"-?\d+\.\d+", value):
            return float(value)
    return value


def _stringify_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class HomeAssistantLightingBackend(LightingBackend):
    """Room-environment backend backed by the Home Assistant REST API."""

    provider_name = "home_assistant"

    def __init__(
        self,
        config: HomeAssistantConfig,
        session: requests.Session | None = None,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        response = self._session.request(
            method,
            f"{self._config.url}{path}",
            headers={
                "Authorization": f"Bearer {self._config.token}",
                "Content-Type": "application/json",
            },
            json=json_body,
            timeout=REQUEST_TIMEOUT_SECONDS,
            verify=self._config.verify_ssl,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise LightingError(
                f"Home Assistant API request failed ({response.status_code}): {response.text}"
            ) from e
        return _safe_json(response)

    def _supports_brightness(self, state: dict[str, Any]) -> bool:
        attrs = state.get("attributes", {})
        color_modes = attrs.get("supported_color_modes") or []
        if "brightness" in attrs or "brightness_pct" in attrs:
            return True
        return list(color_modes) != ["onoff"] if color_modes else False

    def _status_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        entity_id = state["entity_id"]
        attrs = state.get("attributes", {})
        brightness_pct: int | None = None

        if isinstance(attrs.get("brightness_pct"), (int, float)):
            brightness_pct = _normalize_pct(round(attrs["brightness_pct"]))
        elif isinstance(attrs.get("brightness"), (int, float)):
            brightness_pct = _normalize_pct(round(attrs["brightness"] * 100 / 255))

        status = LightStatus(
            id=entity_id,
            name=attrs.get("friendly_name", entity_id),
            provider=self.provider_name,
            power=state.get("state", "unknown"),
            brightness_pct=brightness_pct,
            raw=state,
        )
        return status.to_dict()

    def list_lights(self) -> list[dict[str, Any]]:
        states = self._request("GET", "/api/states")
        lights: list[dict[str, Any]] = []
        for state in states:
            entity_id = state.get("entity_id", "")
            if not entity_id.startswith("light."):
                continue
            attrs = state.get("attributes", {})
            lights.append(
                LightSummary(
                    id=entity_id,
                    name=attrs.get("friendly_name", entity_id),
                    provider=self.provider_name,
                    supports_brightness=self._supports_brightness(state),
                ).to_dict()
            )
        return sorted(lights, key=lambda item: item["id"])

    def get_status(self, light_id: str) -> dict[str, Any]:
        state = self._request("GET", f"/api/states/{light_id}")
        return self._status_from_state(state)

    def turn_on(self, light_id: str, brightness_pct: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"entity_id": light_id}
        if brightness_pct is not None:
            payload["brightness_pct"] = _normalize_pct(brightness_pct)
        self._request("POST", "/api/services/light/turn_on", json_body=payload)
        return {
            "ok": True,
            "action": "turn_on",
            "light_id": light_id,
            "status": self.get_status(light_id),
        }

    def turn_off(self, light_id: str) -> dict[str, Any]:
        self._request(
            "POST",
            "/api/services/light/turn_off",
            json_body={"entity_id": light_id},
        )
        return {
            "ok": True,
            "action": "turn_off",
            "light_id": light_id,
            "status": self.get_status(light_id),
        }

    def set_brightness(self, light_id: str, brightness_pct: int) -> dict[str, Any]:
        return self.turn_on(light_id, brightness_pct=_normalize_pct(brightness_pct))

    def press_button(self, light_id: str, button: str) -> dict[str, Any]:
        raise UnsupportedOperationError(
            "Home Assistant backend does not expose arbitrary light buttons. "
            "Use light_on/light_off/light_set_brightness instead."
        )

    def _aircon_summary_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        attrs = state.get("attributes", {})
        capabilities: dict[str, Any] = {}
        if attrs.get("fan_modes"):
            capabilities["fan_modes"] = list(attrs["fan_modes"])
        if attrs.get("swing_modes"):
            capabilities["swing_modes"] = list(attrs["swing_modes"])
        if attrs.get("target_temp_step") is not None:
            capabilities["target_temp_step"] = attrs["target_temp_step"]

        return AirconSummary(
            id=state["entity_id"],
            name=attrs.get("friendly_name", state["entity_id"]),
            provider=self.provider_name,
            modes=list(attrs.get("hvac_modes") or []),
            temp_unit=attrs.get("temperature_unit"),
            min_temp=attrs.get("min_temp"),
            max_temp=attrs.get("max_temp"),
            capabilities=capabilities,
        ).to_dict()

    def _aircon_status_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        attrs = state.get("attributes", {})
        mode = attrs.get("hvac_mode") or state.get("state")
        power = "off" if mode == "off" or state.get("state") == "off" else "on"
        return AirconStatus(
            id=state["entity_id"],
            name=attrs.get("friendly_name", state["entity_id"]),
            provider=self.provider_name,
            power=power,
            mode=mode,
            target_temperature=attrs.get("temperature"),
            temp_unit=attrs.get("temperature_unit"),
            current_temperature=attrs.get("current_temperature"),
            air_volume=attrs.get("fan_mode"),
            air_direction=attrs.get("swing_mode"),
            raw=state,
        ).to_dict()

    def list_aircons(self) -> list[dict[str, Any]]:
        states = self._request("GET", "/api/states")
        aircons: list[dict[str, Any]] = []
        for state in states:
            entity_id = state.get("entity_id", "")
            if not entity_id.startswith("climate."):
                continue
            aircons.append(self._aircon_summary_from_state(state))
        return sorted(aircons, key=lambda item: item["id"])

    def get_aircon_status(self, aircon_id: str) -> dict[str, Any]:
        state = self._request("GET", f"/api/states/{aircon_id}")
        return self._aircon_status_from_state(state)

    def turn_aircon_on(self, aircon_id: str) -> dict[str, Any]:
        self._request(
            "POST",
            "/api/services/climate/turn_on",
            json_body={"entity_id": aircon_id},
        )
        return {
            "ok": True,
            "action": "turn_on",
            "aircon_id": aircon_id,
            "status": self.get_aircon_status(aircon_id),
        }

    def turn_aircon_off(self, aircon_id: str) -> dict[str, Any]:
        self._request(
            "POST",
            "/api/services/climate/turn_off",
            json_body={"entity_id": aircon_id},
        )
        return {
            "ok": True,
            "action": "turn_off",
            "aircon_id": aircon_id,
            "status": self.get_aircon_status(aircon_id),
        }

    def set_aircon_mode(self, aircon_id: str, mode: str) -> dict[str, Any]:
        self._request(
            "POST",
            "/api/services/climate/set_hvac_mode",
            json_body={"entity_id": aircon_id, "hvac_mode": mode},
        )
        return {
            "ok": True,
            "action": "set_mode",
            "aircon_id": aircon_id,
            "mode": mode,
            "status": self.get_aircon_status(aircon_id),
        }

    def set_aircon_temperature(
        self,
        aircon_id: str,
        temperature: int | float | str,
    ) -> dict[str, Any]:
        self._request(
            "POST",
            "/api/services/climate/set_temperature",
            json_body={"entity_id": aircon_id, "temperature": temperature},
        )
        return {
            "ok": True,
            "action": "set_temperature",
            "aircon_id": aircon_id,
            "temperature": temperature,
            "status": self.get_aircon_status(aircon_id),
        }


class NatureRemoLightingBackend(LightingBackend):
    """Room-environment backend backed by the Nature Remo cloud API."""

    provider_name = "nature_remo"
    _ON_BUTTON_CANDIDATES = (
        "on",
        "poweron",
        "all",
        "full",
        "max",
        "bright",
        "100",
    )
    _OFF_BUTTON_CANDIDATES = (
        "off",
        "poweroff",
        "sleep",
        "nightoff",
    )

    def __init__(
        self,
        config: NatureRemoConfig,
        session: requests.Session | None = None,
    ) -> None:
        self._config = config
        self._session = session or requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> Any:
        response = self._session.request(
            method,
            f"{self._config.api_base_url}{path}",
            headers={
                "Authorization": f"Bearer {self._config.access_token}",
            },
            data=data,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise LightingError(
                f"Nature Remo API request failed ({response.status_code}): {response.text}"
            ) from e
        return _safe_json(response)

    def _fetch_appliances(self) -> list[dict[str, Any]]:
        appliances = self._request("GET", "/1/appliances")
        if not isinstance(appliances, list):
            raise LightingError("Nature Remo returned an unexpected appliances payload.")
        return appliances

    def _find_appliance(self, light_id: str) -> dict[str, Any]:
        for appliance in self._fetch_appliances():
            if appliance.get("id") == light_id and appliance.get("light") is not None:
                return appliance
        raise LightNotFoundError(f"Nature Remo light appliance not found: {light_id}")

    def _find_aircon(self, aircon_id: str) -> dict[str, Any]:
        for appliance in self._fetch_appliances():
            if appliance.get("id") == aircon_id and appliance.get("type") == "AC":
                return appliance
        raise AirconNotFoundError(f"Nature Remo air conditioner not found: {aircon_id}")

    def _button_names(self, appliance: dict[str, Any]) -> list[str]:
        buttons = appliance.get("light", {}).get("buttons") or []
        return [button.get("name", "") for button in buttons if button.get("name")]

    def _pick_button(self, appliance: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
        buttons = appliance.get("light", {}).get("buttons") or []
        for button in buttons:
            raw_name = button.get("name", "")
            raw_label = button.get("label", "")
            normalized = _normalize_name(raw_name)
            normalized_label = _normalize_name(raw_label)
            if any(
                candidate == normalized or candidate == normalized_label
                for candidate in candidates
            ):
                return raw_name
        return None

    def _status_from_appliance(self, appliance: dict[str, Any]) -> dict[str, Any]:
        light = appliance.get("light", {}) or {}
        state = light.get("state", {}) or {}
        brightness = state.get("brightness")
        brightness_pct: int | None = None
        if isinstance(brightness, str) and brightness.isdigit():
            brightness_pct = _normalize_pct(int(brightness))

        status = LightStatus(
            id=appliance["id"],
            name=appliance.get("nickname", appliance["id"]),
            provider=self.provider_name,
            power=state.get("power", "unknown"),
            brightness_pct=brightness_pct,
            last_action=state.get("last_button"),
            raw=state,
        )
        return status.to_dict()

    def _aircon_modes(self, appliance: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
        aircon = appliance.get("aircon", {}) or {}
        range_info = aircon.get("range", {}) or {}
        modes = range_info.get("modes") or {}
        return modes if isinstance(modes, dict) else {}

    def _aircon_capabilities(self, appliance: dict[str, Any]) -> dict[str, Any]:
        capabilities: dict[str, Any] = {}
        mode_capabilities: dict[str, Any] = {}
        for mode, values in self._aircon_modes(appliance).items():
            if not isinstance(values, dict):
                continue
            mode_capability = {
                "temperatures": [
                    _coerce_scalar(temp) for temp in values.get("temp", []) if temp != ""
                ],
                "air_volumes": [volume for volume in values.get("vol", []) if volume != ""],
                "air_directions": [
                    direction for direction in values.get("dir", []) if direction != ""
                ],
                "air_direction_h": [
                    direction for direction in values.get("dirh", []) if direction != ""
                ],
            }
            mode_capabilities[mode] = mode_capability
        if mode_capabilities:
            capabilities["modes"] = mode_capabilities

        range_info = (appliance.get("aircon", {}) or {}).get("range", {}) or {}
        fixed_buttons = [button for button in range_info.get("fixedButtons", []) if button]
        if fixed_buttons:
            capabilities["fixed_buttons"] = fixed_buttons

        extras = range_info.get("extras") or []
        available_extras = [extra for extra in extras if extra.get("availability") == "available"]
        if available_extras:
            capabilities["extras"] = available_extras
        return capabilities

    def _aircon_summary(self, appliance: dict[str, Any]) -> dict[str, Any]:
        numeric_temps: list[int | float] = []
        for mode in self._aircon_modes(appliance).values():
            for temp in mode.get("temp", []):
                coerced = _coerce_scalar(temp)
                if isinstance(coerced, (int, float)):
                    numeric_temps.append(coerced)
        return AirconSummary(
            id=appliance["id"],
            name=appliance.get("nickname", appliance["id"]),
            provider=self.provider_name,
            modes=sorted(self._aircon_modes(appliance).keys()),
            temp_unit=(appliance.get("aircon", {}) or {}).get("tempUnit"),
            min_temp=min(numeric_temps) if numeric_temps else None,
            max_temp=max(numeric_temps) if numeric_temps else None,
            capabilities=self._aircon_capabilities(appliance),
        ).to_dict()

    def _aircon_status_from_appliance(self, appliance: dict[str, Any]) -> dict[str, Any]:
        settings = appliance.get("settings", {}) or {}
        return AirconStatus(
            id=appliance["id"],
            name=appliance.get("nickname", appliance["id"]),
            provider=self.provider_name,
            power="off" if settings.get("button") == "power-off" else "on",
            mode=settings.get("mode"),
            target_temperature=_coerce_scalar(settings.get("temp")),
            temp_unit=settings.get("temp_unit")
            or (appliance.get("aircon", {}) or {}).get("tempUnit"),
            air_volume=settings.get("vol") or None,
            air_direction=settings.get("dir") or None,
            air_direction_h=settings.get("dirh") or None,
            updated_at=settings.get("updated_at"),
            raw=settings,
        ).to_dict()

    def _resolve_aircon_value(
        self,
        value: Any,
        *,
        allowed: list[str],
        field_name: str,
        explicit: bool,
    ) -> str:
        normalized_allowed = [_stringify_value(item) for item in allowed] or [""]
        raw_value = _stringify_value(value)
        if raw_value in normalized_allowed:
            return raw_value
        if explicit:
            raise UnsupportedOperationError(
                f"{field_name} {raw_value!r} is not supported. Allowed values: {normalized_allowed}"
            )
        if "auto" in normalized_allowed:
            return "auto"
        if "" in normalized_allowed:
            return ""
        return normalized_allowed[0]

    def _aircon_payload(
        self,
        appliance: dict[str, Any],
        *,
        operation_mode: str | None = None,
        temperature: int | float | str | None = None,
        button: str | None = None,
    ) -> dict[str, Any]:
        settings = appliance.get("settings", {}) or {}
        modes = self._aircon_modes(appliance)
        mode = operation_mode or settings.get("mode")
        if not mode:
            raise UnsupportedOperationError("Could not determine the current air conditioner mode.")
        if mode not in modes:
            raise UnsupportedOperationError(
                f"Mode {mode!r} is not supported. Available modes: {sorted(modes)}"
            )

        mode_capabilities = modes[mode]
        resolved_temperature = self._resolve_aircon_value(
            temperature if temperature is not None else settings.get("temp"),
            allowed=list(mode_capabilities.get("temp", [])),
            field_name="temperature",
            explicit=temperature is not None,
        )
        resolved_air_volume = self._resolve_aircon_value(
            settings.get("vol"),
            allowed=list(mode_capabilities.get("vol", [])),
            field_name="air_volume",
            explicit=False,
        )
        resolved_air_direction = self._resolve_aircon_value(
            settings.get("dir"),
            allowed=list(mode_capabilities.get("dir", [])),
            field_name="air_direction",
            explicit=False,
        )
        resolved_air_direction_h = self._resolve_aircon_value(
            settings.get("dirh"),
            allowed=list(mode_capabilities.get("dirh", [])),
            field_name="air_direction_h",
            explicit=False,
        )

        return {
            "operation_mode": mode,
            "temperature": resolved_temperature,
            "temperature_unit": settings.get("temp_unit")
            or (appliance.get("aircon", {}) or {}).get("tempUnit")
            or "",
            "air_volume": resolved_air_volume,
            "air_direction": resolved_air_direction,
            "air_direction_h": resolved_air_direction_h,
            "button": button if button is not None else settings.get("button", ""),
        }

    def _update_aircon(
        self,
        aircon_id: str,
        *,
        operation_mode: str | None = None,
        temperature: int | float | str | None = None,
        button: str | None = None,
    ) -> dict[str, Any]:
        appliance = self._find_aircon(aircon_id)
        payload = self._aircon_payload(
            appliance,
            operation_mode=operation_mode,
            temperature=temperature,
            button=button,
        )
        response = self._request(
            "POST",
            f"/1/appliances/{aircon_id}/aircon_settings",
            data=payload,
        )
        status = self.get_aircon_status(aircon_id)
        if isinstance(response, dict):
            status["raw_response"] = response
        result: dict[str, Any] = {
            "ok": True,
            "aircon_id": aircon_id,
            "status": status,
        }
        if operation_mode is not None:
            result["mode"] = operation_mode
        if temperature is not None:
            result["temperature"] = temperature
        if button is not None:
            result["button"] = button
        return result

    def list_lights(self) -> list[dict[str, Any]]:
        lights: list[dict[str, Any]] = []
        for appliance in self._fetch_appliances():
            if appliance.get("light") is None:
                continue
            signals = appliance.get("signals") or []
            signal_items = [
                {"id": signal["id"], "name": signal.get("name", signal["id"])}
                for signal in signals
                if signal.get("id")
            ]
            lights.append(
                LightSummary(
                    id=appliance["id"],
                    name=appliance.get("nickname", appliance["id"]),
                    provider=self.provider_name,
                    supports_brightness=False,
                    buttons=self._button_names(appliance),
                    signals=signal_items,
                ).to_dict()
            )
        return sorted(lights, key=lambda item: item["id"])

    def get_status(self, light_id: str) -> dict[str, Any]:
        appliance = self._find_appliance(light_id)
        return self._status_from_appliance(appliance)

    def turn_on(self, light_id: str, brightness_pct: int | None = None) -> dict[str, Any]:
        if brightness_pct is not None:
            raise UnsupportedOperationError(
                "Nature Remo backend does not support arbitrary brightness_pct. "
                "Use light_press_button with a learned brightness button instead."
            )
        appliance = self._find_appliance(light_id)
        button = self._pick_button(appliance, self._ON_BUTTON_CANDIDATES)
        if button is None:
            raise UnsupportedOperationError(
                "Could not infer an ON button for this Nature Remo light. "
                "Use light_press_button with one of the listed buttons."
            )
        return self.press_button(light_id, button)

    def turn_off(self, light_id: str) -> dict[str, Any]:
        appliance = self._find_appliance(light_id)
        button = self._pick_button(appliance, self._OFF_BUTTON_CANDIDATES)
        if button is None:
            raise UnsupportedOperationError(
                "Could not infer an OFF button for this Nature Remo light. "
                "Use light_press_button with one of the listed buttons."
            )
        return self.press_button(light_id, button)

    def set_brightness(self, light_id: str, brightness_pct: int) -> dict[str, Any]:
        raise UnsupportedOperationError(
            "Nature Remo backend does not support arbitrary brightness_pct. "
            "Use light_press_button with a learned brightness button instead."
        )

    def press_button(self, light_id: str, button: str) -> dict[str, Any]:
        appliance = self._find_appliance(light_id)
        buttons = self._button_names(appliance)
        if button not in buttons:
            raise UnsupportedOperationError(
                f"Button {button!r} is not available for light {light_id}. "
                f"Available buttons: {buttons}"
            )
        state = self._request(
            "POST",
            f"/1/appliances/{light_id}/light",
            data={"button": button},
        )
        status = self.get_status(light_id)
        if isinstance(state, dict):
            status["raw_response"] = state
        return {
            "ok": True,
            "action": "press_button",
            "light_id": light_id,
            "button": button,
            "status": status,
        }

    def list_signals(self, light_id: str) -> list[dict[str, Any]]:
        appliance = self._find_appliance(light_id)
        signals = appliance.get("signals") or []
        return [
            {"id": signal["id"], "name": signal.get("name", signal["id"])}
            for signal in signals
            if signal.get("id")
        ]

    def send_signal(self, signal_id: str) -> dict[str, Any]:
        if not signal_id.strip():
            raise SignalNotFoundError("signal_id is required")
        self._request(
            "POST",
            f"/1/signals/{signal_id}/send",
            data={},
        )
        return {
            "ok": True,
            "action": "send_signal",
            "signal_id": signal_id,
        }

    def list_aircons(self) -> list[dict[str, Any]]:
        aircons: list[dict[str, Any]] = []
        for appliance in self._fetch_appliances():
            if appliance.get("type") != "AC":
                continue
            aircons.append(self._aircon_summary(appliance))
        return sorted(aircons, key=lambda item: item["id"])

    def get_aircon_status(self, aircon_id: str) -> dict[str, Any]:
        appliance = self._find_aircon(aircon_id)
        return self._aircon_status_from_appliance(appliance)

    def turn_aircon_on(self, aircon_id: str) -> dict[str, Any]:
        result = self._update_aircon(aircon_id, button="")
        result["action"] = "turn_on"
        return result

    def turn_aircon_off(self, aircon_id: str) -> dict[str, Any]:
        result = self._update_aircon(aircon_id, button="power-off")
        result["action"] = "turn_off"
        return result

    def set_aircon_mode(self, aircon_id: str, mode: str) -> dict[str, Any]:
        result = self._update_aircon(aircon_id, operation_mode=mode, button="")
        result["action"] = "set_mode"
        return result

    def set_aircon_temperature(
        self,
        aircon_id: str,
        temperature: int | float | str,
    ) -> dict[str, Any]:
        result = self._update_aircon(aircon_id, temperature=temperature, button="")
        result["action"] = "set_temperature"
        return result
