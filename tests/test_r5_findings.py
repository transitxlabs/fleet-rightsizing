"""Round 5 contracts from the independent round 4 publication review."""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from fleet_rightsizing.baseline import load_laval_fleet, load_seattle_fleet
from fleet_rightsizing.pipeline import run_pipeline
from fleet_rightsizing.plan import composite_score
from tests.conftest import FIXTURES
from tests.test_r4_findings import checks

ROOT = Path(__file__).resolve().parents[1]


def test_r4_03_formula_and_constant_group():
    frame = pd.DataFrame(
        {
            "standard_type": ["SUV"] * 3 + ["SEDAN"],
            "annual_km": [1000, 2000, 4000, 2000],
            "year": [2020] * 4,
            "annual_co2_kg": [1000] * 4,
        }
    )
    assert composite_score(frame).tolist() == pytest.approx([0.4, 0.4 * 2 / 3, 0, 0])
    text = (ROOT / "docs/technical-report.md").read_text()
    assert "reversed min-max mileage" in text
    assert "(class_max_km - km) / (class_max_km - class_min_km)" in text
    assert "constant" in text and "analysis year 2026" in text
    assert "inverse" not in (ROOT / "docs/AMENDMENT_2026-10-01.md").read_text()


def test_r4_04_rejections_and_analysis_metadata(tmp_path):
    laval_path = tmp_path / "laval.csv"
    laval_path.write_text((FIXTURES / "laval_sample.csv").read_text() + "999,FORD,VAN,,VAN,OPS\n")
    laval = load_laval_fleet(laval_path)
    receipt = laval.attrs["ingestion"]
    assert receipt["raw_rows"] == receipt["loaded_rows"] + receipt["rejected_rows"]
    assert receipt["rejection_reasons"] == {"blank_year": 1}
    assert receipt["rejected_records"][0]["source_row"] == receipt["raw_rows"]
    seattle_path = tmp_path / "seattle.csv"
    sample = pd.read_csv(FIXTURES / "seattle_sample.csv")
    sample = pd.concat([sample, pd.DataFrame({"EquipID": ["Total", "Applied filters"]})])
    sample.to_csv(seattle_path, index=False)
    seattle = load_seattle_fleet(seattle_path)
    assert seattle.attrs["ingestion"]["rejection_reasons"] == {"publisher_footer": 2}
    paths = {
        name: FIXTURES / filename
        for name, filename in {
            "seattle_fleet": "seattle_sample.csv",
            "nyc_efficiency": "nyc_sample.csv",
            "laval_fleet": "laval_sample.csv",
            "nrcan_ratings": "nrcan_sample.csv",
            "nrcan_bev": "nrcan_bev_sample.csv",
            "federal_fleet_fuel": "federal_sample.csv",
        }.items()
    }
    with patch("fleet_rightsizing.pipeline.ensure_datasets", return_value=paths):
        payload = run_pipeline(results_dir=tmp_path / "results", figures_dir=tmp_path / "figures")
    assert payload["analysis_year"] == 2026
    assert (
        payload["catalogue_coverage"]["eligible_records"]
        >= payload["baseline"]["supported_vehicle_count"]
    )
    for name, item in payload["ingestion"].items():
        assert item["raw_rows"] == payload["inputs"][name]["raw_rows"]
        assert item["raw_rows"] == item["loaded_rows"] + item["rejected_rows"]
        assert item["rejected_rows"] == len(item["rejected_records"])
    assert (tmp_path / "results/ingestion_rejections.csv").exists()
    for path in (tmp_path / "RESULTS.md", tmp_path / "results/report.html"):
        text = path.read_text()
        assert "Analysis year: 2026" in text
        assert "standard test-cycle" in text and "duty-cycle" in text
        assert "publisher_footer" in text


def test_r4_08_release_excludes_private_receipts_and_reports(tmp_path):
    audit = checks()
    for name in ("state/r4-evidence/build.txt", "docs/milestones/PUBLICATION_FIX_REPORT_R4.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private delivery receipt")
        with pytest.raises(ValueError, match="excluded release path"):
            audit.release_inventory(tmp_path)
        path.unlink()
    assert "milestones/**" in (ROOT / "mkdocs.yml").read_text()
    report = (ROOT / "REPORT.md").read_text()
    assert "publication-r4" not in report and "Public-data integration" in report


