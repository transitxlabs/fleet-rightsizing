from __future__ import annotations

from pathlib import Path

from fleet_rightsizing.baseline import BaselineSummary
from fleet_rightsizing.evaluation import EvaluationResult, StopRuleReport
from fleet_rightsizing.federal_check import federal_fleet_factor_check
from fleet_rightsizing.ingest import load_manifest
from fleet_rightsizing.report import write_results_markdown
from tests.conftest import FIXTURES


def test_federal_fleet_factor_check() -> None:
    result = federal_fleet_factor_check(FIXTURES / "nyc_sample.csv")
    assert result["status"] in {"ok", "empty"}


def test_load_manifest() -> None:
    manifest = load_manifest()
    assert "datasets" in manifest


def test_write_results_markdown(tmp_path: Path) -> None:
    summary = BaselineSummary(
        vehicle_count=10,
        supported_vehicle_count=8,
        annual_fuel_litres=1000.0,
        annual_co2_tonnes=2.5,
        annual_fuel_cost_cad=1500.0,
        nrcan_eligible_match_rate=0.2,
        excluded_bev_count=1,
        excluded_non_powered_count=0,
        excluded_trailer_count=1,
        excluded_unsupported_count=2,
    )
    evaluation = EvaluationResult(
        threshold_overlap_nyc=0.75,
        spearman_ghg_rank_nyc=0.5,
        spearman_ci_low=0.4,
        spearman_ci_high=0.6,
        scenario_ghg_reduction_pct=2.0,
        scenario_tco_savings_cad=10000.0,
        scenario_eligible_count=1,
        scenario_infeasible_count=0,
        ghg_bootstrap_low=2.0,
        ghg_bootstrap_high=3.0,
        baseline_b1_count=2,
        baseline_b2_count=3,
        package_illustrative_flag_count=4,
        stop_rules=StopRuleReport(False, True, True, ("match rate low",)),
    )
    payload = {
        "timings_seconds": {"total_instrumented_s": 1.0, "wall_clock_s": 2.0},
        "peak_memory_mb": 100.0,
        "environment": {"platform": "test"},
        "stop_rules_passed": False,
    }
    out = tmp_path / "RESULTS.md"
    write_results_markdown(out, payload, summary, evaluation)
    text = out.read_text(encoding="utf-8")
    assert "Stop rules" in text
    assert "20.0%" in text or "20.0" in text
