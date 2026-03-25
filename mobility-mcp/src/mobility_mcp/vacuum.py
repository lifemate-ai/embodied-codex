"""Tuya robot vacuum control for mobility."""

from __future__ import annotations

import asyncio
import logging

import tinytuya

from .config import TuyaCloudConfig

logger = logging.getLogger(__name__)

# Tuya direction_control standard values
DIRECTION_FORWARD = "forward"
DIRECTION_BACKWARD = "backward"
DIRECTION_LEFT = "turn_left"
DIRECTION_RIGHT = "turn_right"
DIRECTION_STOP = "stop"

VALID_DIRECTIONS = {
    DIRECTION_FORWARD,
    DIRECTION_BACKWARD,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
    DIRECTION_STOP,
}


class VacuumMobilityController:
    """Controls a Tuya robot vacuum for AI mobility via Cloud API."""

    def __init__(self, config: TuyaCloudConfig):
        self._config = config
        self._cloud: tinytuya.Cloud | None = None

    def _ensure_cloud(self) -> tinytuya.Cloud:
        """Get or create cloud connection."""
        if self._cloud is None:
            self._cloud = tinytuya.Cloud(
                apiRegion=self._config.api_region,
                apiKey=self._config.api_key,
                apiSecret=self._config.api_secret,
                apiDeviceID=self._config.device_id,
            )
            logger.info("Connected to Tuya Cloud for device %s", self._config.device_id)
        return self._cloud

    async def _send_direction(self, direction: str) -> dict:
        """Send a direction command to the vacuum via Cloud API."""
        if direction not in VALID_DIRECTIONS:
            raise ValueError(
                f"Invalid direction: {direction}. Must be one of {VALID_DIRECTIONS}"
            )

        cloud = self._ensure_cloud()
        commands = {"commands": [{"code": "direction_control", "value": direction}]}
        result = await asyncio.to_thread(
            cloud.sendcommand, self._config.device_id, commands
        )
        logger.info("Sent direction command: %s -> %s", direction, result)
        return result if isinstance(result, dict) else {}

    async def move_forward(self, duration: float | None = None) -> str:
        """Move forward. If duration specified, stop after that many seconds."""
        await self._send_direction(DIRECTION_FORWARD)
        if duration is not None:
            await asyncio.sleep(duration)
            await self._send_direction(DIRECTION_STOP)
            return f"Moved forward for {duration}s and stopped."
        return "Moving forward. Use stop to halt."

    async def move_backward(self, duration: float | None = None) -> str:
        """Move backward. If duration specified, stop after that many seconds."""
        await self._send_direction(DIRECTION_BACKWARD)
        if duration is not None:
            await asyncio.sleep(duration)
            await self._send_direction(DIRECTION_STOP)
            return f"Moved backward for {duration}s and stopped."
        return "Moving backward. Use stop to halt."

    async def turn_left(self, duration: float | None = None) -> str:
        """Turn left. If duration specified, stop after that many seconds."""
        await self._send_direction(DIRECTION_LEFT)
        if duration is not None:
            await asyncio.sleep(duration)
            await self._send_direction(DIRECTION_STOP)
            return f"Turned left for {duration}s and stopped."
        return "Turning left. Use stop to halt."

    async def turn_right(self, duration: float | None = None) -> str:
        """Turn right. If duration specified, stop after that many seconds."""
        await self._send_direction(DIRECTION_RIGHT)
        if duration is not None:
            await asyncio.sleep(duration)
            await self._send_direction(DIRECTION_STOP)
            return f"Turned right for {duration}s and stopped."
        return "Turning right. Use stop to halt."

    async def stop(self) -> str:
        """Stop all movement immediately."""
        await self._send_direction(DIRECTION_STOP)
        return "Stopped."

    async def start_cleaning(self) -> str:
        """Start smart cleaning mode and leave the charging dock."""
        cloud = self._ensure_cloud()
        commands = {"commands": [{"code": "mode", "value": "smart"}]}
        result = await asyncio.to_thread(
            cloud.sendcommand, self._config.device_id, commands
        )
        logger.info("Sent start cleaning command -> %s", result)
        if isinstance(result, dict) and result.get("success"):
            return "Started smart cleaning. Moving away from dock."
        return f"Start cleaning command sent (result: {result})."

    async def stop_cleaning(self) -> str:
        """Stop cleaning and enter manual-ready standby (power_go=false)."""
        cloud = self._ensure_cloud()
        commands = {"commands": [{"code": "power_go", "value": False}]}
        result = await asyncio.to_thread(
            cloud.sendcommand, self._config.device_id, commands
        )
        logger.info("Sent stop cleaning command -> %s", result)
        if isinstance(result, dict) and result.get("success"):
            return "Cleaning stopped. Now in manual-ready standby — use move_forward/turn_left etc."
        return f"Stop cleaning command sent (result: {result})."

    async def return_to_dock(self) -> str:
        """Send the vacuum back to its charging dock."""
        cloud = self._ensure_cloud()
        # Send mode=chargego to return to charging dock
        commands = {"commands": [{"code": "mode", "value": "chargego"}]}
        result = await asyncio.to_thread(
            cloud.sendcommand, self._config.device_id, commands
        )
        logger.info("Sent return to dock command -> %s", result)
        if isinstance(result, dict) and result.get("success"):
            return "Returning to charging dock."
        return f"Return to dock command sent (result: {result})."

    async def get_status(self) -> dict:
        """Get current device status."""
        cloud = self._ensure_cloud()
        status = await asyncio.to_thread(cloud.getstatus, self._config.device_id)
        logger.info("Device status: %s", status)
        return status if isinstance(status, dict) else {}

    def disconnect(self) -> None:
        """Close cloud connection."""
        self._cloud = None
        logger.info("Disconnected from Tuya Cloud")
