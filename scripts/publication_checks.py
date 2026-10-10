#!/usr/bin/env python3
"""Bounded local publication-history audit and cross-version analytical comparison."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image

from fleet_rightsizing.figures import FIGURE_DIMENSIONS, figure_sources, source_bytes

OBSERVATIONS = {"timings_seconds", "stage_memory_mb", "peak_memory_mb", "environment"}
EXCLUDED = {
    ".review",
    ".venv",
    "site",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}


def analytical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove only declared run observations; hashes/counts and gate results stay."""
    result = {key: value for key, value in payload.items() if key not in OBSERVATIONS}
    result["inputs"] = {
        name: {key: value for key, value in item.items() if key != "observed_at_utc"}
        for name, item in payload.get("inputs", {}).items()
    }
    return result


def compare_values(reference: Any, candidate: Any, path: str = "root") -> None:
    if isinstance(reference, dict):
        assert isinstance(candidate, dict) and reference.keys() == candidate.keys(), path
        for key in reference:
            compare_values(reference[key], candidate[key], f"{path}.{key}")
    elif isinstance(reference, list):
        assert isinstance(candidate, list) and len(reference) == len(candidate), path
        for i, (left, right) in enumerate(zip(reference, candidate, strict=True)):
            compare_values(left, right, f"{path}[{i}]")
    elif isinstance(reference, float):
        assert isinstance(candidate, (int, float)) and reference == candidate, (
            f"{path}: {reference} != {candidate}"
        )
    else:
        assert reference == candidate, f"{path}: {reference} != {candidate}"


def compare_payloads(reference: dict[str, Any], candidate: dict[str, Any]) -> None:
    left, right = analytical_payload(reference), analytical_payload(candidate)
    compare_values(left, right)
    assert source_bytes(left) == source_bytes(right), (
        "Analytical JSON bytes changed after normalization"
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excluded_release_path(relative: Path) -> bool:
    """Shared export/inventory boundary; source history stays private and intact."""
    return (
        any(part in EXCLUDED for part in relative.parts)
        or relative.parts[0] == "state"
        or relative.parts[:2] in {("docs", "milestones"), ("data", "raw")}
        or relative.suffix in {".bundle", ".tar"}
        or relative.name in {".coverage", ".DS_Store"}
    )


def export_release(repository: Path, destination: Path) -> dict[str, dict[str, Any]]:
    """Export HEAD's allowed tracked files into a new directory, without its history."""
    destination.mkdir(parents=True, exist_ok=False)
    archive = git(repository, "archive", "HEAD")
    with tarfile.open(fileobj=io.BytesIO(archive)) as handle:
        for member in handle.getmembers():
            relative = Path(member.name)
            if excluded_release_path(relative) or not member.isfile():
                continue
            assert not relative.is_absolute() and ".." not in relative.parts
            content = handle.extractfile(member)
            assert content is not None
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.read())
            target.chmod(member.mode)
    return release_inventory(destination)


def release_inventory(root: Path) -> dict[str, dict[str, Any]]:
    """Inventory a clean export, rejecting caches, bundles and review artifacts."""
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if ".git" in relative.parts or not path.is_file():
            continue
        if excluded_release_path(relative):
            raise ValueError(f"excluded release path: {relative.as_posix()}")
        result[relative.as_posix()] = {"sha256": digest(path), "bytes": path.stat().st_size}
    return result


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def scan_history(root: Path) -> dict[str, Any]:
    """Scan commits/trees/blobs reachable from every local ref, including other branches.

    No arbitrary encoded-secret guarantee or remote-ref inspection is implied.
    The publication repository must be a fresh import, separate from private history.
    """
    refs = git(root, "for-each-ref", "--format=%(refname)").decode().splitlines()
    objects = git(root, "rev-list", "--objects", "--all").decode().splitlines()
    rules = {
        "prohibited_punctuation": re.compile(chr(0x2014)),
        "home_path": re.compile("/" + "Users/|/" + "home/"),
        "private_key": re.compile("-----BEGIN " + r"(?:[A-Z ]+ )?PRIVATE " + "KEY-----"),
        "coauthor": re.compile("Co-" + "authored-by:", re.I),
        "model_attribution": re.compile(
            "(?:generated|written|authored) by (?:" + "Chat" + "GPT|Cla" + "ude|Open" + "AI)",
            re.I,
        ),
        "credential": re.compile(r"\bAK" + r"IA[A-Z0-9]{16}\b|\bgh" + r"p_[A-Za-z0-9]{36}\b"),
    }
    hits = []
    types: dict[str, int] = {}
    text_records = 0
    for line in objects:
        oid = line.split()[0]
        kind = git(root, "cat-file", "-t", oid).decode().strip()
        types[kind] = types.get(kind, 0) + 1
        if kind not in {"blob", "commit", "tag"}:
            continue
        content = git(root, "cat-file", kind, oid)
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            continue
        text_records += 1
        for name, rule in rules.items():
            if rule.search(decoded):
                hits.append({"object": oid, "rule": name})
    return {
        "refs": refs,
        "objects_scanned": len(objects),
        "object_types": types,
        "utf8_records_scanned": text_records,
        "hits": hits,
        "scope": "all objects reachable from all local refs; bounded pattern scan",
    }


