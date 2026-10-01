"""Round 4 publication regressions, numbered as the independent R3 review."""

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import matplotlib.axes
import pandas as pd
import pytest

from fleet_rightsizing.baseline import compute_baseline, load_seattle_fleet
from fleet_rightsizing.emissions import RatingsIndex
from fleet_rightsizing.figures import plot_utilization_distribution
from fleet_rightsizing.pipeline import run_pipeline
from tests.conftest import FIXTURES

ROOT = Path(__file__).resolve().parents[1]


def checks():
    path = ROOT / "scripts/publication_checks.py"
    assert path.exists(), "Release history and analytical comparison checks are missing"
    spec = importlib.util.spec_from_file_location("publication_checks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    root = tmp_path_factory.mktemp("r4")
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


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def test_r3_01_candidate_history_scan_detects_ancestor(tmp_path):
    audit = checks()
    git(tmp_path, "init", "-q", "-b", "publication-r4")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    report = tmp_path / "REPORT.md"
    report.write_text("Historical " + chr(0x2014) + " claim")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Historical report")
    report.write_text("Corrected claim")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Corrected report")
    receipt = audit.scan_history(tmp_path)
    assert receipt["objects_scanned"] > 2
    assert any(hit["rule"] == "prohibited_punctuation" for hit in receipt["hits"])


def test_r3_02_archival_specification_not_active():
    assert "preregistered evaluation" not in (ROOT / "CHANGELOG.md").read_text()
    config = (ROOT / "mkdocs.yml").read_text()
    assert "exclude_docs:" in config and "PREREGISTRATION.md" in config
    landing = (ROOT / "docs/analysis-archive.md").read_text()
    assert "not proven preregistration" in landing
    assert "AMENDMENT_2026-10-01.md" in landing
    original = (ROOT / "docs/PREREGISTRATION.md").read_bytes()
    assert hashlib.sha256(original).hexdigest() == (
        "2d68b183355b8db38696a1140a70c09fd1bd85117c4c563b8e82d831deaa15ff"
    )
    assert (ROOT / "docs/archive/analysis-specification.txt").read_bytes() == original


def test_r3_03_same_cohort_flags_and_chart(release, tmp_path):
    root, payload = release
    scored = pd.read_csv(root / "results/seattle_scored.csv")
    cohort = scored[scored.estimate_supported]
    assert payload["evaluation"]["diagnostic_cohort_count"] == len(cohort)
    assert payload["evaluation"]["baseline_b2_count"] == int((cohort.annual_km < 5000).sum())
    assert not scored.loc[~scored.estimate_supported, "illustrative_underutilized"].any()
    thresholds = cohort.groupby("standard_type").annual_km.transform(lambda s: s.quantile(0.25))
    assert cohort.illustrative_underutilized.tolist() == (cohort.annual_km < thresholds).tolist()
    plotted = []
    original = matplotlib.axes.Axes.hist

    def capture(self, values, *args, **kwargs):
        plotted.extend(values)
        return original(self, values, *args, **kwargs)

    with patch.object(matplotlib.axes.Axes, "hist", capture):
        plot_utilization_distribution(scored, tmp_path / "cohort.png")
    assert plotted == cohort.annual_km.tolist()
    assert "estimated cohort" in (root / "RESULTS.md").read_text()


def test_r3_04_upfit_uncertainty_displayed(tmp_path):
    source = tmp_path / "upfit.csv"
    sample = pd.read_csv(FIXTURES / "seattle_sample.csv")
    sample.loc[0, "Description"] = "CARGO - CUTAWAY VAN - SPARTAN BODY"
    sample.loc[0, "Equipment Type"] = "VAN"
    sample.loc[0, "Asset Weight Category"] = "CLASS 2"
    sample.to_csv(source, index=False)
    fleet = load_seattle_fleet(source)
    ratings = RatingsIndex.from_files(
        FIXTURES / "nrcan_sample.csv", FIXTURES / "nrcan_bev_sample.csv"
    )
    scored, _ = compute_baseline(fleet, pd.Series([12000.0] * len(fleet)), 1.65, 1.75, ratings)
    assert scored.iloc[0]["upfit_status"] == "identified upfit; compatibility unresolved"
    assert "specialization unresolved" in scored.iloc[0]["scope_status"]
    dictionary = (ROOT / "docs/OUTPUT_DICTIONARY.md").read_text()
    assert "VAN -> Minivan" in dictionary
    assert "unweighted median" in dictionary
    assert (
        "Specialists/heavy/unknown weights excluded"
        not in (ROOT / "docs/technical-report.md").read_text()
    )


def test_r3_05_analytical_comparison_ignores_only_observations():
    audit = checks()
    reference = {
        "baseline": {"co2": 3.0},
        "inputs": {"a": {"sha256": "x", "observed_at_utc": "old"}},
        "timings_seconds": {"total": 1},
        "environment": {"python": "3.11"},
    }
    current = json.loads(json.dumps(reference))
    current["inputs"]["a"]["observed_at_utc"] = "new"
    current["timings_seconds"]["total"] = 100
    current["environment"]["python"] = "3.12"
    audit.compare_payloads(reference, current)
    current["baseline"]["co2"] = 3.001
    with pytest.raises(AssertionError):
        audit.compare_payloads(reference, current)
    current["baseline"]["co2"] = 3.0
    current["inputs"]["a"]["sha256"] = "changed"
    with pytest.raises(AssertionError):
        audit.compare_payloads(reference, current)


def test_r3_06_release_inventory_enforces_provider_boundaries(tmp_path):
    audit = checks()
    (tmp_path / "ATTRIBUTION.md").write_text("Provider conditions")
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "data/raw/source.csv").write_text("private cache")
    with pytest.raises(ValueError, match="excluded release path"):
        audit.release_inventory(tmp_path)
    (tmp_path / "data/raw/source.csv").unlink()
    receipt = audit.release_inventory(tmp_path)
    assert receipt["ATTRIBUTION.md"]["sha256"] == hashlib.sha256(b"Provider conditions").hexdigest()


