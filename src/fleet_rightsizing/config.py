"""Configuration and analysis assumptions; see dated amendment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(
    os.environ.get("FLEET_RIGHTSIZING_ROOT", Path.cwd()),
)
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_FIGURES_DIR = PROJECT_ROOT / "figures"

ANALYSIS_YEAR = 2026

# Illustrative cost assumptions (CAD); not quotes or fleet-specific capital
GASOLINE_PRICE = 1.65
DIESEL_PRICE = 1.75
ELECTRICITY_PRICE = 0.14
DISCOUNT_RATE = 0.05
HORIZON_YEARS = 10
ICE_MAINTENANCE_PER_KM = 0.05
BEV_MAINTENANCE_PER_KM = 0.03
CHARGER_AMORTIZATION = 3500.0
ICE_REPLACEMENT_COST = 35000.0
BEV_PURCHASE_COST = 45000.0
USD_TO_CAD = 1.35
MIN_BEV_RANGE_KM = 200
ZEV_TAILPIPE_REDUCTION = 1.0

# Composite score weights (frozen analysis specification)
WEIGHT_UTILIZATION = 0.4
WEIGHT_AGE = 0.3
WEIGHT_EMISSIONS = 0.3

# Utilization
TORONTO_KM_THRESHOLD = 5000
BOOTSTRAP_SAMPLES = 500
BOOTSTRAP_SEED = 42
MATCH_RATE_THRESHOLD = 0.5
BOOTSTRAP_WIDTH_THRESHOLD = 0.4
MEMORY_LIMIT_MB = 12_000

# Data URLs (public, verified 2026-10-01)
DATA_URLS: dict[str, str] = {
    "seattle_fleet": ("https://data.seattle.gov/api/views/enxu-fgzb/rows.csv?accessType=DOWNLOAD"),
    "nyc_efficiency": (
        "https://data.cityofnewyork.us/api/v3/views/mn2p-34if/export.csv?accessType=DOWNLOAD"
    ),
    "laval_fleet": (
        "https://www.donneesquebec.ca/recherche/dataset/"
        "d866cf2f-9a68-49ba-9825-41c9872d55cb/resource/"
        "3e8045d4-7562-4bb1-9889-3b8c0af5f110/download/vehicule-equipement.csv"
    ),
    "nrcan_ratings": (
        "https://open.canada.ca/data/dataset/98f1a129-f628-4ce4-b24d-6f16bf24dd64/"
        "resource/c98b9dc8-b23f-4cd8-8b19-e892da1e4688/download/"
        "my2015-2024-fuel-consumption-ratings.csv"
    ),
    "nrcan_bev": (
        "https://open.canada.ca/data/dataset/98f1a129-f628-4ce4-b24d-6f16bf24dd64/"
        "resource/026e45b4-eb63-451f-b34f-d9308ea3a3d9/download/"
        "my2012-2026-battery-electric-vehicles.csv"
    ),
    "federal_fleet_fuel": (
        "https://open.canada.ca/data/dataset/6bed41cd-9816-4912-a2b8-b0b224909396/"
        "resource/95cd8311-59ac-4f6d-aeec-b434ab860a51/download/"
        "3.-2024-25-fuel-use-and-emissions-fleet-en.csv"
    ),
}


@dataclass(frozen=True)
class SensitivityRange:
    low: float
    high: float


SENSITIVITY: dict[str, SensitivityRange] = {
    "gasoline_price": SensitivityRange(1.40, 1.90),
    "diesel_price": SensitivityRange(1.50, 2.00),
    "electricity_price": SensitivityRange(0.10, 0.20),
    "discount_rate": SensitivityRange(0.03, 0.07),
    "ice_maintenance": SensitivityRange(0.03, 0.08),
    "bev_maintenance": SensitivityRange(0.02, 0.05),
}
