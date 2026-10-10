"""Rating averages retain the arithmetic used by the published results."""

from pathlib import Path

import pytest

from fleet_rightsizing.emissions import RatingsIndex
from tests.conftest import FIXTURES


@pytest.mark.parametrize("route", ["class_mean", "fuel_class_mean", "variant_mean"])
def test_rating_means_preserve_published_float_values(tmp_path: Path, route: str) -> None:
    ratings = tmp_path / "ratings.csv"
    ratings.write_text(
        "Model year,Make,Model,Vehicle class,Fuel type,Combined (L/100 km),"
        "CO2 emissions (g/km)\n"
        "2024,TEST,MODEL,Compact,X,8.1,181.1\n"
        "2024,TEST,MODEL,Compact,X,8.2,182.2\n"
        "2024,TEST,MODEL,Compact,X,8.3,183.3\n",
        encoding="utf-8",
    )
    index = RatingsIndex.from_files(ratings, FIXTURES / "nrcan_bev_sample.csv")
    if route == "variant_mean":
        factors = index.lookup(2024, "TEST", "MODEL", "SEDAN", fuel_type="UNL")
    else:
        factors = index.lookup(
            1900, "UNKNOWN", "", "SEDAN", fuel_type="UNL" if route == "fuel_class_mean" else ""
        )
    # Exact binary floats from source-order accumulation in the publication runtime.
    assert factors.combined_l_per_100km == 8.2
    assert factors.co2_g_per_km == 182.19999999999996
    assert factors.co2_low == 181.1
    assert factors.co2_high == 183.3
