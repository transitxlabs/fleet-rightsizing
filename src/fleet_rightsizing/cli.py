"""Command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from fleet_rightsizing.pipeline import run_pipeline

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Municipal fleet rightsizing analysis on public open data",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory for cached CSV downloads",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Results output directory",
    )
    parser.add_argument(
        "--figures",
        type=Path,
        default=None,
        help="Figures output directory",
    )
    args = parser.parse_args()
    payload = run_pipeline(
        data_dir=args.data_dir,
        results_dir=args.output,
        figures_dir=args.figures,
    )
    console.print("[green]Pipeline complete[/green]")
    console.print(payload["evaluation"])


if __name__ == "__main__":
    main()
