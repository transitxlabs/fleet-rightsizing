from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from fleet_rightsizing.data_io import sha256_file
from fleet_rightsizing.pipeline import peak_memory_mb, run_pipeline
from tests.conftest import FIXTURES


@pytest.fixture
def fixture_paths(tmp_path: Path) -> dict[str, Path]:
    mapping = {
        "seattle_fleet": FIXTURES / "seattle_sample.csv",
        "nyc_efficiency": FIXTURES / "nyc_sample.csv",
        "laval_fleet": FIXTURES / "laval_sample.csv",
        "nrcan_ratings": FIXTURES / "nrcan_sample.csv",
        "nrcan_bev": FIXTURES / "nrcan_bev_sample.csv",
        "federal_fleet_fuel": FIXTURES / "nyc_sample.csv",
    }
    for key, source in mapping.items():
        dest = tmp_path / f"{key}.csv"
        content = source.read_text(encoding="utf-8")
        dest.write_text(content, encoding="utf-8")
        digest = sha256_file(dest)
        dest.with_suffix(".csv.sha256").write_text(digest + "\n", encoding="utf-8")
    return {key: tmp_path / f"{key}.csv" for key in mapping}


def test_peak_memory_mb() -> None:
    assert peak_memory_mb() > 0


def test_run_pipeline_with_fixtures(
    tmp_path: Path,
    fixture_paths: dict[str, Path],
) -> None:
    with patch("fleet_rightsizing.pipeline.ensure_datasets", return_value=fixture_paths):
        payload = run_pipeline(
            results_dir=tmp_path / "results",
            figures_dir=tmp_path / "figures",
        )
    assert payload["baseline"]["vehicle_count"] == 26
    assert (tmp_path / "results" / "results.json").exists()
    assert (tmp_path / "results" / "report.html").exists()
    assert "stop_rules_passed" in payload
