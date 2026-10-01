from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from fleet_rightsizing.config import SENSITIVITY
from fleet_rightsizing.tco import hypothetical_cost_case

ROOT = Path(__file__).resolve().parents[1]


def test_finding_9_rendered_pages_route() -> None:
    url = "https://transitxlabs.github.io/fleet-rightsizing/"
    readme = (ROOT / "README.md").read_text()
    assert f"]({url})" in readme
    assert "GitHub Pages build of `docs/`" in readme
    assert "when the repository is published" in readme
    assert "Fleet savings and operational recommendations are withheld" in readme
    config = yaml.safe_load((ROOT / "mkdocs.yml").read_text())
    assert config["site_url"] == url
    assert config["docs_dir"] == "docs"
    assert "milestones/**" in config["exclude_docs"]
    workflow = yaml.safe_load((ROOT / ".github/workflows/pages.yml").read_text())
    build = workflow["jobs"]["build"]
    assert any(step.get("run") == "mkdocs build --strict" for step in build["steps"])
    upload = next(
        step for step in build["steps"] if "upload-pages-artifact" in step.get("uses", "")
    )
    assert upload["with"]["path"] == "site"
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "build"
    assert deploy["environment"]["name"] == "github-pages"
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert any("deploy-pages" in step.get("uses", "") for step in deploy["steps"])


def test_finding_9_chart_uses_only_synthetic_sensitivity(tmp_path: Path) -> None:
    from fleet_rightsizing.figures import plot_fictional_sensitivity

    rows = [
        {
            "parameter": name,
            "level": label,
            "value": value,
            **hypothetical_cost_case(**{name: value}),
        }
        for name, span in SENSITIVITY.items()
        for label, value in (("low", span.low), ("high", span.high))
    ]
    # Shuffled inputs exercise pairing by parameter rather than source row order.
    sensitivity = pd.DataFrame(rows).sample(frac=1, random_state=42)
    captured = []
    subplots = plt.subplots

    def capture(*args, **kwargs):
        fig, ax = subplots(*args, **kwargs)
        captured.append(ax)
        return fig, ax

    with patch("fleet_rightsizing.figures.plt.subplots", side_effect=capture):
        output = plot_fictional_sensitivity(sensitivity, tmp_path / "synthetic.png")
    assert output.read_bytes().startswith(b"\x89PNG")
    ax = captured[0]
    parameters = sensitivity.loc[sensitivity.level == "low", "parameter"].tolist()
    assert [tick.get_text() for tick in ax.get_yticklabels()] == [
        name.replace("_", " ") for name in parameters
    ]
    for collection, level in zip(ax.collections[1:], ("low", "high"), strict=True):
        expected = [
            hypothetical_cost_case(**{name: getattr(SENSITIVITY[name], level)})[
                "hypothetical_npv_delta_cad"
            ]
            for name in parameters
        ]
        np.testing.assert_allclose(collection.get_offsets()[:, 0], expected)
    assert "Synthetic" in ax.get_title() and "not municipal fleet savings" in ax.get_title()
    for directory in (ROOT / "figures", ROOT / "docs/figures"):
        assert not (directory / "scenario_tco_savings.png").exists()
