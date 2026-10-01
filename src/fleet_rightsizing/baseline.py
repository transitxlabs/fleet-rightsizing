"""Fleet inventory parsing and baseline GHG/fuel estimates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fleet_rightsizing.data_io import (
    DataError,
    IngestionReceipt,
    parse_number,
    require_csv_columns,
    row_get,
    stream_csv_rows,
)
from fleet_rightsizing.emissions import EmissionFactors, RatingsIndex

EQUIPMENT_TO_STANDARD: dict[str, str] = {
    "SUV": "SUV",
    "VAN": "VAN",
    "TRUCK": "TRUCK",
    "PICKUP": "TRUCK",
    "SEDAN": "SEDAN",
    "PASSENGER": "SEDAN",
    "FIRE": "TRUCK",
    "TRAILER": "TRAILER",
}

NON_POWERED_FUEL_TOKENS = frozenset({"NON", "NONE", "NA", "N/A"})
BEV_FUEL_TOKENS = frozenset({"ELE", "ELECTRIC", "EV", "BEV"})
HYBRID_FUEL_TOKENS = frozenset({"HYB", "HYBRID"})


@dataclass(frozen=True)
class VehicleRecord:
    vehicle_id: str
    make: str
    model: str
    year: int
    department: str
    fuel_type: str
    equipment_type: str
    standard_type: str
    in_service_cost: float
    description: str = ""
    weight_category: str = ""


@dataclass(frozen=True)
class BaselineSummary:
    vehicle_count: int
    supported_vehicle_count: int
    annual_fuel_litres: float
    annual_co2_tonnes: float
    annual_fuel_cost_cad: float
    nrcan_eligible_match_rate: float
    excluded_bev_count: int
    excluded_non_powered_count: int
    excluded_trailer_count: int
    excluded_unsupported_count: int


def map_standard_type(equipment_type: str, description: str) -> str:
    text = f"{equipment_type} {description}".upper()
    for token, standard in EQUIPMENT_TO_STANDARD.items():
        if token in text:
            return standard
    if "HYBRID" in text:
        return "SEDAN"
    return "OTHER"


def classify_powertrain(fuel_type: str, standard_type: str) -> str:
    token = fuel_type.upper().strip()
    if standard_type == "TRAILER":
        return "trailer"
    if token in BEV_FUEL_TOKENS:
        return "bev"
    if token in NON_POWERED_FUEL_TOKENS:
        return "non_powered"
    if token in HYBRID_FUEL_TOKENS or "HYB" in token:
        return "hybrid_ice"
    if token in {"", "UNKNOWN", "UNL", "DSL", "GAS", "GASOLINE", "DIESEL", "PROP", "CNG"}:
        return "ice"
    if "DSL" in token or "GAS" in token or "UNL" in token or "PROP" in token:
        return "ice"
    return "unsupported"


def emissions_supported(powertrain: str, standard_type: str) -> bool:
    if powertrain in {"bev", "non_powered", "trailer", "unsupported"}:
        return False
    return not (standard_type == "OTHER" and powertrain == "ice")


def load_seattle_fleet(path: Path) -> pd.DataFrame:
    require_csv_columns(
        path,
        {
            "EquipID",
            "Year",
            "Make",
            "Model",
            "Description",
            "Dept",
            "Equipment Type",
            "Fuel Type",
            "Asset Weight Category",
        },
    )
    receipt = IngestionReceipt()
    rows: list[dict[str, object]] = []
    for batch in stream_csv_rows(path):
        for row in batch:
            receipt.observe()
            year_raw = row_get(row, "Year")
            try:
                year = int(float(year_raw))
            except (ValueError, OverflowError):
                identity = row_get(row, "EquipID")
                footer = (
                    identity
                    if identity.lower() in {"total", "applied filters"}
                    or identity.lower().startswith("applied filters:")
                    else ""
                )
                receipt.reject(
                    "publisher_footer"
                    if footer
                    else "blank_year"
                    if not year_raw
                    else "unparseable_year",
                    "footer" if footer else "year",
                    footer or year_raw,
                )
                continue
            equip = row_get(row, "Equipment Type")
            desc = row_get(row, "Description")
            fuel = row_get(row, "Fuel Type")
            standard = map_standard_type(equip, desc)
            record = VehicleRecord(
                vehicle_id=row_get(row, "EquipID"),
                make=row_get(row, "Make"),
                model=row_get(row, "Model"),
                year=year,
                department=row_get(row, "Dept"),
                fuel_type=fuel,
                equipment_type=equip,
                standard_type=standard,
                in_service_cost=parse_number(row_get(row, "InServiceCost")) or 0.0,
                description=desc,
                weight_category=row_get(row, "Asset Weight Category"),
            )
            rows.append(record.__dict__)
    frame = pd.DataFrame(rows)
    frame["powertrain"] = [
        classify_powertrain(str(f), str(s))
        for f, s in zip(frame["fuel_type"], frame["standard_type"], strict=True)
    ]
    frame["emissions_supported"] = [
        emissions_supported(str(p), str(s))
        for p, s in zip(frame["powertrain"], frame["standard_type"], strict=True)
    ]
    frame["light_duty_scope"] = [
        light_duty_scope(str(w), str(e), str(d), str(st))
        for w, e, d, st in zip(
            frame["weight_category"],
            frame["equipment_type"],
            frame["description"],
            frame["standard_type"],
            strict=True,
        )
    ]
    frame["scope_status"] = [
        "screen passed; specialization unresolved" if passed else "outside inventory screen"
        for passed in frame["light_duty_scope"]
    ]
    frame["upfit_status"] = [
        "identified upfit; compatibility unresolved"
        if any(token in str(desc).upper() for token in ("SERVICE BODY", "CUTAWAY"))
        else "upfit and compatibility unverified"
        for desc in frame["description"]
    ]
    frame["emissions_supported"] &= frame["light_duty_scope"]
    frame["emissions_supported"] &= (
        frame["fuel_type"]
        .str.upper()
        .isin(["UNL", "DSL", "GAS", "GASOLINE", "DIESEL", "HYB", "HYBRID"])
    )
    frame.attrs["ingestion"] = receipt.payload()
    return frame


def light_duty_scope(weight: str, equipment: str, description: str, standard: str) -> bool:
    """Conservative inventory screen; it does not establish replacement compatibility."""
    text = f"{equipment} {description}".upper()
    specialist = (
        "POLICE",
        "MEDIC",
        "AID",
        "COMMAND",
        "COMMUNICATION",
        "FIRE",
        "AMBULANCE",
        "BRAUN",
        "WALKIN",
        "DUMP",
        "FLATBED",
        "CRANE",
        "HAZMAT",
        "BOMB",
        "BUCKET",
        "FLUSHER",
        "AERIAL",
        "SWEEPER",
    )
    return (
        weight.upper() in {"CLASS 1", "CLASS 2", "LIGHT"}
        and standard in {"SEDAN", "SUV", "VAN", "TRUCK"}
        and not any(token in text for token in specialist)
    )


def load_laval_fleet(path: Path) -> pd.DataFrame:
    receipt = IngestionReceipt()
    rows: list[dict[str, object]] = []
    for batch in stream_csv_rows(path):
        for row in batch:
            receipt.observe()
            year_raw = row_get(row, "annee", "Année")
            try:
                year = int(float(year_raw))
            except (ValueError, OverflowError):
                receipt.reject(
                    "blank_year" if not year_raw else "unparseable_year", "year", year_raw
                )
                continue
            equip = row_get(row, "type-equipement", "type_equipement")
            record = VehicleRecord(
                vehicle_id=row_get(row, "equipement"),
                make=row_get(row, "marque"),
                model=row_get(row, "modele"),
                year=year,
                department=row_get(row, "affectation"),
                fuel_type="unknown",
                equipment_type=equip,
                standard_type=map_standard_type(equip, equip),
                in_service_cost=0.0,
            )
            rows.append(record.__dict__)
    frame = pd.DataFrame(rows)
    frame["powertrain"] = [
        classify_powertrain(str(f), str(s))
        for f, s in zip(frame["fuel_type"], frame["standard_type"], strict=True)
    ]
    frame["emissions_supported"] = [
        emissions_supported(str(p), str(s))
        for p, s in zip(frame["powertrain"], frame["standard_type"], strict=True)
    ]
    frame.attrs["ingestion"] = receipt.payload()
    return frame


def load_nyc_measured(path: Path) -> pd.DataFrame:
    receipt = IngestionReceipt()
    rows: list[dict[str, object]] = []
    for batch in stream_csv_rows(path):
        for row in batch:
            receipt.observe()
            count = parse_number(row_get(row, "Vehicle Count"))
            miles = parse_number(row_get(row, "TOTAL ACTUAL MILES"))
            fuel = parse_number(row_get(row, "TOTAL ACTUAL FUEL"))
            if count is None or miles is None or count <= 0:
                receipt.reject(
                    "invalid_count_or_miles",
                    "Vehicle Count/TOTAL ACTUAL MILES",
                    f"{row_get(row, 'Vehicle Count')}/{row_get(row, 'TOTAL ACTUAL MILES')}",
                )
                continue
            standard = row_get(row, "STANDARD TYPE").upper()
            if standard not in {"SEDAN", "SUV", "VAN", "PICKUP"}:
                raise DataError(f"Unknown NYC calibration class: {standard}")
            rows.append(
                {
                    "year": int(parse_number(row_get(row, "YEAR")) or 0),
                    "make": row_get(row, "MAKE"),
                    "model": row_get(row, "MODEL"),
                    "standard_type": standard,
                    "vehicle_count": int(count),
                    "total_miles": miles,
                    "total_fuel_gallons": fuel or 0.0,
                    "miles_per_vehicle": miles / count,
                }
            )
    frame = pd.DataFrame(rows)
    frame.attrs["ingestion"] = receipt.payload()
    return frame


def attach_emissions(df: pd.DataFrame, ratings: RatingsIndex) -> pd.DataFrame:
    enriched = df.copy()
    factors: list[EmissionFactors] = []
    for _, row in enriched.iterrows():
        supported = bool(row.get("emissions_supported", True))
        factors.append(
            ratings.lookup(
                int(row["year"]),
                str(row["make"]),
                str(row["model"]),
                str(row.get("standard_type", "OTHER")),
                fuel_type=str(row.get("fuel_type", "")),
                estimate_supported=supported,
            )
        )
    enriched["co2_g_per_km"] = [f.co2_g_per_km for f in factors]
    enriched["l_per_100km"] = [f.combined_l_per_100km for f in factors]
    enriched["nrcan_vehicle_class"] = [f.vehicle_class for f in factors]
    enriched["nrcan_matched"] = [f.matched for f in factors]
    enriched["match_provenance"] = [f.provenance for f in factors]
    enriched["factor_uncertainty"] = [
        "engine/transmission/fuel variant unresolved; catalogue mean"
        if f.matched
        else "class proxy; variant and mission unresolved"
        if f.provenance == "class_mean"
        else "unsupported; no compatible factor"
        for f in factors
    ]
    enriched["factor_co2_low_g_per_km"] = [f.co2_low for f in factors]
    enriched["factor_co2_high_g_per_km"] = [f.co2_high for f in factors]
    enriched["estimate_supported"] = [
        bool(row.get("emissions_supported", True)) and f.estimate_supported
        for (_, row), f in zip(enriched.iterrows(), factors, strict=True)
    ]
    return enriched


def compute_baseline(
    fleet: pd.DataFrame,
    annual_km: pd.Series,
    gasoline_price: float,
    diesel_price: float,
    ratings: RatingsIndex,
) -> tuple[pd.DataFrame, BaselineSummary]:
    work = attach_emissions(fleet, ratings)
    work["annual_km"] = annual_km.values
    work["annual_fuel_litres"] = 0.0
    work["annual_co2_kg"] = 0.0
    supported = work["estimate_supported"]
    work.loc[supported, "annual_fuel_litres"] = (
        work.loc[supported, "l_per_100km"] * work.loc[supported, "annual_km"] / 100.0
    )
    work.loc[supported, "annual_co2_kg"] = (
        work.loc[supported, "co2_g_per_km"] * work.loc[supported, "annual_km"] / 1000.0
    )
    is_diesel = work["fuel_type"].str.upper().str.contains("DSL|DIESEL", na=False)
    work["fuel_price"] = gasoline_price
    work.loc[is_diesel, "fuel_price"] = diesel_price
    work["annual_fuel_cost"] = work["annual_fuel_litres"] * work["fuel_price"]
    work["exclusion_reason"] = "included_proxy_estimate"
    for category in ("bev", "non_powered", "trailer"):
        work.loc[work["powertrain"] == category, "exclusion_reason"] = category
    work.loc[
        (~supported) & ~work["powertrain"].isin(["bev", "non_powered", "trailer"]),
        "exclusion_reason",
    ] = "unsupported_scope_or_factor"
    summary = BaselineSummary(
        vehicle_count=len(work),
        supported_vehicle_count=int(supported.sum()),
        annual_fuel_litres=float(work["annual_fuel_litres"].sum()),
        annual_co2_tonnes=float(work["annual_co2_kg"].sum() / 1000.0),
        annual_fuel_cost_cad=float(work["annual_fuel_cost"].sum()),
        nrcan_eligible_match_rate=ratings.eligible_match_rate(work),
        excluded_bev_count=int((work["powertrain"] == "bev").sum()),
        excluded_non_powered_count=int((work["powertrain"] == "non_powered").sum()),
        excluded_trailer_count=int((work["powertrain"] == "trailer").sum()),
        excluded_unsupported_count=int(
            ((~supported) & ~work["powertrain"].isin(["bev", "non_powered", "trailer"])).sum()
        ),
    )
    return work, summary