def test_r4_09_case_study_and_stewardship():
    page = (ROOT / "docs/index.md").read_text()
    assert page.splitlines()[2].startswith("Which")
    for term in (
        "Source-to-output",
        "Coverage and exclusions",
        "1,544",
        "361 / 1,568",
        "planned future work",
    ):
        assert term in page
    stewardship = (ROOT / "docs/stewardship.md").read_text()
    for term in (
        "TransitX Labs Inc.",
        "info@transitxlabs.ca",
        "Apache-2.0",
        "CC BY 4.0",
        "Support scope",
    ):
        assert term in stewardship


def test_export_uses_the_enforced_boundary(tmp_path):
    from tests.test_r4_findings import git

    source = tmp_path / "source"
    source.mkdir()
    git(source, "init", "-q", "-b", "main")
    git(source, "config", "user.name", "Test")
    git(source, "config", "user.email", "test@example.invalid")
    for name in ("README.md", "state/r4-evidence/test.txt", "docs/milestones/old.md"):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    git(source, "add", ".")
    git(source, "commit", "-qm", "Fixture")
    destination = tmp_path / "candidate"
    inventory = checks().export_release(source, destination)
    assert set(inventory) == {"README.md"}
    assert (source / "state/r4-evidence/test.txt").exists()
    assert not (destination / "state").exists()
    with pytest.raises(FileExistsError):
        checks().export_release(source, destination)


def test_ingestion_rejection_reasons_cover_each_parser(tmp_path):
    from fleet_rightsizing.baseline import load_nyc_measured
    from fleet_rightsizing.emissions import RatingsIndex
    from fleet_rightsizing.federal_check import federal_fleet_factor_check

    rows = pd.read_csv(FIXTURES / "laval_sample.csv", dtype=str)
    rows = pd.concat([rows, rows.assign(annee="invalid")])
    rows.to_csv(tmp_path / "laval.csv", index=False)
    assert load_laval_fleet(tmp_path / "laval.csv").attrs["ingestion"]["rejection_reasons"] == {
        "unparseable_year": 1
    }
    rows = pd.read_csv(FIXTURES / "nyc_sample.csv", dtype=str)
    rows = pd.concat([rows, rows.iloc[:1].assign(**{"Vehicle Count": "0"})])
    rows.to_csv(tmp_path / "nyc.csv", index=False)
    assert load_nyc_measured(tmp_path / "nyc.csv").attrs["ingestion"]["rejection_reasons"] == {
        "invalid_count_or_miles": 1
    }
    ice = pd.read_csv(FIXTURES / "nrcan_sample.csv", dtype=str)
    ice = pd.concat(
        [
            ice,
            ice.iloc[:1].assign(**{"Model year": "invalid"}),
            ice.iloc[:1].assign(**{"CO2 emissions (g/km)": "invalid"}),
        ]
    )
    ice.to_csv(tmp_path / "ice.csv", index=False)
    bev = pd.read_csv(FIXTURES / "nrcan_bev_sample.csv", dtype=str)
    bev = pd.concat([bev, bev.iloc[:1].assign(**{"Range (km)": "invalid"})])
    bev.to_csv(tmp_path / "bev.csv", index=False)
    ratings = RatingsIndex.from_files(tmp_path / "ice.csv", tmp_path / "bev.csv")
    assert ratings.ingestion["nrcan_ratings"]["rejection_reasons"] == {
        "unparseable_year": 1,
        "unparseable_factors": 1,
    }
    assert ratings.ingestion["nrcan_bev"]["rejected_rows"] == 1
    federal = pd.read_csv(FIXTURES / "federal_sample.csv", dtype=str)
    federal = pd.concat([federal, federal.iloc[:1].assign(**{"Fiscal year": "invalid"})])
    federal.to_csv(tmp_path / "federal.csv", index=False)
    check = federal_fleet_factor_check(tmp_path / "federal.csv")
    assert check["ingestion"]["rejection_reasons"] == {"unparseable_fiscal_year": 1}
