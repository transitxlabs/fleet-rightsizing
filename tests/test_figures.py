from __future__ import annotations

from pathlib import Path

import pandas as pd

from fleet_rightsizing.figures import (
    plot_fictional_sensitivity,
    plot_ghg_by_department,
    plot_utilization_distribution,
)


def test_figure_helpers(tmp_path: Path) -> None:
    fleet = pd.DataFrame(
        {
            "department": ["A", "A", "B"],
            "annual_co2_kg": [100.0, 200.0, 50.0],
            "annual_km": [1000.0, 2000.0, 500.0],
            "vehicle_id": ["1", "2", "3"],
            "estimate_supported": [True, True, True],
            "standard_type": ["SUV", "SUV", "SEDAN"],
        }
    )
    sensitivity = pd.DataFrame(
        {
            "parameter": ["gasoline_price", "gasoline_price"],
            "level": ["low", "high"],
            "hypothetical_npv_delta_cad": [-1000.0, 500.0],
        }
    )
    assert plot_ghg_by_department(fleet, tmp_path / "ghg.png").exists()
    assert plot_utilization_distribution(fleet, tmp_path / "util.png").exists()
    assert plot_fictional_sensitivity(sensitivity, tmp_path / "sav.png").exists()
