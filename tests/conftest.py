import os
import tempfile

# ambient_rainfall.utils constructs its AmbientAPI client and diskcache Cache
# at import time, so these must be set before anything imports it.
os.environ.setdefault("AMBIENT_API_KEY", "test-api-key")
os.environ.setdefault("AMBIENT_APPLICATION_KEY", "test-application-key")
os.environ.setdefault(
    "AMBIENT_RAINFALL_CACHE_DIR",
    tempfile.mkdtemp(prefix="ambient-rainfall-test-cache-"),
)

import pytest


@pytest.fixture(autouse=True)
def _clear_device_cache():
    from ambient_rainfall.utils import DEVICE_CACHE

    DEVICE_CACHE.clear()
    yield
    DEVICE_CACHE.clear()
