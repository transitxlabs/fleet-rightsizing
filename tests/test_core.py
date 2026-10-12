from __future__ import annotations

import numpy as np
import pandas as pd

from fleet_rightsizing.config import SENSITIVITY
from fleet_rightsizing.emissions import RatingsIndex
from fleet_rightsizing.evaluation import (
    bootstrap_spearman,
    empty_score,
    evaluate,
    perfect_score,
    spearman_rho,
    surplus_scorer,
)
from fleet_rightsizing.plan import age_only_flags, build_replacement_plan, composite_score
from fleet_rightsizing.tco import annuity_factor, bev_tco_row, ice_tco_row, scenario_comparison
from fleet_rightsizing.utilization import (
    bootstrap_fleet_ghg,
    measured_underutilized,
    miles_to_km,
    proxy_annual_km,
    proxy_underutilized,
)
from tests.conftest import FIXTURES


def test_ratings_lookup_and_bev() -> None:
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    direct = ratings.lookup(2020, "FORD", "ESCAPE", "SUV")
    assert direct.matched
    assert direct.provenance == "exact"
    fallback = ratings.lookup(1999, "UNKNOWN", "MODEL", "SUV")
    assert fallback.provenance == "class_mean"
    assert not fallback.matched
    bev = ratings.best_bev("Sport utility vehicle: Small", 200.0)
    assert bev is not None


def test_utilization_measured_and_proxy() -> None:
    nyc = pd.DataFrame(
        {
            "standard_type": ["SUV", "SUV", "SEDAN"],
            "miles_per_vehicle": [1000.0, 5000.0, 8000.0],
        }
    )
    measured = measured_underutilized(nyc)
    assert measured["underutilized"].any()
    fleet = pd.DataFrame({"standard_type": ["SUV", "SUV", "SEDAN"]})
    medians = pd.Series({"SUV": miles_to_km(3000), "SEDAN": miles_to_km(6000)})
    rng = np.random.default_rng(42)
    km = proxy_annual_km(fleet, medians, rng)
    proxy = proxy_underutilized(fleet, km)
    assert len(proxy) == 3
    assert "illustrative_underutilized" in proxy.columns
    point, low, high = bootstrap_fleet_ghg(np.array([1.0, 2.0, 3.0]), n_samples=50)
    assert low <= point <= high


def test_tco_and_plan() -> None:
    ice = ice_tco_row(10000, 800, 1.65, 30000)
    bev = bev_tco_row(10000, 20, 0.14, 45000, 0.03, 3500)
    assert ice.ten_year_npv > 0
    assert bev.ten_year_npv > 0
    assert annuity_factor(0.05, 10) > 0
    fleet = pd.DataFrame(
        {
            "vehicle_id": ["1", "2"],
            "year": [2010, 2020],
            "annual_km": [5000.0, 15000.0],
            "annual_co2_kg": [5000.0, 2000.0],
            "annual_fuel_litres": [600.0, 400.0],
            "fuel_price": [1.65, 1.65],
            "in_service_cost": [10000.0, 30000.0],
            "illustrative_underutilized": [True, False],
            "department": ["A", "A"],
            "standard_type": ["SUV", "SEDAN"],
            "nrcan_vehicle_class": [
                "Sport utility vehicle: Small",
                "Sport utility vehicle: Small",
            ],
            "estimate_supported": [True, True],
        }
    )
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    scenario = scenario_comparison(fleet, ratings, replacement_fraction=0.5)
    assert scenario["illustrative_screen_flag"].any()
    plan = build_replacement_plan(fleet, top_n=2)
    assert len(plan) == 2
    assert age_only_flags(fleet).any()
    assert composite_score(fleet).notna().all()


def test_sensitivity_table() -> None:
    from fleet_rightsizing.evaluation import sensitivity_table

    def baseline_fn(**params: float) -> float:
        return params["gasoline_price"]

    table = sensitivity_table(baseline_fn, {"gasoline_price": 1.65})
    assert len(table) == len(SENSITIVITY) * 2


def test_perfect_score_edge_cases() -> None:
    assert perfect_score([], {}, {}) == 0.0
    assert perfect_score(["a"], {"a": 1.0}, {"a": 1.0}) == 1.0
    keys = ["a", "b"]
    truth = {"a": 1.0, "b": 2.0}
    assert perfect_score(keys, {"a": 1.0, "b": 2.0}, truth) == 1.0
    assert empty_score() == 0.0
    assert surplus_scorer(keys, truth, truth) == 1.0
    assert spearman_rho(np.array([1, 2, 3]), np.array([1, 2, 3])) == 1.0
    rho, low, high = bootstrap_spearman(np.arange(5), np.arange(5), n_samples=20)
    assert low <= rho <= high

    from fleet_rightsizing.evaluation import StopRuleReport

    seattle = pd.DataFrame(
        {
            "vehicle_id": ["1"],
            "year": [2010],
            "annual_km": [4000.0],
            "annual_co2_kg": [1000.0],
            "annual_fuel_litres": [500.0],
            "fuel_price": [1.65],
            "in_service_cost": [10000.0],
            "illustrative_underutilized": [True],
            "department": ["A"],
            "standard_type": ["SUV"],
            "estimate_supported": [True],
        }
    )
    nyc = pd.DataFrame(
        {
            "year": [2019],
            "make": ["FORD"],
            "model": ["ESCAPE"],
            "standard_type": ["SUV"],
            "miles_per_vehicle": [1000.0],
        }
    )
    nyc_scored = pd.DataFrame(
        {
            "underutilized": [True],
            "standard_type": ["SUV"],
            "miles_per_vehicle": [1000.0],
        }
    )
    scenario = pd.DataFrame(
        {
            "illustrative_screen_flag": [True],
            "bev_feasible": [True],
            "annual_co2_kg": [1000.0],
            "scenario_ghg_reduction_factor": [0.7],
            "tco_savings_10yr": [5000.0],
        }
    )
    result = evaluate(
        seattle,
        nyc,
        nyc_scored,
        scenario,
        1.0,
        0.9,
        1.1,
        StopRuleReport(True, True, True),
        lambda y, mk, md, st: 200.0,
    )
    assert result.scenario_tco_savings_cad == 5000.0
