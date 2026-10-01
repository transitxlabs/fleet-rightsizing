"""Download and cache public datasets."""

from __future__ import annotations

import json
from pathlib import Path

from fleet_rightsizing.config import DATA_URLS, DEFAULT_DATA_DIR
from fleet_rightsizing.data_io import DataError, download_file, sha256_file, verify_sidecar


def _manifest_path(data_dir: Path) -> Path:
    return data_dir.parent / "manifest.json"


def ensure_datasets(data_dir: Path | None = None, *, refresh: bool = False) -> dict[str, Path]:
    root = data_dir or DEFAULT_DATA_DIR
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for key, url in DATA_URLS.items():
        filename = f"{key}.csv"
        dest = root / filename
        if refresh or not dest.exists() or not verify_sidecar(dest):
            download_file(url, dest)
        elif not verify_sidecar(dest):
            msg = f"Cached dataset failed hash verification: {dest.name}"
            raise DataError(msg)
        publication_receipt = root.parent / "publication-inputs.json"
        if publication_receipt.exists() and not refresh:
            expected = json.loads(publication_receipt.read_text())[key]["sha256"]
            if sha256_file(dest) != expected:
                raise DataError(f"Publication input changed: {key}; review an explicit data update")
        paths[key] = dest
    return paths


def load_manifest() -> dict[str, object]:
    path = _manifest_path(DEFAULT_DATA_DIR)
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data
