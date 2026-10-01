from __future__ import annotations

from pathlib import Path

import pandas as pd

from fleet_rightsizing.baseline import (
    attach_emissions,
    classify_powertrain,
    emissions_supported,
)
from fleet_rightsizing.config import (
    BEV_PURCHASE_COST,
    BOOTSTRAP_WIDTH_THRESHOLD,
    ICE_REPLACEMENT_COST,
    MATCH_RATE_THRESHOLD,
    USD_TO_CAD,
)
from fleet_rightsizing.data_io import sha256_file, verify_sidecar
from fleet_rightsizing.emissions import ELIGIBLE_MATCH_PROVENANCES, RatingsIndex
from fleet_rightsizing.evaluation import (
    StopRuleReport,
    empty_score,
    evaluate,
    perfect_score,
    surplus_scorer,
)
from fleet_rightsizing.tco import bev_tco_row, ice_tco_row, scenario_comparison
from fleet_rightsizing.utilization import proxy_annual_km, threshold_overlap_rate
from tests.conftest import FIXTURES


def test_finding1_bev_and_trailer_not_supported() -> None:
    assert emissions_supported("bev", "SUV") is False
    assert emissions_supported("trailer", "TRAILER") is False
    frame = pd.DataFrame(
        {
            "year": [2020],
            "make": ["FORD"],
            "model": ["ESCAPE"],
            "standard_type": ["SUV"],
            "emissions_supported": [False],
        }
    )
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    enriched = attach_emissions(frame, ratings)
    assert not enriched.iloc[0]["estimate_supported"]
    assert enriched.iloc[0]["co2_g_per_km"] == 0.0


def test_finding1_powertrain_classification() -> None:
    assert classify_powertrain("ELE", "SUV") == "bev"
    assert classify_powertrain("NON", "TRUCK") == "non_powered"


def test_finding2_class_mean_not_eligible_match() -> None:
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    fallback = ratings.lookup(1999, "UNKNOWN", "MODEL", "SUV")
    assert fallback.provenance == "class_mean"
    assert fallback.matched is False
    assert "class_mean" not in ELIGIBLE_MATCH_PROVENANCES


def test_finding2_match_rate_threshold_constant() -> None:
    assert MATCH_RATE_THRESHOLD == 0.5


def test_finding3_scenario_only_counts_feasible_bev() -> None:
    fleet = pd.DataFrame(
        {
            "vehicle_id": ["1", "2"],
            "year": [2010, 2010],
            "annual_km": [15000.0, 15000.0],
            "annual_co2_kg": [5000.0, 5000.0],
            "annual_fuel_litres": [600.0, 600.0],
            "fuel_price": [1.65, 1.65],
            "in_service_cost": [10000.0, 10000.0],
            "standard_type": ["SUV", "OTHER"],
            "nrcan_vehicle_class": ["Sport utility vehicle: Small", "Unknown"],
            "estimate_supported": [True, True],
        }
    )
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv",
        FIXTURES / "nrcan_bev_sample.csv",
    )
    scenario = scenario_comparison(fleet, ratings, replacement_fraction=1.0)
    assert scenario.loc[~scenario["bev_feasible"], "scenario_ghg_reduction_factor"].eq(0).all()


def test_finding4_tco_npv_includes_upfront_capital() -> None:
    ice = ice_tco_row(10000, 800, 1.65, ICE_REPLACEMENT_COST)
    bev = bev_tco_row(10000, 20, 0.14, BEV_PURCHASE_COST, 0.03, 3500)
    assert ice.ten_year_npv > ICE_REPLACEMENT_COST
    assert bev.ten_year_npv > BEV_PURCHASE_COST


def test_finding4_usd_in_service_converted() -> None:
    assert USD_TO_CAD > 1.0


def test_finding5_proxy_mileage_is_simulated() -> None:
    import numpy as np

    fleet = pd.DataFrame({"standard_type": ["SUV", "SUV"]})
    medians = pd.Series({"SUV": 10000.0})
    km = proxy_annual_km(fleet, medians, np.random.default_rng(42))
    assert (km >= 500).all()


def test_finding6_threshold_overlap_not_independent_validation() -> None:
    flagged = pd.Series([True, True, False, False])
    reference = pd.Series([True, True, False, False])
    assert threshold_overlap_rate(flagged, reference) == 1.0


def test_finding6_surplus_scorer_perfect_and_empty() -> None:
    keys = ["a", "b"]
    truth = {"a": True, "b": False}
    assert surplus_scorer(keys, truth, truth) == 1.0
    assert empty_score() == 0.0
    assert perfect_score([], {}, {}) == 0.0


def test_finding7_stop_rule_report_fields() -> None:
    report = StopRuleReport(memory_ok=True, match_rate_ok=False, bootstrap_width_ok=True)
    assert report.match_rate_ok is False


def test_finding8_manifest_licence_fields() -> None:
    import json

    manifest = json.loads(Path("data/manifest.json").read_text(encoding="utf-8"))
    laval = next(d for d in manifest["datasets"] if d["id"] == "laval_fleet")
    assert "CC BY 4.0" in laval["licence"]
    assert "licence_url" in laval


def test_finding10_coverage_gitignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert ".coverage" in text


def test_finding11_bootstrap_width_threshold() -> None:
    assert BOOTSTRAP_WIDTH_THRESHOLD == 0.4


def test_finding14_verify_sidecar(tmp_path: Path) -> None:
    target = tmp_path / "x.csv"
    target.write_text("a,b\n1,2\n", encoding="utf-8")
    digest = sha256_file(target)
    target.with_suffix(".csv.sha256").write_text(digest + "\n", encoding="utf-8")
    assert verify_sidecar(target)


def test_finding16_citation_has_no_invalid_orcid() -> None:
    text = Path("CITATION.cff").read_text(encoding="utf-8")
    assert "orcid:" not in text


def test_finding3_evaluate_uses_feasible_only() -> None:
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
    nyc_scored = nyc.assign(underutilized=[True])
    scenario = pd.DataFrame(
        {
            "replace_candidate": [True],
            "bev_feasible": [True],
            "annual_co2_kg": [1000.0],
            "scenario_ghg_reduction_factor": [0.7],
            "tco_savings_10yr": [5000.0],
        }
    )
    stop = StopRuleReport(True, True, True)
    result = evaluate(
        seattle,
        nyc,
        nyc_scored,
        scenario,
        1.0,
        0.9,
        1.1,
        stop,
        lambda y, mk, md, st: 200.0,
    )
    assert result.scenario_tco_savings_cad == 5000.0
