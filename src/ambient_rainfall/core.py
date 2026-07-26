import argparse
import time
from datetime import datetime, timedelta

from ambient_rainfall.utils import (
    api,
    DEFAULT_HOUR,
    _get_default_device,
    _looks_like_mac_address,
    _ensure_utc_datetime,
)

from ambient_api.ambientapi import AmbientWeatherStation


def get_data_for_date_range(
    device: str = None,
    start_datetime: datetime = None,
    end_datetime: datetime = None,
    timezone_name: str = None,
    round_start_hour_down: bool = True,
) -> dict:
    if start_datetime is None or end_datetime is None:
        raise ValueError("Both start_datetime and end_datetime must be provided.")
    if not isinstance(start_datetime, datetime) or not isinstance(
        end_datetime, datetime
    ):
        raise TypeError("start_datetime and end_datetime must be datetime objects.")
    start_datetime = _ensure_utc_datetime(start_datetime, timezone_name=timezone_name)
    if round_start_hour_down:
        start_datetime = start_datetime.replace(minute=0, second=0, microsecond=0)
    end_datetime = _ensure_utc_datetime(end_datetime, timezone_name=timezone_name)

    if start_datetime >= end_datetime:
        raise ValueError("start_datetime must be earlier than end_datetime.")
    if device is None:
        device = _get_default_device()
    else:
        if not isinstance(device, str):
            raise TypeError("device must be a string MAC address when provided")
        if not _looks_like_mac_address(device):
            raise ValueError("device must appear to be a MAC address")
        device = AmbientWeatherStation(api, {"macAddress": device})
    if device is None:
        raise ValueError("No device found for the user.")
    duration_seconds = (end_datetime - start_datetime).total_seconds()
    duration_minutes = duration_seconds / 60
    duration_5min_intervals = int(duration_minutes / 5)

    time.sleep(1)

    data = device.get_data(end_date=end_datetime, limit=duration_5min_intervals)
    return data, start_datetime, end_datetime


def get_total_rainfall_for_date_range(
    device: str = None,
    start_datetime: datetime = None,
    end_datetime: datetime = None,
    timezone_name: str = None,
    round_start_hour_down: bool = True,
    csv_path: str = None,
) -> float:
    """Return the sum of hourlyrainin values for the requested date range."""
    data, start_datetime, end_datetime = get_data_for_date_range(
        device=device,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        timezone_name=timezone_name,
        round_start_hour_down=round_start_hour_down,
    )

    records = data if isinstance(data, list) else data.get("data", [])
    total_rainfall = 0.0

    if csv_path is None:
        csv_path = f"rainfall_{start_datetime:%Y%m%d%H%M}_{end_datetime:%Y%m%d%H%M}.csv"

    hourly_rainfall_records = {}

    for x, record in enumerate(records):
        hour_str = record.get("date")[:13]
        hourly_rain = record.get("hourlyrainin")
        if hour_str not in hourly_rainfall_records:
            hourly_rainfall_records[hour_str] = 0.0
        hourly_rainfall_records[hour_str] = hourly_rain
        total_rainfall = sum(hourly_rainfall_records.values())

    return total_rainfall


def _parse_datetime_arg(value: str, default_hour: int) -> datetime:
    """Parse an ISO8601 datetime string, filling in default_hour when the string
    doesn't include a time component."""
    parsed = datetime.fromisoformat(value)
    if len(value.strip()) <= 10:  # date-only, e.g. "2026-07-22"
        parsed = parsed.replace(hour=default_hour)
    return parsed


def cli():
    parser = argparse.ArgumentParser(
        description="Calculate total rainfall for a date range."
    )
    parser.add_argument(
        "--start",
        dest="start_datetime",
        type=str,
        help="Start datetime, ISO format (e.g. 2026-07-22 or 2026-07-22T08:00:00). "
        "Defaults to yesterday. If the string omits a time, --hour is used.",
    )
    parser.add_argument(
        "--end",
        dest="end_datetime",
        type=str,
        help="End datetime, ISO format (e.g. 2026-07-23 or 2026-07-23T08:00:00). "
        "Defaults to today. If the string omits a time, --hour is used.",
    )
    parser.add_argument(
        "--device",
        dest="device",
        default=None,
        help="MAC address of the weather station to query. "
        "Defaults to the first station found on the account.",
    )
    parser.add_argument(
        "--hour",
        dest="hour",
        type=int,
        default=DEFAULT_HOUR,
        help="Hour (0-23) used for the yesterday/today defaults when --start/--end "
        "are omitted, and to fill in --start/--end values that omit a time. "
        "Defaults to the AMBIENT_HOUR environment variable, or 0 if unset.",
    )
    args = parser.parse_args()

    today_at_hour = datetime.now().replace(
        hour=args.hour, minute=0, second=0, microsecond=0
    )
    end_datetime = (
        _parse_datetime_arg(args.end_datetime, args.hour)
        if args.end_datetime
        else today_at_hour
    )
    start_datetime = (
        _parse_datetime_arg(args.start_datetime, args.hour)
        if args.start_datetime
        else (today_at_hour - timedelta(days=1))
    )

    delta = end_datetime - start_datetime

    rainfall = get_total_rainfall_for_date_range(
        device=args.device, start_datetime=start_datetime, end_datetime=end_datetime
    )
    print(
        f"Total rainfall for the {delta.days * 24:.0f} hours up to {end_datetime.strftime('%a %b %-d %-I %p %Z')}: {rainfall:.2f} inches"
    )


if __name__ == "__main__":
    cli()