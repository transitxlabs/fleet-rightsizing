from __future__ import annotations

from fleet_rightsizing.baseline import load_laval_fleet
from fleet_rightsizing.plan import reallocation_candidates
from tests.conftest import FIXTURES


def test_load_laval_fleet() -> None:
    df = load_laval_fleet(FIXTURES / "laval_sample.csv")
    assert len(df) == 1
    assert df.iloc[0]["make"] == "FORD"


def test_reallocation_candidates() -> None:
    import pandas as pd

    fleet = pd.DataFrame(
        {
            "department": ["A", "A", "A"],
            "standard_type": ["SUV", "SUV", "SEDAN"],
            "illustrative_underutilized": [True, True, False],
        }
    )
    groups = reallocation_candidates(fleet)
    assert groups.iloc[0]["illustrative_flag_count"] == 2
