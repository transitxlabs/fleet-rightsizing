from __future__ import annotations

import pandas as pd

from fleet_rightsizing.baseline import (
    attach_emissions,
    compute_baseline,
    load_nyc_measured,
    load_seattle_fleet,
    map_standard_type,
)
from fleet_rightsizing.config import DIESEL_PRICE, GASOLINE_PRICE
from fleet_rightsizing.emissions import RatingsIndex
from tests.conftest import FIXTURES


def test_map_standard_type() -> None:
    assert map_standard_type("SUV - SML", "small suv") == "SUV"
    assert map_standard_type("TRAILER - EQUIPMENT", "") == "TRAILER"


def test_load_seattle_and_nyc() -> None:
    seattle = load_seattle_fleet(FIXTURES / "seattle_sample.csv")
    assert len(seattle) == 26
    assert "powertrain" in seattle.columns
    nyc = load_nyc_measured(FIXTURES / "nyc_sample.csv")
    assert len(nyc) == 2
    assert nyc.iloc[0]["miles_per_vehicle"] == 2000.0


def test_compute_baseline() -> None:
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    seattle = load_seattle_fleet(FIXTURES / "seattle_sample.csv")
    km = pd.Series([12000.0] * len(seattle))
    scored, summary = compute_baseline(seattle, km, GASOLINE_PRICE, DIESEL_PRICE, ratings)
    assert summary.vehicle_count == 26
    assert summary.annual_co2_tonnes >= 0
    assert summary.nrcan_eligible_match_rate >= 0
    assert "annual_fuel_litres" in scored.columns


def test_attach_emissions() -> None:
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    seattle = load_seattle_fleet(FIXTURES / "seattle_sample.csv")
    enriched = attach_emissions(seattle, ratings)
    assert "match_provenance" in enriched.columns
