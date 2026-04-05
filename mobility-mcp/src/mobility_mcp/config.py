"""Configuration for mobility MCP server."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class TuyaCloudConfig:
    """Configuration for Tuya Cloud API connection."""

    def __init__(
        self,
        device_id: str,
        api_key: str,
        api_secret: str,
        api_region: str = "cn",
    ):
        self.device_id = device_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_region = api_region

    @classmethod
    def from_env(cls) -> TuyaCloudConfig:
        """Create config from environment variables."""
        device_id = os.getenv("TUYA_DEVICE_ID", "")
        api_key = os.getenv("TUYA_API_KEY", "")
        api_secret = os.getenv("TUYA_API_SECRET", "")
        api_region = os.getenv("TUYA_API_REGION", "cn")

        if not device_id:
            raise ValueError("TUYA_DEVICE_ID environment variable is required")
        if not api_key:
            raise ValueError("TUYA_API_KEY environment variable is required")
        if not api_secret:
            raise ValueError("TUYA_API_SECRET environment variable is required")

        return cls(
            device_id=device_id,
            api_key=api_key,
            api_secret=api_secret,
            api_region=api_region,
        )


# Direction control Data Point ID (standard Tuya robot vacuum DP)
DIRECTION_DP = int(os.getenv("TUYA_DIRECTION_DP", "4"))

# Duration for timed movements (seconds)
DEFAULT_MOVE_DURATION = float(os.getenv("DEFAULT_MOVE_DURATION", "1.0"))
MAX_MOVE_DURATION = float(os.getenv("MAX_MOVE_DURATION", "10.0"))


def get_max_move_duration() -> float:
    """Get max move duration from TOML > env > default."""
    from ._behavior import get_behavior

    return float(get_behavior("mobility", "max_move_duration", MAX_MOVE_DURATION))


def get_default_move_duration() -> float:
    """Get default move duration from TOML > env > default."""
    from ._behavior import get_behavior

    return float(get_behavior("mobility", "default_move_duration", DEFAULT_MOVE_DURATION))


def get_direction_dp() -> int:
    """Get direction DP from TOML > env > default."""
    from ._behavior import get_behavior

    return int(get_behavior("mobility", "direction_dp", DIRECTION_DP))
