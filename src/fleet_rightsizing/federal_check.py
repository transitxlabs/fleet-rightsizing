"""Canadian aggregate fuel accounting, not municipal tailpipe validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fleet_rightsizing.data_io import IngestionReceipt, parse_number, row_get, stream_csv_rows


def federal_fleet_factor_check(path: Path) -> dict[str, Any]:
    rows = [row for batch in stream_csv_rows(path, chunk_size=1000) for row in batch]
    receipt = IngestionReceipt()
    dated = []
    for row in rows:
        receipt.observe()
        match = re.fullmatch(r"(?:FY)?(\d{4})(?:-\d{2,4})?", row_get(row, "Fiscal year", "Year"))
        if match:
            dated.append((int(match[1]), row))
        else:
            receipt.reject(
                "unparseable_fiscal_year", "Fiscal year", row_get(row, "Fiscal year", "Year")
            )
    if not dated:
        return {
            "ingestion": receipt.payload(),
            "status": "empty",
            "latest_year": 0,
            "latest_year_rows": 0,
            "compatible_rows": 0,
            "fuels": {},
            "scope": "Unavailable: no fiscal-year rows",
        }
    latest = max(year for year, _ in dated)
    latest_rows = [row for year, row in dated if year == latest]
    fuels: dict[str, dict[str, float]] = {}
    compatible = 0
    for row in latest_rows:
        fuel = row_get(row, "Fuel type").lower()
        fleet = row_get(row, "Fleet type").lower()
        litres = parse_number(row_get(row, "Fuel consumption (L)")) or 0
        kt = parse_number(row_get(row, "Emissions (kt)"))
        if (
            fuel not in {"gasoline", "diesel", "diesel (#2 oil)"}
            or fleet != "on-road vehicles"
            or row_get(row, "GHG scope") != "1"
            or litres <= 0
            or kt is None
        ):
            continue
        fuel = "diesel" if fuel.startswith("diesel") else fuel
        item = fuels.setdefault(fuel, {"litres": 0.0, "emissions_kt": 0.0, "rows": 0.0})
        item["litres"] += litres
        item["emissions_kt"] += kt
        item["rows"] += 1
        compatible += 1
    # Comparison only within fuel; source reports GHG, so retain CO2e units.
    references = {"gasoline": 2.3, "diesel": 2.7}
    for fuel, item in fuels.items():
        item["kg_co2e_per_l"] = item["emissions_kt"] * 1_000_000 / item["litres"]
        item["illustrative_co2_kg_per_l"] = references[fuel]
        item["difference_kg_per_l"] = item["kg_co2e_per_l"] - references[fuel]
    return {
        "ingestion": receipt.payload(),
        "status": "ok" if compatible else "empty",
        "latest_year": latest,
        "latest_year_rows": len(latest_rows),
        "compatible_rows": compatible,
        "excluded_rows": len(latest_rows) - compatible,
        "fuels": fuels,
        "scope": "Scope 1 on-road gasoline/diesel only; source CO2e versus illustrative CO2 "
        "factors (2.3/2.7 kg/L); rounding, blends and non-CO2 gases prevent validation",
    }
