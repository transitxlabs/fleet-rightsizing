"""Safe data download and streaming CSV helpers."""

from __future__ import annotations

import csv
import hashlib
import re
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_SCHEMES = frozenset({"https"})
URL_HOST_PATTERN = re.compile(
    r"^(data\.seattle\.gov|data\.cityofnewyork\.us|open\.canada\.ca|"
    r"www\.donneesquebec\.ca|opencanada\.blob\.core\.windows\.net)$"
)


@dataclass
class IngestionReceipt:
    """Parser row reconciliation; source_row is a 1-based data-record ordinal."""

    raw_rows: int = 0
    rejected_records: list[dict[str, object]] = field(default_factory=list)

    def observe(self) -> None:
        self.raw_rows += 1

    def reject(self, reason: str, field_name: str, value: str) -> None:
        self.rejected_records.append(
            {
                "source_row": self.raw_rows,
                "reason": reason,
                "field": field_name,
                "value": value,
            }
        )

    def payload(self) -> dict[str, Any]:
        reasons: dict[str, int] = {}
        for row in self.rejected_records:
            reason = str(row["reason"])
            reasons[reason] = reasons.get(reason, 0) + 1
        return {
            "raw_rows": self.raw_rows,
            "loaded_rows": self.raw_rows - len(self.rejected_records),
            "rejected_rows": len(self.rejected_records),
            "rejection_reasons": reasons,
            "rejected_records": self.rejected_records,
        }


class DataError(Exception):
    """Raised when data access fails validation."""


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        msg = f"URL scheme not allowed: {parsed.scheme}"
        raise DataError(msg)
    host = parsed.netloc.lower()
    if not URL_HOST_PATTERN.match(host):
        msg = f"URL host not allowed: {host}"
        raise DataError(msg)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_sidecar(path: Path) -> bool:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists():
        return False
    expected = sidecar.read_text(encoding="utf-8").strip().split()[0]
    return sha256_file(path) == expected


def download_file(url: str, dest: Path, timeout: float = 120.0) -> Path:
    validate_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    total = 0
    with tempfile.NamedTemporaryFile(delete=False, dir=dest.parent, suffix=".part") as tmp:
        tmp_path = Path(tmp.name)
        with httpx.stream("GET", url, follow_redirects=True, timeout=timeout) as response:
            response.raise_for_status()
            final_url = str(response.url)
            validate_url(final_url)
            for chunk in response.iter_bytes(65536):
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    tmp_path.unlink(missing_ok=True)
                    msg = f"Download exceeds size limit: {url}"
                    raise DataError(msg)
                hasher.update(chunk)
                tmp.write(chunk)
    digest = hasher.hexdigest()
    tmp_path.replace(dest)
    sidecar = dest.with_suffix(dest.suffix + ".sha256")
    sidecar.write_text(digest + "\n", encoding="utf-8")
    return dest


def stream_csv_rows(path: Path, chunk_size: int = 5000) -> Iterator[list[dict[str, str]]]:
    """Yield CSV rows in chunks without loading the full file."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        batch: list[dict[str, str]] = []
        for row in reader:
            batch.append({k: (v or "").strip() for k, v in row.items()})
            if len(batch) >= chunk_size:
                yield batch
                batch = []
        if batch:
            yield batch


def count_csv_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def parse_number(value: str) -> float | None:
    cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
    if not cleaned or cleaned.lower() in {"n/a", "na", "-"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_make(value: str) -> str:
    return re.sub(r"\s+", " ", value.upper().strip())


MAKE_ALIASES: dict[str, str] = {
    "TOYT": "TOYOTA",
    "TOYTA": "TOYOTA",
    "CHEV": "CHEVROLET",
    "CHEVY": "CHEVROLET",
    "GMC": "GMC",
    "NISS": "NISSAN",
    "HOND": "HONDA",
    "HYUN": "HYUNDAI",
    "MAZD": "MAZDA",
    "SUBA": "SUBARU",
    "VOLK": "VOLKSWAGEN",
    "VW": "VOLKSWAGEN",
    "MERZ": "MERCEDES-BENZ",
    "MB": "MERCEDES-BENZ",
    "DODG": "DODGE",
    "RAM": "RAM",
    "CHRY": "CHRYSLER",
    "FORD": "FORD",
    "ACUR": "ACURA",
    "BMW": "BMW",
    "AUDI": "AUDI",
    "LEXS": "LEXUS",
    "KIA": "KIA",
}


def canonical_make(value: str) -> str:
    norm = normalize_make(value)
    return MAKE_ALIASES.get(norm, norm)


def normalize_model(value: str) -> str:
    return re.sub(r"\s+", " ", value.upper().strip())


def safe_path(base: Path, name: str) -> Path:
    if ".." in name or name.startswith("/"):
        msg = f"Unsafe path component: {name}"
        raise DataError(msg)
    resolved = (base / name).resolve()
    if base.resolve() not in resolved.parents and resolved != base.resolve():
        msg = f"Path escapes base directory: {name}"
        raise DataError(msg)
    return resolved


def row_get(row: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return str(row[key]).strip()
    return default


def require_csv_columns(path: Path, required: set[str]) -> None:
    """Fail closed on publisher header changes before silently changing estimates."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        columns = set(csv.DictReader(handle).fieldnames or [])
    missing = required - columns
    if missing:
        raise DataError(f"Source schema changed ({path.name}): missing {sorted(missing)}")
