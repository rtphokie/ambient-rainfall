# ambient-rainfall

A small wrapper around the [Ambient Weather](https://ambientweather.net) API for
pulling historical station data and calculating total rainfall over a date range.

## Requirements

- Python >= 3.11
- An Ambient Weather account with an API key and application key
  (generate these at [ambientweather.net/account](https://ambientweather.net/account))

## Installation

Install with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

or with pip, into a virtual environment:

```bash
pip install .
```

For development (editable install with test/lint tools):

```bash
uv sync --group dev
# or: pip install -e ".[dev]"
```

Create a `.env` file in the project root with your Ambient Weather credentials:

```dotenv
AMBIENT_API_KEY=your-api-key
AMBIENT_APPLICATION_KEY=your-application-key
```

Optionally set `AMBIENT_RAINFALL_CACHE_DIR` to control where the default-device
cache is stored (defaults to `.cache` in the project root).

Optionally set `AMBIENT_HOUR` to control the hour (0-23) used for the
start/end datetime defaults described below (defaults to `0`).

## Usage

Installing the package exposes a console script:

```bash
ambient-rainfall --start 2026-07-22T08:00:00 --end 2026-07-23T08:00:00
```

`--start` and `--end` accept ISO-formatted datetimes (e.g. `2026-07-22` or
`2026-07-22T08:00:00`). If omitted, `--end` defaults to today and `--start`
defaults to yesterday, both at the hour set by `--hour` (or the `AMBIENT_HOUR`
environment variable, or `0` if neither is set). If `--start`/`--end` are
given but omit a time component (e.g. `2026-07-22`), that same hour is filled
in; an explicit time in the string (e.g. `2026-07-22T08:00:00`) is always
kept as-is.

Each run prints the total rainfall for the requested range and writes a CSV
(`rainfall_<start>_<end>.csv`) with the hourly rainfall values used in the
calculation.

By default, the script uses the first weather station found on your account
(cached for 7 days). Pass a specific station with `--device <mac-address>`,
or the `device` argument when calling the library functions directly.

## Library usage

```python
from datetime import datetime
from ambient_rainfall.core import get_total_rainfall_for_date_range

rainfall = get_total_rainfall_for_date_range(
    start_datetime=datetime(2026, 7, 22, 8),
    end_datetime=datetime(2026, 7, 23, 8),
)
```
