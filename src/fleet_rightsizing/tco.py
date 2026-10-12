"""Total cost of ownership calculations."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from fleet_rightsizing.config import (
    BEV_MAINTENANCE_PER_KM,
    BEV_PURCHASE_COST,
    CHARGER_AMORTIZATION,
    DISCOUNT_RATE,
    ELECTRICITY_PRICE,
    GASOLINE_PRICE,
    HORIZON_YEARS,
    ICE_MAINTENANCE_PER_KM,
    ICE_REPLACEMENT_COST,
    MIN_BEV_RANGE_KM,
    ZEV_TAILPIPE_REDUCTION,
)
from fleet_rightsizing.emissions import RatingsIndex
from fleet_rightsizing.plan import composite_score


@dataclass(frozen=True)
class TcoResult:
    annual_energy_cost: float
    annual_maintenance: float
    upfront_capital: float
    discounted_operating_npv: float
    ten_year_npv: float


def annuity_factor(rate: float, years: int) -> float:
    if rate == 0:
        return float(years)
    return (1 - (1 + rate) ** -years) / rate


def ice_tco_row(
    annual_km: float,
    fuel_litres: float,
    fuel_price: float,
    replacement_cost: float,
    maintenance_per_km: float = ICE_MAINTENANCE_PER_KM,
    discount_rate: float = DISCOUNT_RATE,
    horizon: int = HORIZON_YEARS,
) -> TcoResult:
    annual_energy = fuel_litres * fuel_price
    annual_maint = annual_km * maintenance_per_km
    operating = annual_energy + annual_maint
    discounted_operating = operating * annuity_factor(discount_rate, horizon)
    return TcoResult(
        annual_energy_cost=annual_energy,
        annual_maintenance=annual_maint,
        upfront_capital=replacement_cost,
        discounted_operating_npv=discounted_operating,
        ten_year_npv=replacement_cost + discounted_operating,
    )


def bev_tco_row(
    annual_km: float,
    kwh_per_100km: float,
    electricity_price: float,
    purchase_cost: float,
    maintenance_per_km: float,
    charger_cost: float,
    discount_rate: float = DISCOUNT_RATE,
    horizon: int = HORIZON_YEARS,
) -> TcoResult:
    annual_kwh = kwh_per_100km * annual_km / 100.0
    annual_energy = annual_kwh * electricity_price
    annual_maint = annual_km * maintenance_per_km
    operating = annual_energy + annual_maint
    discounted_operating = operating * annuity_factor(discount_rate, horizon)
    upfront = purchase_cost + charger_cost
    return TcoResult(
        annual_energy_cost=annual_energy,
        annual_maintenance=annual_maint,
        upfront_capital=upfront,
        discounted_operating_npv=discounted_operating,
        ten_year_npv=upfront + discounted_operating,
    )


def scenario_comparison(
    baseline: pd.DataFrame,
    ratings: RatingsIndex,
    replacement_fraction: float = 0.1,
) -> pd.DataFrame:
    """Illustrative catalogue screen; no engineering feasibility or fleet savings claim."""
    work = baseline.copy()
    work = work[work["estimate_supported"]].copy()
    if work.empty:
        return work
    work["composite_score"] = composite_score(work)
    work = work.sort_values("composite_score", ascending=False)
    n_replace = max(1, int(len(work) * replacement_fraction))
    work["illustrative_screen_flag"] = False
    work.loc[work.index[:n_replace], "illustrative_screen_flag"] = True
    savings: list[float] = []
    bev_ranges: list[float | None] = []
    bev_kwh: list[float | None] = []
    feasible: list[bool] = []
    for _, row in work.iterrows():
        if not row["illustrative_screen_flag"]:
            savings.append(0.0)
            bev_ranges.append(None)
            bev_kwh.append(None)
            feasible.append(False)
            continue
        vehicle_class = str(row.get("nrcan_vehicle_class", "Unknown"))
        bev = ratings.best_bev(vehicle_class, min_range=MIN_BEV_RANGE_KM)
        if bev is None:
            savings.append(0.0)
            bev_ranges.append(None)
            bev_kwh.append(None)
            feasible.append(False)
            continue
        replacement_cost = ICE_REPLACEMENT_COST
        ice = ice_tco_row(
            annual_km=float(row["annual_km"]),
            fuel_litres=float(row["annual_fuel_litres"]),
            fuel_price=float(row.get("fuel_price", GASOLINE_PRICE)),
            replacement_cost=replacement_cost,
        )
        bev_cost = bev_tco_row(
            annual_km=float(row["annual_km"]),
            kwh_per_100km=bev.combined_kwh_per_100km,
            electricity_price=ELECTRICITY_PRICE,
            purchase_cost=BEV_PURCHASE_COST,
            maintenance_per_km=BEV_MAINTENANCE_PER_KM,
            charger_cost=CHARGER_AMORTIZATION,
        )
        savings.append(ice.ten_year_npv - bev_cost.ten_year_npv)
        bev_ranges.append(bev.range_km)
        bev_kwh.append(bev.combined_kwh_per_100km)
        feasible.append(True)
    work["tco_savings_10yr"] = savings
    work["bev_range_km"] = bev_ranges
    work["bev_kwh_per_100km"] = bev_kwh
    work["illustrative_option"] = feasible
    work["engineering_status"] = "not reviewed; not a recommendation"
    work["scenario_value_status"] = "withheld placeholders; not evaluated fleet outcomes"
    work["hypothetical_npv_delta_cad"] = savings
    work["bev_feasible"] = False
    work["tco_savings_10yr"] = 0.0
    work["scenario_ghg_reduction_factor"] = [
        ZEV_TAILPIPE_REDUCTION if flag else 0.0 for flag in work["bev_feasible"]
    ]
    return work


def hypothetical_cost_case(**params: float) -> dict[str, float]:
    """Two fictional equivalent base vehicles; no municipal asset capital inference.

    Each transfers all 12,000 annual km to a BEV at 20 kWh/100 km. One ICE
    uses gasoline at 8 L/100 km, one diesel at 9 L/100 km. No upfits, residual
    value, tax or infrastructure beyond the stated charger allowance.
    """
    rate = params.get("discount_rate", DISCOUNT_RATE)
    ice_maint = params.get("ice_maintenance", ICE_MAINTENANCE_PER_KM)
    bev_maint = params.get("bev_maintenance", BEV_MAINTENANCE_PER_KM)
    delta = 0.0
    ice_total = 0.0
    bev_total = 0.0
    for fuel, litres, price in (
        ("gasoline_price", 960.0, GASOLINE_PRICE),
        ("diesel_price", 1080.0, 1.75),
    ):
        ice = ice_tco_row(
            12000, litres, params.get(fuel, price), ICE_REPLACEMENT_COST, ice_maint, rate
        )
        bev = bev_tco_row(
            12000,
            20,
            params.get("electricity_price", ELECTRICITY_PRICE),
            BEV_PURCHASE_COST,
            bev_maint,
            CHARGER_AMORTIZATION,
            rate,
        )
        ice_total += ice.ten_year_npv
        bev_total += bev.ten_year_npv
        delta += ice.ten_year_npv - bev.ten_year_npv
    return {
        "hypothetical_npv_delta_cad": delta,
        "ice_npv_cad": ice_total,
        "bev_npv_cad": bev_total,
        "hypothetical_tailpipe_reduction_pct": 100.0,
    }
