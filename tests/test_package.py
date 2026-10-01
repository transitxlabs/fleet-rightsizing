from __future__ import annotations

from fleet_rightsizing import __version__
from fleet_rightsizing.config import DATA_URLS, HORIZON_YEARS


def test_version_and_config() -> None:
    assert __version__ == "0.1.0"
    assert "seattle_fleet" in DATA_URLS
    assert HORIZON_YEARS == 10
