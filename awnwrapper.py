import argparse
import csv
import time
from datetime import datetime, timedelta
from pprint import pprint

from utils import api, _get_default_device, _looks_like_mac_address, _ensure_utc_datetime

from ambient_api.ambientapi import AmbientWeatherStation


def get_data_for_date_range(device: str = None, 
                            start_datetime: datetime = None,
                            end_datetime: datetime = None,
                            timezone_name: str = None,
                            round_start_hour_down: bool = True) -> dict:
    if start_datetime is None or end_datetime is None:
        raise ValueError("Both start_datetime and end_datetime must be provided.")
    if not isinstance(start_datetime, datetime) or not isinstance(end_datetime, datetime):
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
    print(device)

    data = device.get_data(end_date=end_datetime, limit=duration_5min_intervals)
    return data, start_datetime, end_datetime


def get_total_rainfall_for_date_range(device: str = None,
                                      start_datetime: datetime = None,
                                      end_datetime: datetime = None,
                                      timezone_name: str = None,
                                      round_start_hour_down: bool = True,
                                      csv_path: str = None) -> float:
    """Return the sum of hourlyrainin values for the requested date range."""
    data, start_datetime, end_datetime = get_data_for_date_range(
        device=device,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        timezone_name=timezone_name,
        round_start_hour_down=round_start_hour_down,
    )
    print(f"device: {device}, start_datetime: {start_datetime}, end_datetime: {end_datetime}")

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
        print(f"{x:3}: {record.get('date')}, hourlyrainin: {hourly_rain} => total_rainfall: {total_rainfall:.2f}")

    pprint(hourly_rainfall_records)
    print(total_rainfall)
    return total_rainfall


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate total rainfall for a date range.")
    parser.add_argument("--start", dest="start_datetime", type=datetime.fromisoformat,
                        help="Start datetime, ISO format (e.g. 2026-07-22 or 2026-07-22T08:00:00). "
                             "Defaults to yesterday at 8am.")
    parser.add_argument("--end", dest="end_datetime", type=datetime.fromisoformat,
                        help="End datetime, ISO format (e.g. 2026-07-23 or 2026-07-23T08:00:00). "
                             "Defaults to today at 8am.")
    args = parser.parse_args()

    today_at_8am = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    end_datetime = args.end_datetime or today_at_8am
    start_datetime = args.start_datetime or (today_at_8am - timedelta(days=1))

    print(f"Calculating total rainfall between {start_datetime} and {end_datetime}...")
    rainfall = get_total_rainfall_for_date_range(start_datetime=start_datetime, end_datetime=end_datetime)
    print(f"Total rainfall between {start_datetime} and {end_datetime}: {rainfall:.2f} inches")