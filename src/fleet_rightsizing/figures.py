"""Figure generation."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from fleet_rightsizing.utilization import diagnostic_cohort


def plot_ghg_by_department(fleet: pd.DataFrame, output: Path) -> Path:
    supported = fleet[fleet["estimate_supported"]]
    grouped = (
        supported.groupby("match_provenance" if "match_provenance" in supported else "department")[
            "annual_co2_kg"
        ]
        .sum()
        .sort_values(ascending=False)
        .head(15)
    )
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
    cohort = diagnostic_cohort(fleet)
    ax.hist(cohort["annual_km"], bins=40, color="#4a8f5c", edgecolor="white")
    for standard, group in cohort.groupby("standard_type"):
        standard_name = str(standard)
        threshold = float(group["annual_km"].quantile(0.25))
        label = f"{standard_name} 25th pct"
        ax.axvline(threshold, color="#a33", linestyle=":", alpha=0.5, label=label)
    ax.set_xlabel("Simulated proxy annual km (illustrative)")
    ax.set_ylabel("Vehicle count")
    ax.set_title(f"Seattle estimated cohort: {len(cohort):,} simulated records")
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
    low = sensitivity[sensitivity["level"] == "low"].set_index("parameter")
    high = sensitivity[sensitivity["level"] == "high"].set_index("parameter").loc[low.index]
    labels = [str(name).replace("_", " ") for name in low.index]
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hlines(
        labels,
        low["hypothetical_npv_delta_cad"],
        high["hypothetical_npv_delta_cad"],
        color="#555555",
    )
    ax.scatter(
        low["hypothetical_npv_delta_cad"],
        labels,
        marker="o",
        color="#2c6e9b",
        label="Low parameter input",
    )
    ax.scatter(
        high["hypothetical_npv_delta_cad"],
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
