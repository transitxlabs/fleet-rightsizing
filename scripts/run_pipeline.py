#!/usr/bin/env python3
"""Regenerate all numbers and figures."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from fleet_rightsizing.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate fleet-rightsizing results")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Results output directory (default: ./results)",
    )
    parser.add_argument(
        "--figures",
        type=Path,
        default=None,
        help="Figures output directory (default: ./figures)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Cached dataset directory (default: ./data/raw)",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("FLEET_RIGHTSIZING_ROOT", str(root))
    results_dir = args.output or root / "results"
    figures_dir = args.figures or root / "figures"
    run_pipeline(
        data_dir=args.data_dir or root / "data" / "raw",
        results_dir=results_dir,
        figures_dir=figures_dir,
    )


if __name__ == "__main__":
    main()
