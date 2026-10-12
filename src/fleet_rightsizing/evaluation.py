"""Evaluation metrics and baseline comparisons."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fleet_rightsizing.config import SENSITIVITY, TORONTO_KM_THRESHOLD
from fleet_rightsizing.plan import age_only_flags, composite_score
from fleet_rightsizing.utilization import diagnostic_cohort, threshold_overlap_rate


@dataclass(frozen=True)
class StopRuleReport:
    memory_ok: bool
    match_rate_ok: bool
    bootstrap_width_ok: bool
    messages: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationResult:
    threshold_overlap_nyc: float
    spearman_ghg_rank_nyc: float
    spearman_ci_low: float
    spearman_ci_high: float
    scenario_ghg_reduction_pct: float
    scenario_tco_savings_cad: float
    scenario_eligible_count: int
    scenario_infeasible_count: int
    ghg_bootstrap_low: float
    ghg_bootstrap_high: float
    baseline_b1_count: int
    baseline_b2_count: int
    package_illustrative_flag_count: int
    diagnostic_cohort_count: int = 0
    stop_rules: StopRuleReport = field(
        default_factory=lambda: StopRuleReport(True, True, True)
    )


def perfect_score(keys: list[str], predicted: dict[str, float], truth: dict[str, float]) -> float:
    if not keys:
        return 0.0
    errors = [abs(predicted[k] - truth[k]) for k in keys]
    max_error = max(truth.values()) - min(truth.values()) if truth else 1.0
    if max_error == 0:
        return 1.0 if all(e == 0 for e in errors) else 0.0
    mae = sum(errors) / len(errors)
    return max(0.0, 1.0 - mae / max_error)


def empty_score() -> float:
    return 0.0


def surplus_scorer(keys: list[str], flagged: dict[str, bool], reference: dict[str, bool]) -> float:
    if not keys:
        return 0.0
    matches = sum(1 for key in keys if flagged.get(key) == reference.get(key))
    return matches / len(keys)


def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 2:
        return 0.0
    xr = pd.Series(x).rank(method="average").to_numpy()
    yr = pd.Series(y).rank(method="average").to_numpy()
    if np.std(xr) == 0 or np.std(yr) == 0:
        return 0.0
    return float(np.corrcoef(xr, yr)[0, 1])


def bootstrap_spearman(
    x: np.ndarray,
    y: np.ndarray,
    n_samples: int = 500,
    seed: int = 42,
) -> tuple[float, float, float]:
    point = spearman_rho(x, y)
    if len(x) < 3:
        return point, point, point
    rng = np.random.default_rng(seed)
    rhos = np.empty(n_samples)
    n = len(x)
    for i in range(n_samples):
        idx = rng.integers(0, n, size=n)
        rhos[i] = spearman_rho(x[idx], y[idx])
    return point, float(np.percentile(rhos, 2.5)), float(np.percentile(rhos, 97.5))


def prepare_nyc_rank_frame(
    nyc_measured: pd.DataFrame,
    intensity_lookup: Callable[[int, str, str, str], float],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for row in nyc_measured.to_dict(orient="records"):
        year = int(row["year"])
        make = str(row["make"])
        model = str(row["model"])
        standard_type = str(row["standard_type"])
        miles = float(row["miles_per_vehicle"])
        intensity = intensity_lookup(year, make, model, standard_type)
        annual_km = miles * 1.60934
        rows.append(
            {
                "year": year,
                "make": make,
                "model": model,
                "standard_type": standard_type,
                "annual_km": annual_km,
                "annual_co2_kg": intensity * annual_km / 1000.0,
                "co2_g_per_km": intensity,
            }
        )
    return pd.DataFrame(rows)


def evaluate(
    seattle_scored: pd.DataFrame,
    nyc_measured: pd.DataFrame,
    nyc_scored: pd.DataFrame,
    scenario: pd.DataFrame,
    ghg_point: float,
    ghg_low: float,
    ghg_high: float,
    stop_rules: StopRuleReport,
    intensity_lookup: Callable[[int, str, str, str], float],
) -> EvaluationResult:
    measured = nyc_scored.copy()
    overlap = threshold_overlap_rate(
        measured["underutilized"],
        measured["miles_per_vehicle"]
        < measured.groupby("standard_type")["miles_per_vehicle"].transform("median"),
    )

    nyc_rank_frame = prepare_nyc_rank_frame(nyc_measured, intensity_lookup)
    package_rank = composite_score(nyc_rank_frame).rank(ascending=False)
    intensity_rank = nyc_rank_frame["co2_g_per_km"].rank(ascending=False, method="average")
    rho, rho_low, rho_high = bootstrap_spearman(
        package_rank.to_numpy(),
        intensity_rank.to_numpy(),
    )

    supported = seattle_scored.loc[seattle_scored["estimate_supported"], "annual_co2_kg"]
    baseline_ghg = float(supported.sum())
    replaced = scenario[scenario["bev_feasible"]]
    reduction_mass = float(
        (replaced["annual_co2_kg"] * replaced["scenario_ghg_reduction_factor"]).sum()
    )
    scenario_ghg = baseline_ghg - reduction_mass
    reduction = (baseline_ghg - scenario_ghg) / baseline_ghg * 100 if baseline_ghg else 0.0
    tco_savings = float(scenario.loc[scenario["bev_feasible"], "tco_savings_10yr"].sum())

    cohort = diagnostic_cohort(seattle_scored)
    b2_flags = cohort["annual_km"] < TORONTO_KM_THRESHOLD

    return EvaluationResult(
        threshold_overlap_nyc=overlap,
        spearman_ghg_rank_nyc=rho,
        spearman_ci_low=rho_low,
        spearman_ci_high=rho_high,
        scenario_ghg_reduction_pct=reduction,
        scenario_tco_savings_cad=tco_savings,
        scenario_eligible_count=int(replaced.shape[0]),
        scenario_infeasible_count=int(
            scenario[scenario["illustrative_screen_flag"] & ~scenario["bev_feasible"]].shape[0]
        ),
        ghg_bootstrap_low=ghg_low,
        ghg_bootstrap_high=ghg_high,
        baseline_b1_count=int(age_only_flags(cohort).sum()),
        baseline_b2_count=int(b2_flags.sum()),
        package_illustrative_flag_count=int(cohort["illustrative_underutilized"].sum()),
        diagnostic_cohort_count=len(cohort),
        stop_rules=stop_rules,
    )


def sensitivity_table(
    baseline_fn: Callable[..., float],
    base_params: dict[str, float],
) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for name, span in SENSITIVITY.items():
        for label, value in (("low", span.low), ("high", span.high)):
            params = dict(base_params)
            params[name] = value
            result = baseline_fn(**params)
            rows.append({"parameter": name, "level": label, "value": value, "ghg_tonnes": result})
    return pd.DataFrame(rows)
