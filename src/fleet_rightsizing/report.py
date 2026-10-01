"""HTML report generation with accessible markup."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, Template, select_autoescape

from fleet_rightsizing.baseline import BaselineSummary
from fleet_rightsizing.evaluation import EvaluationResult


def _load_template() -> Template:
    template_path = files("fleet_rightsizing").joinpath("templates/report.html.j2")
    text = template_path.read_text(encoding="utf-8")
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    return env.from_string(text)


def format_range(uncertainty: object) -> str:
    bounds = uncertainty.get("assumption_range_tonnes", []) if isinstance(uncertainty, dict) else []
    return f"{bounds[0]:,.1f} to {bounds[1]:,.1f}" if len(bounds) == 2 else "unavailable"


def cost_rows(case: object) -> list[tuple[str, str]]:
    if not isinstance(case, dict):
        return []
    return [
        (label, f"{case[key]:,.2f}")
        for key, label in (
            ("ice_npv_cad", "ICE NPV"),
            ("bev_npv_cad", "BEV NPV"),
            ("hypothetical_npv_delta_cad", "ICE minus BEV NPV"),
        )
        if key in case
    ]


def render_report(
    output: Path,
    fleet_name: str,
    summary: BaselineSummary,
    evaluation: EvaluationResult,
    figures: list[dict[str, str]],
    payload: dict[str, object] | None = None,
) -> Path:
    template = _load_template()
    stop_text = (
        "Configured diagnostic gates passed; this does not establish validation."
        if evaluation.stop_rules.match_rate_ok
        and evaluation.stop_rules.bootstrap_width_ok
        and evaluation.stop_rules.memory_ok
        else "; ".join(evaluation.stop_rules.messages) or "Stop rule review required."
    )
    html_text = template.render(
        fleet_name=fleet_name,
        summary=summary,
        fuel_litres=f"{summary.annual_fuel_litres:.0f}",
        co2_tonnes=f"{summary.annual_co2_tonnes:.1f}",
        fuel_cost=f"{summary.annual_fuel_cost_cad:.0f}",
        match_rate=f"{summary.nrcan_eligible_match_rate * 100:.1f}%",
        overlap=f"{evaluation.threshold_overlap_nyc * 100:.1f}%",
        spearman=(
            f"{evaluation.spearman_ghg_rank_nyc:.3f} "
            f"(95% CI {evaluation.spearman_ci_low:.3f} to "
            f"{evaluation.spearman_ci_high:.3f})"
        ),
        ghg_reduction=f"{evaluation.scenario_ghg_reduction_pct:.1f}%",
        tco_savings=f"{evaluation.scenario_tco_savings_cad:.0f}",
        ghg_ci=(f"{evaluation.ghg_bootstrap_low:.1f} to {evaluation.ghg_bootstrap_high:.1f}"),
        eligible_count=evaluation.scenario_eligible_count,
        evaluation_count=evaluation.diagnostic_cohort_count,
        age_flags=evaluation.baseline_b1_count,
        km_flags=evaluation.baseline_b2_count,
        quartile_flags=evaluation.package_illustrative_flag_count,
        infeasible_count=evaluation.scenario_infeasible_count,
        stop_text=stop_text,
        figures=figures,
        payload=payload or {},
        assumption_range=format_range((payload or {}).get("uncertainty", {})),
        cost_rows=cost_rows((payload or {}).get("hypothetical_cost_case", {})),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n", encoding="utf-8"
    )
    return output


def write_results_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def federal_rows(check: object) -> list[str]:
    if not isinstance(check, dict):
        return ["Unavailable."]
    rows = [
        f"Status: {check.get('status', 'empty')}; fiscal year beginning "
        f"{check.get('latest_year', 0)}; compatible rows "
        f"{check.get('compatible_rows', 0)} of {check.get('latest_year_rows', 0)}.",
        "",
        "| Fuel | Litres | kg CO2e/L | Illustrative CO2 kg/L |",
        "| --- | ---: | ---: | ---: |",
    ]
    for fuel, item in check.get("fuels", {}).items():
        rows.append(
            f"| {fuel} | {item['litres']:,.0f} | {item['kg_co2e_per_l']:.3f} | "
            f"{item['illustrative_co2_kg_per_l']:.1f} |"
        )
    return rows


def write_results_markdown(
    output: Path,
    payload: dict[str, object],
    summary: BaselineSummary,
    evaluation: EvaluationResult,
) -> None:
    timings_raw = payload.get("timings_seconds", {})
    timings = timings_raw if isinstance(timings_raw, dict) else {}
    env_raw = payload.get("environment", {})
    environment = env_raw if isinstance(env_raw, dict) else {}
    coverage_raw = payload.get("catalogue_coverage", {})
    coverage = coverage_raw if isinstance(coverage_raw, dict) else {}
    excluded = summary.vehicle_count - summary.supported_vehicle_count
    lines = [
        "# Results: public-data integration demonstration",
        "",
        "Generated from the same results record as `results/results.json` and HTML. "
        "This work sample is not client work.",
        "",
        f"Analysis year: {payload.get('analysis_year', 'unavailable')}. Fixed age reference year, "
        "not a claim of current inventory or catalogue availability.",
        "",
        "## Scope and failed gate",
        "",
        "Fleet savings and operational recommendations: **withheld**. Catalogue options are "
        "illustrative, awaiting engineering review of payload, body, seating, mission, upfits "
        "and current availability. Laval is an ingestion case only.",
        "",
        f"Stop rules passed: **{payload.get('stop_rules_passed', False)}**. "
        + "; ".join(evaluation.stop_rules.messages),
        "",
        "## Seattle simulated light-duty estimate",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Loaded / estimated records | {summary.vehicle_count:,} / "
        f"{summary.supported_vehicle_count:,} |",
        f"| Annual fuel (L) | {summary.annual_fuel_litres:,.0f} |",
        f"| Annual tailpipe CO2 (t) | {summary.annual_co2_tonnes:,.1f} |",
        f"| Annual fuel cost (CAD) | {summary.annual_fuel_cost_cad:,.0f} |",
        f"| NRCan catalogue match rate (scoped powered light-duty) | "
        f"{coverage.get('matched_records', 0):,}/{coverage.get('eligible_records', 0):,} "
        f"({summary.nrcan_eligible_match_rate:.1%}) |",
        "",
        f"Total exclusions: **{excluded:,}**. Disjoint breakdown: "
        f"{summary.excluded_bev_count:,} BEV, {summary.excluded_non_powered_count:,} non-powered, "
        f"{summary.excluded_trailer_count:,} trailer, "
        f"{summary.excluded_unsupported_count:,} other unsupported (scope or factor).",
        "",
        f"Catalogue gate: {coverage.get('matched_records', 0):,} matches / "
        f"{coverage.get('eligible_records', 0):,} scope/fuel-eligible records. "
        f"The estimated cohort has {summary.supported_vehicle_count:,} records; "
        f"{coverage.get('eligible_without_supported_factors', 0):,} eligible records lack "
        "supported factors and are excluded from estimated totals.",
        "",
        "NRCan factors are standard test-cycle ratings, not municipal duty-cycle measurements. "
        "No measured duty-cycle adjustment is available. Inventory and catalogue vintages "
        "differ (ICE ratings 2015-2024); they establish neither current inventory nor current "
        "purchase availability. Input hashes identify snapshots, not a common observation year.",
        "",
        "## Factor provenance",
        "",
        "Catalogue matches use compatible-fuel variant means with unresolved engine and "
        "transmission; they are not verified municipal specifications. Class proxies use "
        "arithmetic means and observed catalogue extrema, not medians. Known weights and "
        "identified duty tokens screened; specialization remains unresolved. SERVICE BODY "
        "and CUTAWAY can pass; scope/upfit statuses in both ledgers disclose this. "
        "Generic factors are "
        "unsupported and contribute no estimate. Excluded records are not zero-emission assets.",
        "",
        "| Provenance | Records | CO2 (t) | Share of estimate |",
        "| --- | ---: | ---: | ---: |",
    ]
    totals = payload.get("provenance_totals", {})
    if isinstance(totals, dict):
        for name, item in totals.items():
            mass = item["co2_kg"] / 1000
            share = mass / summary.annual_co2_tonnes if summary.annual_co2_tonnes else 0
            lines.append(f"| {name} | {item['records']} | {mass:,.1f} | {share:.1%} |")
    uncertainty = payload.get("uncertainty", {})
    assumption = format_range(uncertainty)
    lines += [
        "",
        "## Uncertainty and descriptive flags",
        "",
        f"Conditional row-bootstrap diagnostic (central 95% of resamples): "
        f"{evaluation.ghg_bootstrap_low:,.1f} to {evaluation.ghg_bootstrap_high:,.1f} t. "
        "The estimand is the sum of n iid draws from the empirical distribution of "
        "fixed simulated light-duty emissions. It has no coverage claim for the real "
        "finite municipal fleet. Calibration, classification and mission errors are omitted.",
        "",
        f"Assumption range (t): {assumption}. Chosen mileage multipliers 0.7/1.3 "
        "times observed variant/class factor extrema. This is not a probability interval.",
        "",
        f"NYC threshold overlap: {evaluation.threshold_overlap_nyc:.1%}; "
        "quartile versus median labels on the same groups, not accuracy. "
        f"Composite versus g/km rho: {evaluation.spearman_ghg_rank_nyc:.3f} "
        f"(row diagnostic {evaluation.spearman_ci_low:.3f} to "
        f"{evaluation.spearman_ci_high:.3f}), not superiority.",
        "",
        f"All three diagnostics and the utilization chart use the same estimated cohort "
        f"of {evaluation.diagnostic_cohort_count:,} records, including light-duty trucks. "
        "Quartiles are recalculated within this cohort; excluded records are not flagged. "
        f"Age-only flags: {evaluation.baseline_b1_count}; kilometre-only Toronto "
        f"proxy flags: {evaluation.baseline_b2_count}; simulated quartile flags: "
        f"{evaluation.package_illustrative_flag_count}. These flags do not establish "
        "surplus. Legacy zero fleet scenario values are withheld placeholders; "
        "not evaluated fleet outcomes. "
        "Engine hours, frequency, dispatch, reserve, emergency coverage and service demand "
        "are absent. No ranked replacement or reallocation plan is released.",
        "",
        "## Fictional cost example",
        "",
        "Two equivalent hypothetical base vehicles each travel 12,000 km/year; one uses "
        "960 L gasoline and one 1,080 L diesel. Both BEVs use 20 kWh/100 km. Capital is "
        "CAD 35,000 ICE versus CAD 45,000 BEV plus CAD 3,500 charging per unit. "
        "No historical in-service value, FX conversion, specialist upfit, tax or residual "
        "value enters this illustration. All mileage transfers to BEVs: 100% vehicle "
        "tailpipe reduction, with upstream/manufacturing excluded. This is not "
        "fleet savings.",
        "",
        "Fictional cash flows (CAD): "
        + "; ".join(
            f"{label}: {value}"
            for label, value in cost_rows(payload.get("hypothetical_cost_case", {}))
        )
        + ". "
        "Six one-at-a-time economic ranges are in `results/sensitivity.csv`; emissions "
        "are physically invariant to these prices. Scenario confidence intervals "
        "are withheld.",
        "",
        "## Canadian aggregate accounting example",
        "",
        "Federal source GHG is CO2e. Latest-year scope-1 on-road gasoline and diesel "
        "are compared separately to illustrative 2.3/2.7 kg CO2/L references. Differences "
        "can reflect rounding, blends and non-CO2 gases; this does not validate "
        "Seattle factors.",
        "",
        *federal_rows(payload.get("federal_factor_check", {})),
        "",
    ]
    lines += [
        "",
        "## Ingestion reconciliation",
        "",
        "Loaded means accepted by the source parser, before analysis exclusions. "
        "Seattle publisher_footer rows are Total and Applied filters metadata, not vehicles. "
        "Laval blank_year rows are rejected inventory records; Laval remains ingestion only. "
        "The small rejected-record ledger is results/ingestion_rejections.csv; "
        "source_row is a 1-based data-record ordinal after the header.",
        "",
        "| Source | Raw | Loaded | Rejected | Reasons |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    ingestion = payload.get("ingestion", {})
    if isinstance(ingestion, dict):
        for name, item in ingestion.items():
            reasons = "; ".join(
                f"{key}: {value}" for key, value in item["rejection_reasons"].items()
            )
            lines.append(
                f"| {name} | {item['raw_rows']:,} | {item['loaded_rows']:,} | "
                f"{item['rejected_rows']:,} | {reasons or 'none'} |"
            )
    lines += [
        "",
        "## Input receipt",
        "",
        "Hashes identify observed publication inputs; retrieval timestamps for inherited "
        "caches are unknown. Changed endpoints fail the pinned release check; update inputs "
        "explicitly and reassess outputs. Snapshot availability is not guaranteed.",
        "",
        "| Dataset | Rows | Bytes | SHA-256 | Observed UTC |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    inputs = payload.get("inputs", {})
    if isinstance(inputs, dict):
        for name, item in inputs.items():
            lines.append(
                f"| {name} | {item['raw_rows']} | {item['bytes']} | "
                f"{item['sha256']} | {item['observed_at_utc']} |"
            )
    lines += [
        "",
        "## Performance receipt",
        "",
        f"OS/architecture: {environment.get('platform', 'unknown')}; "
        f"Python: {environment.get('python_version', 'unknown')}. "
        f"Process high-water RSS: {payload.get('peak_memory_mb', 0):.1f} MiB. "
        f"Instrumented stage sum: {timings.get('total_instrumented_s', 0):.2f} s. "
        f"Through CSV/HTML output: {timings.get('through_output_s', 0):.2f} s. "
        "Imports, final JSON/Markdown metadata serialization and interpreter startup are "
        "excluded. Stage RSS observations are process high-water marks, not isolated usage.",
        "",
        "## Charts",
        "",
        "![Simulated CO2 by factor provenance, not measured emissions]"
        "(figures/ghg_by_department.png)",
        "",
        "![Invented annual kilometres and class quartiles, not operational surplus]"
        "(figures/utilization_proxy.png)",
        "",
        "![Synthetic sensitivity for two fictional base vehicles: circles show low inputs, "
        "squares high inputs; no public assets or municipal fleet savings]"
        "(figures/fictional_sensitivity.png)",
        "",
        "This code-generated chart uses only the synthetic two-vehicle cost inputs "
        "described above. Each of six economic inputs varies alone; all others stay fixed. "
        "Numeric low/high inputs and NPV values are in `results/sensitivity.csv`.",
        "",
        "Portable HTML embeds its images and provider notices. "
        "See `ATTRIBUTION.md` for data attribution; portable outputs carry "
        "`results/ATTRIBUTION.md`. Code is Apache-2.0; prose is CC BY 4.0; source rights "
        "continue to apply to figures and derived data.",
        "",
    ]
    # Root and docs pages are byte-identical; provide assets next to both in pipeline.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
