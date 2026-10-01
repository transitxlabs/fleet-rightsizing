"""Utilization detection with measured and proxy modes."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fleet_rightsizing.config import BOOTSTRAP_SAMPLES, BOOTSTRAP_SEED, TORONTO_KM_THRESHOLD


def class_miles_per_vehicle(nyc: pd.DataFrame) -> pd.Series:
    grouped = nyc.groupby("standard_type")["miles_per_vehicle"]
    return grouped.median()


def diagnostic_cohort(fleet: pd.DataFrame) -> pd.DataFrame:
    """One cohort for all descriptive flags and the mileage chart: estimated records."""
    return fleet.loc[fleet["estimate_supported"]].copy()


def miles_to_km(miles: float) -> float:
    return miles * 1.60934


def measured_underutilized(nyc: pd.DataFrame) -> pd.DataFrame:
    work = nyc.copy()
    thresholds = work.groupby("standard_type")["miles_per_vehicle"].transform(
        lambda s: s.quantile(0.25)
    )
    work["threshold_miles"] = thresholds
    work["underutilized"] = work["miles_per_vehicle"] < thresholds
    work["mode"] = "measured"
    return work


def proxy_annual_km(
    fleet: pd.DataFrame,
    class_medians_km: pd.Series,
    rng: np.random.Generator,
) -> pd.Series:
    """Illustrative proxy mileage: class median plus Gaussian noise (seeded)."""
    km_values: list[float] = []
    for _, row in fleet.iterrows():
        standard = str(row["standard_type"])
        calibration_class = "PICKUP" if standard == "TRUCK" else standard
        median = class_medians_km.get(calibration_class, class_medians_km.median())
        noise = rng.normal(0.0, 0.15 * median)
        km_values.append(max(500.0, median + noise))
    return pd.Series(km_values, index=fleet.index, name="proxy_annual_km")


def proxy_underutilized(fleet: pd.DataFrame, annual_km: pd.Series) -> pd.DataFrame:
    work = fleet.copy()
    work["annual_km"] = annual_km
    work["mileage_mode"] = "simulated_proxy"
    thresholds = work.groupby("standard_type")["annual_km"].transform(lambda s: s.quantile(0.25))
    work["threshold_km"] = thresholds
    work["illustrative_underutilized"] = work["annual_km"] < thresholds
    work["toronto_rule"] = work["annual_km"] < TORONTO_KM_THRESHOLD
    work["mode"] = "proxy"
    return work


def bootstrap_fleet_ghg(
    ghg_per_vehicle: np.ndarray,
    n_samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    n = len(ghg_per_vehicle)
    if n == 0:
        return 0.0, 0.0, 0.0
    totals = np.empty(n_samples)
    for i in range(n_samples):
        sample = rng.choice(ghg_per_vehicle, size=n, replace=True)
        totals[i] = sample.sum()
    point = float(ghg_per_vehicle.sum())
    low = float(np.percentile(totals, 2.5))
    high = float(np.percentile(totals, 97.5))
    return point, low, high


def threshold_overlap_rate(
    flagged: pd.Series,
    reference: pd.Series,
) -> float:
    if len(flagged) == 0:
        return 0.0
    return float((flagged == reference).mean())
