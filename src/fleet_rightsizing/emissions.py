"""NRCan fuel ratings and BEV catalogue matching."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from fleet_rightsizing.data_io import (
    DataError,
    IngestionReceipt,
    canonical_make,
    normalize_make,
    normalize_model,
    require_csv_columns,
    stream_csv_rows,
)

MATCH_PROVENANCES = frozenset(
    {"exact", "year_adjacent", "fuzzy", "class_mean", "generic", "not_applicable"}
)
ELIGIBLE_MATCH_PROVENANCES = frozenset({"exact", "year_adjacent", "fuzzy"})


@dataclass(frozen=True)
class EmissionFactors:
    combined_l_per_100km: float
    co2_g_per_km: float
    fuel_type: str
    vehicle_class: str
    matched: bool
    provenance: str
    estimate_supported: bool
    co2_low: float = 0.0
    co2_high: float = 0.0


@dataclass(frozen=True)
class BevOption:
    make: str
    model: str
    model_year: int
    vehicle_class: str
    range_km: float
    combined_kwh_per_100km: float


STANDARD_TO_NRCAN_CLASS: dict[str, str] = {
    "SEDAN": "Compact",
    "SUV": "Sport utility vehicle: Small",
    "VAN": "Minivan",
    "TRUCK": "Pickup truck: Standard",
    "PICKUP": "Pickup truck: Standard",
}


NRCAN_CLASSES = frozenset(
    {
        "Compact",
        "Subcompact",
        "Minicompact",
        "Mid-size",
        "Full-size",
        "Two-seater",
        "Sport utility vehicle: Small",
        "Sport utility vehicle: Standard",
        "Pickup truck: Standard",
        "Pickup truck: Small",
        "Special purpose vehicle",
        "Minivan",
        "Station wagon: Small",
        "Station wagon: Mid-size",
        "Van: Passenger",
    }
)


def _sequential_mean(values: Iterable[float]) -> float:
    """Retain source-order float addition used by the Python 3.11 publication.

    Python 3.12 changed float sum() to compensated summation. Explicit additions
    preserve the published factor bits across both supported Python versions.
    Callers supply nonempty groups in the frozen catalogue order.
    """
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count


class RatingsIndex:
    """In-memory index built by streaming NRCan CSV once."""

    def __init__(self) -> None:
        self.ingestion: dict[str, dict[str, object]] = {}
        self._ice: dict[tuple[int, str, str], list[EmissionFactors]] = {}
        self._bev: dict[str, list[BevOption]] = {}
        self._class_means: dict[str, EmissionFactors] = {}

    @classmethod
    def from_files(cls, ratings_path: Path, bev_path: Path) -> RatingsIndex:
        require_csv_columns(
            ratings_path,
            {
                "Model year",
                "Make",
                "Model",
                "Vehicle class",
                "Fuel type",
                "Combined (L/100 km)",
                "CO2 emissions (g/km)",
            },
        )
        require_csv_columns(
            bev_path,
            {"Model year", "Make", "Model", "Vehicle class", "Range (km)", "Combined (kWh/100 km)"},
        )
        index = cls()
        index._load_ratings(ratings_path)
        index._load_bev(bev_path)
        index._compute_class_means()
        return index

    def _compute_class_means(self) -> None:
        by_class: dict[str, list[EmissionFactors]] = {}
        for variants in self._ice.values():
            for factors in variants:
                by_class.setdefault(factors.vehicle_class, []).append(factors)
        for vehicle_class, items in by_class.items():
            combined = _sequential_mean(i.combined_l_per_100km for i in items)
            co2 = _sequential_mean(i.co2_g_per_km for i in items)
            self._class_means[vehicle_class] = EmissionFactors(
                combined_l_per_100km=combined,
                co2_g_per_km=co2,
                fuel_type="class_mean",
                vehicle_class=vehicle_class,
                matched=False,
                provenance="class_mean",
                estimate_supported=True,
                co2_low=min(i.co2_g_per_km for i in items),
                co2_high=max(i.co2_g_per_km for i in items),
            )

    def _load_ratings(self, path: Path) -> None:
        receipt = IngestionReceipt()
        for batch in stream_csv_rows(path, chunk_size=2000):
            for row in batch:
                receipt.observe()
                year_raw = row.get("Model year", "")
                try:
                    year = int(float(year_raw))
                except (ValueError, OverflowError):
                    receipt.reject("unparseable_year", "Model year", year_raw)
                    continue
                make = normalize_make(row.get("Make", ""))
                model = normalize_model(row.get("Model", ""))
                combined = row.get("Combined (L/100 km)", "")
                co2 = row.get("CO2 emissions (g/km)", "")
                try:
                    combined_f = float(combined)
                    co2_f = float(co2)
                except (ValueError, OverflowError):
                    receipt.reject("unparseable_factors", "combined/co2", f"{combined}/{co2}")
                    continue
                vehicle_class = row.get("Vehicle class", "").strip()
                vehicle_class = {"Standard pickup truck": "Pickup truck: Standard"}.get(
                    vehicle_class, vehicle_class
                )
                if vehicle_class not in NRCAN_CLASSES:
                    raise DataError(f"Unknown NRCan class: {vehicle_class}")
                key = (year, make, model)
                self._ice.setdefault(key, []).append(
                    EmissionFactors(
                        combined_l_per_100km=combined_f,
                        co2_g_per_km=co2_f,
                        fuel_type=row.get("Fuel type", ""),
                        vehicle_class=vehicle_class,
                        matched=True,
                        provenance="exact",
                        estimate_supported=True,
                        co2_low=co2_f,
                        co2_high=co2_f,
                    )
                )
        self.ingestion["nrcan_ratings"] = receipt.payload()

    def _load_bev(self, path: Path) -> None:
        receipt = IngestionReceipt()
        for batch in stream_csv_rows(path, chunk_size=2000):
            for row in batch:
                receipt.observe()
                try:
                    year = int(float(row.get("Model year", "0")))
                    range_km = float(row.get("Range (km)", "0"))
                    kwh = float(row.get("Combined (kWh/100 km)", "0"))
                except (ValueError, OverflowError):
                    receipt.reject(
                        "unparseable_bev_numbers",
                        "year/range/kwh",
                        "/".join(
                            row.get(k, "")
                            for k in ("Model year", "Range (km)", "Combined (kWh/100 km)")
                        ),
                    )
                    continue
                vehicle_class = row.get("Vehicle class", "Unknown")
                option = BevOption(
                    make=row.get("Make", ""),
                    model=row.get("Model", ""),
                    model_year=year,
                    vehicle_class=vehicle_class,
                    range_km=range_km,
                    combined_kwh_per_100km=kwh,
                )
                self._bev.setdefault(vehicle_class, []).append(option)
        self.ingestion["nrcan_bev"] = receipt.payload()

    def lookup(
        self,
        year: int,
        make: str,
        model: str,
        standard_type: str = "OTHER",
        *,
        estimate_supported: bool = True,
        fuel_type: str = "",
    ) -> EmissionFactors:
        if not estimate_supported:
            return EmissionFactors(
                combined_l_per_100km=0.0,
                co2_g_per_km=0.0,
                fuel_type="unsupported",
                vehicle_class="Unsupported",
                matched=False,
                provenance="not_applicable",
                estimate_supported=False,
            )
        norm_make = canonical_make(make)
        norm_model = normalize_model(model)
        if norm_model:
            for delta in (0, -1, 1):
                key = (year + delta, norm_make, norm_model)
                if key in self._ice:
                    provenance = "exact" if delta == 0 else "year_adjacent"
                    return self._variant_mean(self._ice[key], provenance, fuel_type)
            for delta in (0, -1, 1):
                prefix = (year + delta, norm_make)
                for (y, mk, md), variants in self._ice.items():
                    if (y, mk) == prefix and (
                        norm_model.startswith(md) or md.startswith(norm_model.split()[0])
                    ):
                        return self._variant_mean(variants, "fuzzy", fuel_type)
        nrcan_class = STANDARD_TO_NRCAN_CLASS.get(standard_type)
        if nrcan_class and nrcan_class in self._class_means:
            factor = self._class_means[nrcan_class]
            if not fuel_type:
                return factor
            codes = {"D"} if fuel_type.upper() in {"DSL", "DIESEL"} else {"X", "Z"}
            items = [
                f
                for variants in self._ice.values()
                for f in variants
                if f.vehicle_class == nrcan_class and f.fuel_type in codes
            ]
            if items:
                return replace(
                    factor,
                    combined_l_per_100km=_sequential_mean(f.combined_l_per_100km for f in items),
                    co2_g_per_km=_sequential_mean(f.co2_g_per_km for f in items),
                    co2_low=min(f.co2_g_per_km for f in items),
                    co2_high=max(f.co2_g_per_km for f in items),
                )
        return EmissionFactors(
            combined_l_per_100km=0.0,
            co2_g_per_km=0.0,
            fuel_type="unknown",
            vehicle_class="Unknown",
            matched=False,
            provenance="generic",
            estimate_supported=False,
        )

    def _variant_mean(
        self, variants: list[EmissionFactors], provenance: str, fuel_type: str
    ) -> EmissionFactors:
        fuel = fuel_type.upper()
        codes = {"D"} if fuel in {"DSL", "DIESEL"} else {"X", "Z"}
        compatible = [f for f in variants if not fuel or f.fuel_type in codes]
        if not compatible:
            return replace(
                variants[0],
                matched=False,
                provenance="not_applicable",
                estimate_supported=False,
                combined_l_per_100km=0,
                co2_g_per_km=0,
                co2_low=0,
                co2_high=0,
            )
        return replace(
            compatible[0],
            provenance=provenance,
            combined_l_per_100km=_sequential_mean(f.combined_l_per_100km for f in compatible),
            co2_g_per_km=_sequential_mean(f.co2_g_per_km for f in compatible),
            co2_low=min(f.co2_g_per_km for f in compatible),
            co2_high=max(f.co2_g_per_km for f in compatible),
        )

    def best_bev(self, vehicle_class: str, min_range: float) -> BevOption | None:
        options = self._bev.get(vehicle_class, [])
        eligible = [o for o in options if o.range_km >= min_range]
        if not eligible:
            return None
        return min(eligible, key=lambda o: o.combined_kwh_per_100km)

    def eligible_match_rate(self, records: pd.DataFrame, light_duty_only: bool = True) -> float:
        if records.empty or "match_provenance" not in records.columns:
            return 0.0
        subset = records
        if light_duty_only and "standard_type" in records.columns:
            subset = records[records["standard_type"].isin(["SEDAN", "SUV", "VAN", "TRUCK"])]
            if "light_duty_scope" in subset:
                subset = subset[subset["light_duty_scope"] & subset["emissions_supported"]]
        if subset.empty:
            return 0.0
        eligible = subset["match_provenance"].isin(ELIGIBLE_MATCH_PROVENANCES)
        return float(eligible.sum()) / float(len(subset))

    def provenance_counts(self, records: pd.DataFrame) -> dict[str, int]:
        if records.empty or "match_provenance" not in records.columns:
            return {}
        counts = records["match_provenance"].value_counts()
        return {str(k): int(v) for k, v in counts.items()}
