"""Publication R2 regressions; each numbered test was observed failing on db7cb2d."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from fleet_rightsizing.baseline import compute_baseline, load_seattle_fleet
from fleet_rightsizing.emissions import STANDARD_TO_NRCAN_CLASS, RatingsIndex
from fleet_rightsizing.federal_check import federal_fleet_factor_check
from fleet_rightsizing.pipeline import run_pipeline
from fleet_rightsizing.tco import scenario_comparison
from fleet_rightsizing.utilization import proxy_annual_km
from tests.conftest import FIXTURES


@pytest.fixture(scope="module")
def ratings():
    return RatingsIndex.from_files(FIXTURES / "nrcan_sample.csv", FIXTURES / "nrcan_bev_sample.csv")


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    root = tmp_path_factory.mktemp("r3")
    paths = {
        "seattle_fleet": FIXTURES / "seattle_sample.csv",
        "nyc_efficiency": FIXTURES / "nyc_sample.csv",
        "laval_fleet": FIXTURES / "laval_sample.csv",
        "nrcan_ratings": FIXTURES / "nrcan_sample.csv",
        "nrcan_bev": FIXTURES / "nrcan_bev_sample.csv",
        "federal_fleet_fuel": FIXTURES / "federal_sample.csv",
    }
    with patch("fleet_rightsizing.pipeline.ensure_datasets", return_value=paths):
        payload = run_pipeline(results_dir=root / "results", figures_dir=root / "figures")
    return root, payload


def test_r2_01_specialists_excluded(ratings):
    fleet = load_seattle_fleet(FIXTURES / "seattle_specialist.csv")
    assert set(fleet.vehicle_id) == {"31512", "86390", "33083"}
    assert not fleet.emissions_supported.any()
    scored, _ = compute_baseline(fleet, pd.Series([12000.0] * 3), 1.65, 1.75, ratings)
    assert scored.annual_co2_kg.eq(0).all()


def test_r2_02_current_docs_reconcile(release):
    root, payload = release
    assert (root / "docs/results.md").read_text() == (root / "RESULTS.md").read_text()
    assert "6,921" not in Path("docs/technical-report.md").read_text()
    assert payload["stop_rules_passed"] is False


def test_r2_03_source_classes_and_factor_uncertainty(ratings):
    assert STANDARD_TO_NRCAN_CLASS["TRUCK"] == "Pickup truck: Standard"
    fleet = pd.DataFrame({"standard_type": ["TRUCK"]})
    medians = pd.Series({"PICKUP": 10000.0, "SEDAN": 1000.0})
    km = proxy_annual_km(fleet, medians, np.random.default_rng(42))
    assert km.iloc[0] > 9000
    frame = load_seattle_fleet(FIXTURES / "seattle_sample.csv")
    scored, _ = compute_baseline(frame, pd.Series([12000.0] * len(frame)), 1.65, 1.75, ratings)
    assert scored.factor_uncertainty.str.contains("variant").any()


def test_r2_04_uncertainty_scope(release):
    root, payload = release
    assert payload["uncertainty"]["kind"] == "conditional_row_bootstrap"
    bounds = payload["uncertainty"]["assumption_range_tonnes"]
    assert bounds[0] < payload["baseline"]["annual_co2_tonnes"] < bounds[1]
    assert "flags do not establish surplus" in (root / "RESULTS.md").read_text()


def test_r2_05_amendment_and_withheld_recommendations(release):
    root, payload = release
    amendment = Path("docs/AMENDMENT_2026-10-01.md").read_text()
    assert "analysis specification" in amendment
    assert "engine hours" in amendment
    assert payload["recommendations_status"] == "withheld"
    assert not (root / "results/replacement_plan.csv").exists()


def test_r2_06_federal_fiscal_year_scope():
    check = federal_fleet_factor_check(FIXTURES / "federal_sample.csv")
    assert check["status"] == "ok"
    assert check["latest_year"] == 2024
    assert check["latest_year_rows"] == 3
    assert check["compatible_rows"] == 2
    assert check["fuels"]["gasoline"]["kg_co2e_per_l"] == pytest.approx(2.3)
    assert check["fuels"]["diesel"]["kg_co2e_per_l"] == pytest.approx(2.7)


def test_r2_07_economic_sensitivity_and_tailpipe(release):
    root, _ = release
    sensitivity = pd.read_csv(root / "results/sensitivity.csv")
    for _, group in sensitivity.groupby("parameter"):
        assert group.hypothetical_npv_delta_cad.nunique() == 2
    assert sensitivity.hypothetical_tailpipe_reduction_pct.eq(100).all()


def test_r2_08_disjoint_exclusions(ratings):
    fleet = load_seattle_fleet(FIXTURES / "seattle_sample.csv")
    fleet.loc[0, ["powertrain", "emissions_supported"]] = ["bev", False]
    _, summary = compute_baseline(fleet, pd.Series([12000.0] * len(fleet)), 1.65, 1.75, ratings)
    total = sum(
        [
            summary.excluded_bev_count,
            summary.excluded_non_powered_count,
            summary.excluded_trailer_count,
            summary.excluded_unsupported_count,
        ]
    )
    assert total == summary.vehicle_count - summary.supported_vehicle_count


def test_r2_09_licence_and_portable_attribution(release):
    root, _ = release
    assert "Derived results and code are Apache" not in Path("README.md").read_text()
    assert "https://creativecommons.org/licenses/by/4.0/" in Path("ATTRIBUTION.md").read_text()
    assert (root / "results/ATTRIBUTION.md").exists()
    assert "City of Seattle" in (root / "results/report.html").read_text()


def test_r2_10_current_tree_hygiene():
    assert chr(0x2014) not in Path("REPORT.md").read_text()


def test_r2_11_release_provenance(release):
    _, payload = release
    assert "inputs" in payload
    for item in payload["inputs"].values():
        assert len(item["sha256"]) == 64
        assert item["observed_at_utc"]
    assert "through_output_s" in payload["timings_seconds"]
    assert Path("requirements-release.txt").exists()


def test_r2_12_scope_no_novelty_claim():
    assert "## What is new" not in Path("README.md").read_text()
    m0 = Path("docs/scope-comparisons.md").read_text()
    assert "UNVERIFIED" in m0
    assert "light-duty-city-vehicle-utilization-data" in m0
    assert "Not open, reproducible software" not in m0


def test_r2_13_readable_case_study(release, ratings):
    root, _ = release
    html = (root / "results/report.html").read_text()
    assert "awaiting engineering review" in html
    assert "factor provenance" in html
    assert "conditional row-bootstrap" in html
    assert "Canadian aggregate" in html
    fleet = load_seattle_fleet(FIXTURES / "seattle_sample.csv")
    scored, _ = compute_baseline(fleet, pd.Series([12000.0] * len(fleet)), 1.65, 1.75, ratings)
    scenario = scenario_comparison(scored, ratings, replacement_fraction=1)
    assert not scenario.bev_feasible.any()


def test_r2_03_real_nrcan_headers_variants_and_unknown_classes(tmp_path):
    from fleet_rightsizing.data_io import DataError

    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_contract.csv", FIXTURES / "nrcan_bev_sample.csv"
    )
    factors = ratings.lookup(1990, "UNKNOWN", "UNKNOWN", "TRUCK")
    assert factors.provenance == "class_mean"
    assert factors.co2_low < factors.co2_high
    source = pd.read_csv(FIXTURES / "nrcan_contract.csv")
    first = source.iloc[0]
    direct = ratings.lookup(
        int(first["Model year"]), first["Make"], first["Model"], "TRUCK", fuel_type="UNL"
    )
    assert direct.co2_low < direct.co2_high
    # All retained contract variants are gasoline, so a diesel identity must fail closed.
    incompatible = ratings.lookup(
        int(first["Model year"]), first["Make"], first["Model"], "TRUCK", fuel_type="DSL"
    )
    assert not incompatible.estimate_supported
    malformed = tmp_path / "bad.csv"
    malformed.write_text("different,headers\n1,2\n")
    with pytest.raises(DataError, match="Source schema changed"):
        RatingsIndex.from_files(malformed, FIXTURES / "nrcan_bev_sample.csv")
    source["Vehicle class"] = "Unrecognized publisher class"
    source.to_csv(malformed, index=False)
    with pytest.raises(DataError, match="Unknown NRCan class"):
        RatingsIndex.from_files(malformed, FIXTURES / "nrcan_bev_sample.csv")


def test_r2_11_pinned_publication_input_rejects_change(tmp_path):
    import json

    from fleet_rightsizing.config import DATA_URLS
    from fleet_rightsizing.data_io import DataError, sha256_file
    from fleet_rightsizing.ingest import ensure_datasets

    raw = tmp_path / "raw"
    raw.mkdir()
    for name in DATA_URLS:
        path = raw / f"{name}.csv"
        path.write_text("a\n")
        path.with_suffix(".csv.sha256").write_text(sha256_file(path))
    receipt = {name: {"sha256": sha256_file(raw / f"{name}.csv")} for name in DATA_URLS}
    (tmp_path / "publication-inputs.json").write_text(json.dumps(receipt))
    assert len(ensure_datasets(raw)) == 6
    path = raw / "seattle_fleet.csv"
    path.write_text("changed\n")
    path.with_suffix(".csv.sha256").write_text(sha256_file(path))
    with pytest.raises(DataError, match="Publication input changed"):
        ensure_datasets(raw)
