from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from ambient_api.ambientapi import AmbientWeatherStation

from ambient_rainfall import utils


class FakeDevice:
    def __init__(self, mac_address, last_data=None, info=None):
        self.mac_address = mac_address
        self.last_data = last_data or {}
        self.info = info or {"name": "Test Station"}


class TestDefaultHourFromEnv:
    def test_defaults_to_zero_when_unset(self, monkeypatch):
        monkeypatch.delenv("AMBIENT_HOUR", raising=False)
        assert utils._default_hour_from_env() == 0

    def test_reads_int_from_environment(self, monkeypatch):
        monkeypatch.setenv("AMBIENT_HOUR", "6")
        assert utils._default_hour_from_env() == 6


class TestLooksLikeMacAddress:
    @pytest.mark.parametrize(
        "value",
        [
            "F8:B3:B7:86:72:98",
            "F8-B3-B7-86-72-98",
            "f8b3b7867298",
        ],
    )
    def test_valid_formats(self, value):
        assert utils._looks_like_mac_address(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "not-a-mac",
            "F8:B3:B7:86:72",
            "F8:B3:B7:86:72:98:00",
            "GG:B3:B7:86:72:98",
            12345,
            None,
        ],
    )
    def test_invalid_formats(self, value):
        assert utils._looks_like_mac_address(value) is False


class TestToAwareDatetime:
    def test_returns_aware_value_unchanged(self):
        aware = datetime(2026, 7, 22, 8, tzinfo=timezone.utc)
        assert utils._to_aware_datetime(aware) is aware

    def test_attaches_explicit_timezone(self):
        naive = datetime(2026, 7, 22, 8)
        result = utils._to_aware_datetime(naive, timezone_name="America/New_York")
        assert result.tzinfo == ZoneInfo("America/New_York")
        assert (result.year, result.month, result.day, result.hour) == (2026, 7, 22, 8)


class TestEnsureAwareDatetime:
    def test_passes_through_aware_value(self):
        aware = datetime(2026, 7, 22, 8, tzinfo=timezone.utc)
        assert utils._ensure_aware_datetime(aware) is aware

    def test_attaches_tz_to_naive_value(self):
        naive = datetime(2026, 7, 22, 8)
        result = utils._ensure_aware_datetime(naive, timezone_name="UTC")
        assert result.tzinfo is not None
        assert result.hour == 8


class TestEnsureUtcDatetime:
    def test_converts_eastern_daylight_time_to_utc(self):
        # July: Eastern is UTC-4 (EDT)
        eastern = datetime(2026, 7, 22, 8, tzinfo=ZoneInfo("America/New_York"))
        result = utils._ensure_utc_datetime(eastern)
        assert result.tzinfo == ZoneInfo("UTC")
        assert (result.year, result.month, result.day, result.hour) == (2026, 7, 22, 12)

    def test_naive_value_uses_supplied_timezone_name(self):
        # January: Eastern is UTC-5 (EST)
        naive = datetime(2026, 1, 15, 8)
        result = utils._ensure_utc_datetime(naive, timezone_name="America/New_York")
        assert result.hour == 13


class TestCacheDevice:
    def test_stores_expected_fields(self):
        device = FakeDevice(
            "AA:BB:CC:DD:EE:FF", last_data={"tempf": 70}, info={"name": "Backyard"}
        )

        utils._cache_device(device)

        cached = utils.DEVICE_CACHE.get(utils.DEFAULT_DEVICE_CACHE_KEY)
        assert cached == {
            "macAddress": "AA:BB:CC:DD:EE:FF",
            "lastData": {"tempf": 70},
            "info": {"name": "Backyard"},
        }


class TestGetDefaultDevice:
    def test_fetches_and_caches_first_device_when_uncached(self, monkeypatch):
        device_one = FakeDevice("AA:BB:CC:DD:EE:FF")
        device_two = FakeDevice("11:22:33:44:55:66")
        calls = []

        def fake_get_devices():
            calls.append(1)
            return [device_one, device_two]

        monkeypatch.setattr(utils.api, "get_devices", fake_get_devices)

        result = utils._get_default_device()

        assert result is device_one
        assert len(calls) == 1
        assert (
            utils.DEVICE_CACHE.get(utils.DEFAULT_DEVICE_CACHE_KEY)["macAddress"]
            == "AA:BB:CC:DD:EE:FF"
        )

    def test_uses_cache_on_subsequent_calls(self, monkeypatch):
        device_one = FakeDevice("AA:BB:CC:DD:EE:FF")
        calls = []

        def fake_get_devices():
            calls.append(1)
            return [device_one]

        monkeypatch.setattr(utils.api, "get_devices", fake_get_devices)

        utils._get_default_device()
        second = utils._get_default_device()

        assert len(calls) == 1
        assert isinstance(second, AmbientWeatherStation)
        assert second.mac_address == "AA:BB:CC:DD:EE:FF"

    def test_raises_when_no_devices_found(self, monkeypatch):
        monkeypatch.setattr(utils.api, "get_devices", lambda: [])

        with pytest.raises(ValueError, match="No devices found"):
            utils._get_default_device()
