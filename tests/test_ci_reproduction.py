"""Exact analytical and figure-data contracts, independent of raster rendering."""

from __future__ import annotations

import json
import runpy
import shutil
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from fleet_rightsizing.figures import (
    FIGURE_DIMENSIONS,
    figure_sources,
    plot_fictional_sensitivity,
    plot_ghg_by_department,
    plot_utilization_distribution,
    source_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKS = runpy.run_path(str(ROOT / "scripts/publication_checks.py"))


@pytest.fixture
def releases(tmp_path: Path) -> tuple[Path, Path]:
    roots = (tmp_path / "reference", tmp_path / "candidate")
    for root in roots:
        root.mkdir()
        for directory in ("results", "figures", "docs/figures"):
            shutil.copytree(ROOT / directory, root / directory)
        for name in ("README.md", "RESULTS.md", "docs/results.md"):
            shutil.copyfile(ROOT / name, root / name)
    return roots


@pytest.mark.parametrize("name", FIGURE_DIMENSIONS)
def test_rendering_difference_with_identical_data_passes(releases, name):
    reference, candidate = releases
    path = candidate / "figures" / name
    with Image.open(path) as original:
        image = original.convert("RGB")
    # Change actual raster pixels, not just PNG metadata or compression.
    image.putpixel((0, 0), (17, 31, 47))
    image.save(path)
    shutil.copyfile(path, candidate / "docs/figures" / name)
    assert path.read_bytes() != (reference / "figures" / name).read_bytes()
    receipt = CHECKS["compare_release"](reference, candidate)
    assert receipt["png"][name]["source_byte_equal"]
    assert not receipt["png"][name]["raster_byte_equal"]


@pytest.mark.parametrize("name", FIGURE_DIMENSIONS)
def test_changed_figure_source_is_rejected(releases, name):
    reference, candidate = releases
    sidecar = candidate / "figures" / Path(name).with_suffix(".data.json")
    data = json.loads(sidecar.read_bytes())
    field = {
        "ghg_by_department.png": "annual_co2_kg",
        "utilization_proxy.png": "annual_km",
        "fictional_sensitivity.png": "low_npv_delta_cad",
    }[name]
    data[field][0] += 0.000001
    sidecar.write_bytes(source_bytes(data))
    with pytest.raises(AssertionError, match="figure source data changed"):
        CHECKS["compare_figures"](reference, candidate)


@pytest.mark.parametrize("name", FIGURE_DIMENSIONS)
def test_identical_but_stale_figure_sources_are_rejected(releases, name):
    reference, candidate = releases
    for root in (reference, candidate):
        sidecar = root / "figures" / Path(name).with_suffix(".data.json")
        data = json.loads(sidecar.read_bytes())
        data["labels" if "labels" in data else "histogram_counts"][0] = "changed"
        sidecar.write_bytes(source_bytes(data))
    with pytest.raises(AssertionError, match="disagrees with analytical CSVs"):
        CHECKS["compare_figures"](reference, candidate)


@pytest.mark.parametrize("defect", ["corrupt", "truncated", "dimensions", "format", "missing"])
def test_invalid_image_is_rejected(releases, defect):
    reference, candidate = releases
    path = candidate / "figures/ghg_by_department.png"
    if defect == "corrupt":
        path.write_bytes(b"not an image")
    elif defect == "truncated":
        path.write_bytes(path.read_bytes()[:100])
    elif defect == "dimensions":
        Image.new("RGB", (10, 10)).save(path)
    elif defect == "format":
        Image.new("RGB", (1500, 900)).save(path, format="JPEG")
    else:
        path.unlink()
    with pytest.raises((AssertionError, OSError, SyntaxError)):
        CHECKS["compare_figures"](reference, candidate)


def test_documentation_image_must_match_generated_image(releases):
    reference, candidate = releases
    Image.new("RGB", (1500, 900)).save(candidate / "docs/figures/ghg_by_department.png")
    with pytest.raises(AssertionError, match="documentation image differs"):
        CHECKS["compare_figures"](reference, candidate)


def test_analytical_json_rejects_formerly_tolerated_change():
    with pytest.raises(AssertionError, match="co2"):
        CHECKS["compare_payloads"]({"co2": 3.0}, {"co2": 3.0 + 1e-12})


def test_analytical_csv_requires_exact_bytes(releases):
    reference, candidate = releases
    path = candidate / "results/sensitivity.csv"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(AssertionError, match="analytical CSV bytes changed"):
        CHECKS["compare_release"](reference, candidate)


def test_generated_tables_require_exact_values(releases):
    reference, candidate = releases
    for name in ("RESULTS.md", "docs/results.md"):
        path = candidate / name
        path.write_text(path.read_text().replace("3,012.7", "3,012.8"))
    with pytest.raises(AssertionError, match="Results changed"):
        CHECKS["compare_release"](reference, candidate)


def test_renderers_export_the_data_they_consume(tmp_path):
    fleet = pd.read_csv(ROOT / "results/seattle_scored.csv", float_precision="round_trip")
    sensitivity = pd.read_csv(ROOT / "results/sensitivity.csv", float_precision="round_trip")
    sources = figure_sources(fleet, sensitivity)
    for name, render, data in (
        ("ghg_by_department.png", plot_ghg_by_department, fleet),
        ("utilization_proxy.png", plot_utilization_distribution, fleet),
        ("fictional_sensitivity.png", plot_fictional_sensitivity, sensitivity),
    ):
        output = render(data, tmp_path / name)
        assert output.with_suffix(".data.json").read_bytes() == source_bytes(sources[name])
        with Image.open(output) as image:
            assert image.size == FIGURE_DIMENSIONS[name]
            image.load()



@pytest.mark.parametrize("name", FIGURE_DIMENSIONS)
def test_changed_analytical_input_changes_figure_source(releases, name):
    reference, candidate = releases
    fleet_path = candidate / "results/seattle_scored.csv"
    sensitivity_path = candidate / "results/sensitivity.csv"
    fleet = pd.read_csv(fleet_path, float_precision="round_trip")
    sensitivity = pd.read_csv(sensitivity_path, float_precision="round_trip")
    row = fleet.index[fleet.estimate_supported][0]
    if name == "ghg_by_department.png":
        fleet.loc[row, "annual_co2_kg"] += 1.0
    elif name == "utilization_proxy.png":
        fleet.loc[row, "annual_km"] += 1.0
    else:
        sensitivity.loc[0, "hypothetical_npv_delta_cad"] += 1.0
    fleet.to_csv(fleet_path, index=False)
    sensitivity.to_csv(sensitivity_path, index=False)
    for figure, data in figure_sources(fleet, sensitivity).items():
        sidecar = candidate / "figures" / Path(figure).with_suffix(".data.json")
        sidecar.write_bytes(source_bytes(data))
    with pytest.raises(AssertionError, match=f"{name}: figure source data changed"):
        CHECKS["compare_figures"](reference, candidate)


@pytest.mark.parametrize("changed", [3, True])
def test_analytical_json_preserves_numeric_types(changed):
    with pytest.raises(AssertionError):
        CHECKS["compare_payloads"]({"co2": 3.0}, {"co2": changed})
