import sys
from datetime import UTC, datetime, timedelta

import pytest

from ambient_rainfall import core


class FakeDevice:
    def __init__(self, records):
        self._records = records
        self.calls = []

    def get_data(self, end_date, limit):
        self.calls.append({"end_date": end_date, "limit": limit})
        return self._records

    def __str__(self):
        return "FakeDevice"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(core.time, "sleep", lambda seconds: None)


class TestGetDataForDateRange:
    def test_requires_both_datetimes(self):
        with pytest.raises(ValueError):
            core.get_data_for_date_range(
                start_datetime=None, end_datetime=datetime(2026, 7, 23)
            )
        with pytest.raises(ValueError):
            core.get_data_for_date_range(
                start_datetime=datetime(2026, 7, 22), end_datetime=None
            )

    def test_requires_datetime_types(self):
        with pytest.raises(TypeError):
            core.get_data_for_date_range(
                start_datetime="2026-07-22", end_datetime=datetime(2026, 7, 23)
            )

    def test_start_must_precede_end(self):
        same = datetime(2026, 7, 22, 8, tzinfo=UTC)
        with pytest.raises(ValueError):
            core.get_data_for_date_range(start_datetime=same, end_datetime=same)

    def test_device_must_be_string(self):
        with pytest.raises(TypeError):
            core.get_data_for_date_range(
                device=12345,
                start_datetime=datetime(2026, 7, 22, tzinfo=UTC),
                end_datetime=datetime(2026, 7, 23, tzinfo=UTC),
            )

    def test_device_must_look_like_mac_address(self):
        with pytest.raises(ValueError):
            core.get_data_for_date_range(
                device="not-a-mac",
                start_datetime=datetime(2026, 7, 22, tzinfo=UTC),
                end_datetime=datetime(2026, 7, 23, tzinfo=UTC),
            )

    def test_uses_default_device_when_none_given(self, monkeypatch):
        fake_device = FakeDevice(records=[{"foo": "bar"}])
        monkeypatch.setattr(core, "_get_default_device", lambda: fake_device)

        data, start, end = core.get_data_for_date_range(
            start_datetime=datetime(2026, 7, 22, 8, 30, tzinfo=UTC),
            end_datetime=datetime(2026, 7, 23, 8, tzinfo=UTC),
        )

        assert data == [{"foo": "bar"}]
        assert (start.minute, start.second) == (0, 0)  # rounded down
        assert fake_device.calls[0]["end_date"] == end

    def test_round_start_hour_down_false_preserves_minutes(self, monkeypatch):
        fake_device = FakeDevice(records=[])
        monkeypatch.setattr(core, "_get_default_device", lambda: fake_device)

        _, start, _ = core.get_data_for_date_range(
            start_datetime=datetime(2026, 7, 22, 8, 30, tzinfo=UTC),
            end_datetime=datetime(2026, 7, 23, 8, tzinfo=UTC),
            round_start_hour_down=False,
        )

        assert start.minute == 30

    def test_computes_5_minute_interval_limit(self, monkeypatch):
        fake_device = FakeDevice(records=[])
        monkeypatch.setattr(core, "_get_default_device", lambda: fake_device)

        core.get_data_for_date_range(
            start_datetime=datetime(2026, 7, 22, 8, tzinfo=UTC),
            end_datetime=datetime(
                2026, 7, 22, 9, tzinfo=UTC
            ),  # 1 hour == 12 intervals
        )

        assert fake_device.calls[0]["limit"] == 12

    def test_explicit_device_constructs_station(self, monkeypatch):
        fake_device = FakeDevice(records=[{"foo": "bar"}])
        monkeypatch.setattr(
            core, "AmbientWeatherStation", lambda api, device_dict: fake_device
        )

        data, _, _ = core.get_data_for_date_range(
            device="F8:B3:B7:86:72:98",
            start_datetime=datetime(2026, 7, 22, 8, tzinfo=UTC),
            end_datetime=datetime(2026, 7, 23, 8, tzinfo=UTC),
        )

        assert data == [{"foo": "bar"}]


