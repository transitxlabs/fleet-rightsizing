"""Figure generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fleet_rightsizing.utilization import diagnostic_cohort

FIGURE_DIMENSIONS = {
    "ghg_by_department.png": (1500, 900),
    "utilization_proxy.png": (1200, 750),
    "fictional_sensitivity.png": (1500, 900),
}


def source_bytes(data: dict[str, Any]) -> bytes:
    """Canonical UTF-8 record of the actual plotted values, without run observations."""
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_source(output: Path, data: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".data.json").write_bytes(source_bytes(data))


def ghg_source(fleet: pd.DataFrame) -> dict[str, Any]:
    supported = fleet[fleet["estimate_supported"]]
    grouped = (
        supported.groupby("match_provenance" if "match_provenance" in supported else "department")[
            "annual_co2_kg"
        ]
        .sum()
        .sort_values(ascending=False)
        .head(15)
    )
    return {"labels": grouped.index.tolist(), "annual_co2_kg": grouped.tolist()}


def utilization_source(fleet: pd.DataFrame) -> dict[str, Any]:
    cohort = diagnostic_cohort(fleet)
    counts, edges = np.histogram(cohort["annual_km"], bins=40)
    return {
        "annual_km": cohort["annual_km"].tolist(),
        "histogram_counts": counts.tolist(),
        "bin_edges": edges.tolist(),
        "quartile_thresholds": [
            {"standard_type": str(standard), "annual_km": float(group["annual_km"].quantile(0.25))}
            for standard, group in cohort.groupby("standard_type")
        ],
    }


def sensitivity_source(sensitivity: pd.DataFrame) -> dict[str, Any]:
    low = sensitivity[sensitivity["level"] == "low"].set_index("parameter")
    high = sensitivity[sensitivity["level"] == "high"].set_index("parameter").loc[low.index]
    return {
        "labels": [str(name).replace("_", " ") for name in low.index],
        "low_npv_delta_cad": low["hypothetical_npv_delta_cad"].tolist(),
        "high_npv_delta_cad": high["hypothetical_npv_delta_cad"].tolist(),
    }


def figure_sources(fleet: pd.DataFrame, sensitivity: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {
        "ghg_by_department.png": ghg_source(fleet),
        "utilization_proxy.png": utilization_source(fleet),
        "fictional_sensitivity.png": sensitivity_source(sensitivity),
    }


def plot_ghg_by_department(fleet: pd.DataFrame, output: Path) -> Path:
    data = ghg_source(fleet)
    write_source(output, data)
    grouped = pd.Series(data["annual_co2_kg"], index=data["labels"])
    fig, ax = plt.subplots(figsize=(10, 6))
    grouped.plot(kind="barh", ax=ax, color="#2c6e9b")
    ax.set_xlabel("Annual tailpipe CO2 (kg)")
    ax.set_ylabel("Factor provenance (catalogue matches have unresolved variants)")
    ax.set_title("Simulated light-duty tailpipe CO2 by factor provenance")
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_utilization_distribution(fleet: pd.DataFrame, output: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5))
    data = utilization_source(fleet)
    write_source(output, data)
    ax.hist(data["annual_km"], bins=data["bin_edges"], color="#4a8f5c", edgecolor="white")
    for item in data["quartile_thresholds"]:
        standard_name = item["standard_type"]
        threshold = item["annual_km"]
        label = f"{standard_name} 25th pct"
        ax.axvline(threshold, color="#a33", linestyle=":", alpha=0.5, label=label)
    ax.set_xlabel("Simulated proxy annual km (illustrative)")
    ax.set_ylabel("Vehicle count")
    ax.set_title(f"Seattle estimated cohort: {len(data['annual_km']):,} simulated records")
    handles, labels = ax.get_legend_handles_labels()
    if labels:
        ax.legend(handles, labels)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_fictional_sensitivity(sensitivity: pd.DataFrame, output: Path) -> Path:
    """Plot synthetic two-vehicle cash flows; never ingest public asset rankings."""
    data = sensitivity_source(sensitivity)
    write_source(output, data)
    labels = data["labels"]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hlines(
        labels,
        data["low_npv_delta_cad"],
        data["high_npv_delta_cad"],
        color="#555555",
    )
    ax.scatter(
        data["low_npv_delta_cad"],
        labels,
        marker="o",
        color="#2c6e9b",
        label="Low parameter input",
    )
    ax.scatter(
        data["high_npv_delta_cad"],
        labels,
        marker="s",
        color="#a34f18",
        label="High parameter input",
    )
    ax.axvline(0, color="#777777", linestyle=":")
    ax.set_xlabel("Fictional two-vehicle ICE minus BEV 10-year NPV (CAD)")
    ax.set_ylabel("One economic input varied at a time; all others fixed")
    ax.set_title("Synthetic sensitivity illustration; not municipal fleet savings")
    ax.legend()
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output