def compare_figures(reference: Path, candidate: Path) -> dict[str, Any]:
    """Compare exact plotted data, bind it to CSVs, and fully decode both PNG copies."""
    sources = {}
    for root in (reference, candidate):
        fleet = pd.read_csv(root / "results/seattle_scored.csv", float_precision="round_trip")
        sensitivity = pd.read_csv(root / "results/sensitivity.csv", float_precision="round_trip")
        sources[root] = figure_sources(fleet, sensitivity)
    receipt = {}
    for name, dimensions in FIGURE_DIMENSIONS.items():
        sidecar = Path(name).with_suffix(".data.json")
        left = (reference / "figures" / sidecar).read_bytes()
        right = (candidate / "figures" / sidecar).read_bytes()
        assert left == right, f"{name}: figure source data changed"
        for root in (reference, candidate):
            assert (root / "figures" / sidecar).read_bytes() == source_bytes(sources[root][name]), (
                f"{name}: figure source data disagrees with analytical CSVs"
            )
            for directory in ("figures", "docs/figures"):
                path = root / directory / name
                with Image.open(path) as picture:
                    assert picture.format == "PNG", f"{name}: expected PNG"
                    assert picture.size == dimensions, f"{name}: unexpected dimensions"
                    picture.verify()
                with Image.open(path) as picture:
                    picture.load()
            assert (root / "figures" / name).read_bytes() == (
                root / "docs/figures" / name
            ).read_bytes(), f"{name}: documentation image differs from generated image"
        receipt[name] = {
            "source_byte_equal": True,
            "source_matches_csv": True,
            "source_sha256": hashlib.sha256(left).hexdigest(),
            "valid_png": True,
            "dimensions": list(dimensions),
            "docs_copy_byte_equal": True,
            "raster_byte_equal": digest(reference / "figures" / name)
            == digest(candidate / "figures" / name),
        }
    return receipt


def compare_release(reference: Path, candidate: Path) -> dict[str, Any]:
    compare_payloads(
        json.loads((reference / "results/results.json").read_text()),
        json.loads((candidate / "results/results.json").read_text()),
    )
    csv_receipt = {}
    for name in (
        "seattle_scored.csv",
        "scenario_ledger.csv",
        "sensitivity.csv",
        "ingestion_rejections.csv",
    ):
        left = pd.read_csv(reference / "results" / name)
        right = pd.read_csv(candidate / "results" / name)
        assert (reference / "results" / name).read_bytes() == (
            candidate / "results" / name
        ).read_bytes(), f"{name}: analytical CSV bytes changed"
        pd.testing.assert_frame_equal(left, right, check_exact=True)
        csv_receipt[name] = {
            "rows": len(left),
            "analytical_equal": True,
            "byte_equal": digest(reference / "results" / name)
            == digest(candidate / "results" / name),
        }
    png_receipt = compare_figures(reference, candidate)
    assert (candidate / "RESULTS.md").read_bytes() == (candidate / "docs/results.md").read_bytes()
    assert (reference / "README.md").read_bytes() == (candidate / "README.md").read_bytes()
    normalize = lambda text: re.sub(  # noqa: E731
        r"(?m)^OS/architecture:.*$",
        "RUN OBSERVATIONS",
        re.sub(r"\d{4}-\d\d-\d\dT[\d:.]+\+00:00", "OBSERVED UTC", text),
    )
    assert normalize((reference / "RESULTS.md").read_text()) == normalize(
        (candidate / "RESULTS.md").read_text()
    ), "Results changed outside declared observations"
    return {
        "analytical_json_equal": True,
        "normalized_analytical_json_byte_equal": True,
        "numeric_tolerance": {"rtol": 0, "atol": 0},
        "csv": csv_receipt,
        "png": png_receipt,
        "readme_byte_equal": True,
        "results_equal_except_observations": True,
        "ignored_json_observations": sorted(OBSERVATIONS) + ["inputs.*.observed_at_utc"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--repository", type=Path, required=True)
    scan.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--reference", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    export = sub.add_parser("export")
    export.add_argument("--repository", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export_release(args.repository, args.destination), indent=2))
    elif args.command == "scan":
        receipt = scan_history(args.repository)
        receipt["tree_inventory"] = release_inventory(args.repository)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({k: v for k, v in receipt.items() if k != "tree_inventory"}, indent=2))
        if receipt["hits"]:
            raise SystemExit(1)
    else:
        print(json.dumps(compare_release(args.reference, args.candidate), indent=2))


if __name__ == "__main__":
    main()