class TestGetTotalRainfallForDateRange:
    def _patch_data(self, monkeypatch, records, is_dict=False):
        start = datetime(2026, 7, 22, 8, tzinfo=UTC)
        end = datetime(2026, 7, 23, 8, tzinfo=UTC)
        payload = {"data": records} if is_dict else records
        monkeypatch.setattr(
            core,
            "get_data_for_date_range",
            lambda **kwargs: (payload, start, end),
        )
        return start, end

    def test_sums_last_reading_per_hour(self, monkeypatch):
        records = [
            {"date": "2026-07-22T08:00:00.000Z", "hourlyrainin": 0.10},
            {"date": "2026-07-22T08:05:00.000Z", "hourlyrainin": 0.15},
            {"date": "2026-07-22T09:00:00.000Z", "hourlyrainin": 0.05},
            {"date": "2026-07-22T09:05:00.000Z", "hourlyrainin": 0.05},
        ]
        self._patch_data(monkeypatch, records)

        total = core.get_total_rainfall_for_date_range(
            start_datetime=datetime(2026, 7, 22, 8, tzinfo=UTC),
            end_datetime=datetime(2026, 7, 23, 8, tzinfo=UTC),
        )

        assert total == pytest.approx(0.20)

    def test_accepts_dict_shaped_payload(self, monkeypatch):
        records = [{"date": "2026-07-22T08:00:00.000Z", "hourlyrainin": 0.30}]
        self._patch_data(monkeypatch, records, is_dict=True)

        total = core.get_total_rainfall_for_date_range(
            start_datetime=datetime(2026, 7, 22, 8, tzinfo=UTC),
            end_datetime=datetime(2026, 7, 23, 8, tzinfo=UTC),
        )

        assert total == pytest.approx(0.30)

    def test_empty_records_yields_zero(self, monkeypatch):
        self._patch_data(monkeypatch, [])

        total = core.get_total_rainfall_for_date_range(
            start_datetime=datetime(2026, 7, 22, 8, tzinfo=UTC),
            end_datetime=datetime(2026, 7, 23, 8, tzinfo=UTC),
        )

        assert total == 0.0


class TestParseDatetimeArg:
    def test_date_only_uses_default_hour(self):
        result = core._parse_datetime_arg("2026-07-22", default_hour=5)
        assert result == datetime(2026, 7, 22, 5, 0, 0)

    def test_full_datetime_keeps_its_own_hour(self):
        result = core._parse_datetime_arg("2026-07-22T08:00:00", default_hour=5)
        assert result == datetime(2026, 7, 22, 8, 0, 0)

    def test_explicit_hour_zero_is_not_overridden(self):
        result = core._parse_datetime_arg("2026-07-22T00", default_hour=5)
        assert result == datetime(2026, 7, 22, 0, 0, 0)


class TestCli:
    def _run_cli(self, monkeypatch, argv, return_value=1.23):
        captured = {}

        def fake_get_total_rainfall(
            device=None, start_datetime=None, end_datetime=None
        ):
            captured["device"] = device
            captured["start_datetime"] = start_datetime
            captured["end_datetime"] = end_datetime
            return return_value

        monkeypatch.setattr(
            core, "get_total_rainfall_for_date_range", fake_get_total_rainfall
        )
        monkeypatch.setattr(sys, "argv", ["ambient-rainfall", *argv])

        core.cli()

        return captured

    def test_defaults_start_end_and_device(self, monkeypatch, capsys):
        captured = self._run_cli(monkeypatch, [])

        assert captured["device"] is None
        assert captured["end_datetime"] - captured["start_datetime"] == timedelta(
            days=1
        )
        assert captured["start_datetime"].hour == core.DEFAULT_HOUR
        assert captured["end_datetime"].hour == core.DEFAULT_HOUR
        assert "1.23 inches" in capsys.readouterr().out

    def test_parses_explicit_arguments(self, monkeypatch):
        captured = self._run_cli(
            monkeypatch,
            [
                "--start", "2026-07-22T08:00:00",
                "--end", "2026-07-23T08:00:00",
                "--device", "F8:B3:B7:86:72:98",
            ],
            return_value=0.5,
        )

        assert captured["device"] == "F8:B3:B7:86:72:98"
        assert captured["start_datetime"] == datetime(2026, 7, 22, 8, 0, 0)
        assert captured["end_datetime"] == datetime(2026, 7, 23, 8, 0, 0)

    def test_hour_option_sets_defaults_when_start_end_omitted(self, monkeypatch):
        captured = self._run_cli(monkeypatch, ["--hour", "5"])

        assert captured["start_datetime"].hour == 5
        assert captured["end_datetime"].hour == 5
        assert captured["end_datetime"] - captured["start_datetime"] == timedelta(
            days=1
        )

    def test_hour_option_fills_in_date_only_start_and_end(self, monkeypatch):
        captured = self._run_cli(
            monkeypatch,
            [
                "--start", "2026-07-22",
                "--end", "2026-07-23",
                "--hour", "5",
            ],
        )

        assert captured["start_datetime"] == datetime(2026, 7, 22, 5, 0, 0)
        assert captured["end_datetime"] == datetime(2026, 7, 23, 5, 0, 0)

    def test_hour_option_does_not_override_explicit_time_in_start_end(
        self, monkeypatch
    ):
        captured = self._run_cli(
            monkeypatch,
            [
                "--start", "2026-07-22T08:00:00",
                "--end", "2026-07-23T08:00:00",
                "--hour", "5",
            ],
        )

        assert captured["start_datetime"] == datetime(2026, 7, 22, 8, 0, 0)
        assert captured["end_datetime"] == datetime(2026, 7, 23, 8, 0, 0)