def test_r3_07_history_scan_covers_secondary_refs(tmp_path):
    audit = checks()
    git(tmp_path, "init", "-q", "-b", "publication-r4")
    git(tmp_path, "config", "user.name", "Test")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    artifact = tmp_path / "file.txt"
    artifact.write_text("Safe")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Safe root")
    git(tmp_path, "checkout", "-qb", "other")
    artifact.write_text("/" + "Users/private/example")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "Unpublished artifact")
    git(tmp_path, "checkout", "-q", "publication-r4")
    receipt = audit.scan_history(tmp_path)
    assert len(receipt["refs"]) == 2
    assert any(hit["rule"] == "home_path" for hit in receipt["hits"])


def test_r3_08_zero_placeholders_have_machine_status(release):
    root, payload = release
    assert payload["scenario_value_status"] == "withheld placeholders; not evaluated fleet outcomes"
    ledger = pd.read_csv(root / "results/scenario_ledger.csv")
    assert ledger.scenario_value_status.eq(payload["scenario_value_status"]).all()
    assert not ledger.bev_feasible.any()
    assert ledger.tco_savings_10yr.eq(0).all()
    assert payload["recommendations_status"] == "withheld"


def test_r3_09_case_study_has_readable_values_and_no_audit_navigation(release):
    root, _ = release
    config = (ROOT / "mkdocs.yml").read_text().split("docs_dir:")[0]
    assert "Round 3 evidence:" not in config
    markdown = (root / "RESULTS.md").read_text()
    html = (root / "results/report.html").read_text()
    assert "Base example cash flows: `{" not in markdown
    assert "ice_npv_cad" not in html
    assert "Fictional cash flows (CAD)" in markdown
    assert "public-data integration" in (ROOT / "docs/index.md").read_text()
