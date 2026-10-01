"""Replacement and reallocation ranking."""

from __future__ import annotations

import pandas as pd

from fleet_rightsizing.config import (
    ANALYSIS_YEAR,
    WEIGHT_AGE,
    WEIGHT_EMISSIONS,
    WEIGHT_UTILIZATION,
)


def _normalize_within(series: pd.Series, groups: pd.Series) -> pd.Series:
    normalized = pd.Series(0.0, index=series.index, dtype=float)
    for _, idx in groups.groupby(groups).groups.items():
        subset = series.loc[idx]
        span = float(subset.max() - subset.min())
        if span == 0:
            normalized.loc[idx] = 0.0
        else:
            normalized.loc[idx] = (subset - subset.min()) / span
    return normalized


def age_only_flags(fleet: pd.DataFrame, min_age: int = 12) -> pd.Series:
    age = ANALYSIS_YEAR - fleet["year"]
    return age >= min_age


def emissions_only_rank(fleet: pd.DataFrame) -> pd.Series:
    return fleet["annual_co2_kg"].rank(ascending=False, method="average")


def composite_score(fleet: pd.DataFrame) -> pd.Series:
    groups = fleet["standard_type"]
    util = _normalize_within(1.0 - fleet["annual_km"], groups)
    age = _normalize_within(ANALYSIS_YEAR - fleet["year"], groups)
    emit = _normalize_within(fleet["annual_co2_kg"], groups)
    return (
        WEIGHT_UTILIZATION * util
        + WEIGHT_AGE * age
        + WEIGHT_EMISSIONS * emit
    )


def build_replacement_plan(fleet: pd.DataFrame, top_n: int = 50) -> pd.DataFrame:
    work = fleet.copy()
    work = work[work["estimate_supported"]].copy()
    if work.empty:
        return work
    work["composite_score"] = composite_score(work)
    work["priority_rank"] = work["composite_score"].rank(ascending=False, method="first")
    work["age_only_flag"] = age_only_flags(work)
    work = work.sort_values("priority_rank")
    return work.head(top_n)


def reallocation_candidates(fleet: pd.DataFrame) -> pd.DataFrame:
    """Departments with duplicate illustrative flags of same standard type."""
    under = fleet[fleet["illustrative_underutilized"]].copy()
    if under.empty:
        return under
    grouped = (
        under.groupby(["department", "standard_type"])
        .size()
        .reset_index(name="illustrative_flag_count")
    )
    grouped = grouped[grouped["illustrative_flag_count"] > 1].sort_values(
        "illustrative_flag_count",
        ascending=False,
    )
    return grouped
