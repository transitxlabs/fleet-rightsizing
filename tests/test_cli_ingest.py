from __future__ import annotations

from pathlib import Path

import pytest

from fleet_rightsizing.cli import main
from fleet_rightsizing.data_io import sha256_file
from fleet_rightsizing.ingest import ensure_datasets


def test_ensure_datasets_uses_verified_cache(tmp_path: Path) -> None:
    for name in (
        "seattle_fleet",
        "nyc_efficiency",
        "laval_fleet",
        "nrcan_ratings",
        "nrcan_bev",
        "federal_fleet_fuel",
    ):
        dest = tmp_path / f"{name}.csv"
        dest.write_text("a\n", encoding="utf-8")
        digest = sha256_file(dest)
        dest.with_suffix(".csv.sha256").write_text(digest + "\n", encoding="utf-8")
    paths = ensure_datasets(tmp_path)
    assert len(paths) == 6


def test_cli_main(capsys: pytest.CaptureFixture[str]) -> None:
    import sys
    from unittest.mock import patch

    with (
        patch("fleet_rightsizing.cli.run_pipeline", return_value={"evaluation": {}}),
        patch.object(sys, "argv", ["fleet-rightsizing"]),
    ):
        main()
    captured = capsys.readouterr()
    assert "Pipeline complete" in captured.out
