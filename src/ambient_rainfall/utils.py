import os
from pprint import pprint
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import time

from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_ENV_PATH)

from ambient_api.ambientapi import AmbientAPI, AmbientWeatherStation
from diskcache import Cache


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}.\n"
            f"Add it to {_ENV_PATH} (creating the file if needed), e.g.:\n"
            f"  {name}=your-{name.lower().replace('_', '-')}-here\n"
            "Get your API key and application key from your account at "
            "https://ambientweather.net (Settings > API Keys)."
        )
    return value


_require_env("AMBIENT_API_KEY"),
_require_env("AMBIENT_APPLICATION_KEY"),
api = AmbientAPI(
    ambient_endpoint="https://ambientweather.net",
    api_key=_require_env("AMBIENT_API_KEY"),
    application_key=_require_env("AMBIENT_APPLICATION_KEY"),
)

DEVICE_CACHE_DIR = Path(os.environ.get("AMBIENT_RAINFALL_CACHE_DIR", ".cache"))
DEVICE_CACHE = Cache(DEVICE_CACHE_DIR)
DEFAULT_DEVICE_CACHE_KEY = "default_device"
DEVICE_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def _default_hour_from_env() -> int:
    """Return the AMBIENT_HOUR environment variable as an int, defaulting to 0."""
    return int(os.environ.get("AMBIENT_HOUR", "0"))


DEFAULT_HOUR = _default_hour_from_env()


def _to_aware_datetime(value: datetime, timezone_name: str | None = None) -> datetime:
    """Return the supplied datetime as an aware datetime in the requested timezone."""
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value

    if timezone_name is None:
        local_dt = datetime.now().astimezone()
        timezone_info = local_dt.tzinfo
    else:
        timezone_info = ZoneInfo(timezone_name)

    return value.replace(tzinfo=timezone_info)


def _ensure_aware_datetime(
    value: datetime, timezone_name: str | None = None
) -> datetime:
    """Ensure the supplied datetime is timezone-aware, attaching local tz if needed."""
    if value.tzinfo is None or value.utcoffset() is None:
        return _to_aware_datetime(value, timezone_name=timezone_name)

    return value


def _ensure_utc_datetime(value: datetime, timezone_name: str | None = None) -> datetime:
    """Ensure the supplied datetime is timezone-aware and convert it to UTC."""
    aware_value = _ensure_aware_datetime(value, timezone_name=timezone_name)
    return aware_value.astimezone(ZoneInfo("UTC"))


def _looks_like_mac_address(value: str) -> bool:
    if not isinstance(value, str):
        return False

    cleaned = value.replace("-", "").replace(":", "")
    return len(cleaned) == 12 and all(ch in "0123456789abcdefABCDEF" for ch in cleaned)


def _cache_device(device):
    DEVICE_CACHE.set(
        DEFAULT_DEVICE_CACHE_KEY,
        {
            "macAddress": device.mac_address,
            "lastData": getattr(device, "last_data", {}),
            "info": getattr(device, "info", {}),
        },
        expire=DEVICE_CACHE_TTL_SECONDS,
    )


def _get_default_device():
    cached_device_data = DEVICE_CACHE.get(DEFAULT_DEVICE_CACHE_KEY)
    if cached_device_data:
        return AmbientWeatherStation(api, cached_device_data)

    # most users will only have one device, so we can just grab the first one
    time.sleep(1)  # avoid hitting the API too quickly
    devices = api.get_devices()
    pprint(devices)
    if not devices or len(devices) == 0:
        raise ValueError("No devices found for the user.")

    device = devices[0]
    _cache_device(device)
    return device
