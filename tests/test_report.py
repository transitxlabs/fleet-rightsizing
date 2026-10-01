from __future__ import annotations

from pathlib import Path

from fleet_rightsizing.baseline import BaselineSummary
from fleet_rightsizing.evaluation import EvaluationResult, StopRuleReport
from fleet_rightsizing.report import render_report, write_results_json


def test_render_report_and_json(tmp_path: Path) -> None:
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
    html_path = render_report(
        tmp_path / "report.html",
        "Test Fleet",
        summary,
        evaluation,
        [{"name": "fig.png", "path": "../figures/fig.png"}],
    )
    text = html_path.read_text(encoding="utf-8")
    assert "<main>" in text
    assert "fig.png" in text
    assert "../figures/fig.png" in text
    json_path = tmp_path / "out.json"
    write_results_json(json_path, {"ok": True})
    assert '"ok": true' in json_path.read_text()
