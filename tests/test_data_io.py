from __future__ import annotations

from pathlib import Path

import pytest

from fleet_rightsizing.data_io import (
    DataError,
    canonical_make,
    count_csv_rows,
    download_file,
    normalize_make,
    parse_number,
    row_get,
    safe_path,
    stream_csv_rows,
    validate_url,
)
from tests.conftest import FIXTURES


def test_validate_url_allows_seattle() -> None:
    validate_url("https://data.seattle.gov/api/views/enxu-fgzb/rows.csv")


def test_validate_url_rejects_unknown_host() -> None:
    with pytest.raises(DataError):
        validate_url("https://evil.example.com/data.csv")


def test_validate_url_rejects_http() -> None:
    with pytest.raises(DataError):
        validate_url("http://data.seattle.gov/x.csv")


def test_parse_number() -> None:
    assert parse_number("1,234.5") == 1234.5
    assert parse_number("$100") == 100.0
    assert parse_number("n/a") is None


def test_canonical_make_aliases() -> None:
    assert canonical_make("TOYT") == "TOYOTA"
    assert normalize_make("  ford ") == "FORD"


def test_stream_csv_rows_and_count() -> None:
    path = FIXTURES / "seattle_sample.csv"
    batches = list(stream_csv_rows(path, chunk_size=2))
    assert len(batches) >= 1


def test_count_csv_rows() -> None:
    path = FIXTURES / "seattle_sample.csv"
    assert count_csv_rows(path) == 26


def test_row_get_and_safe_path(tmp_path: Path) -> None:
    row = {"Year": "2020", "Make": "FORD"}
    assert row_get(row, "Year") == "2020"
    assert row_get(row, "Missing", default="x") == "x"
    assert safe_path(tmp_path, "ok.csv") == tmp_path / "ok.csv"
    with pytest.raises(DataError):
        safe_path(tmp_path, "../escape.csv")


def test_download_file_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    class FakeResponse:
        url = "https://data.seattle.gov/test.csv"

        def __init__(self) -> None:
            self._data = b"a,b\n1,2\n"

        def raise_for_status(self) -> None:
            return None

        def iter_bytes(self, size: int) -> object:
            yield self._data

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeResponse())
    dest = tmp_path / "x.csv"
    download_file("https://data.seattle.gov/test.csv", dest)
    assert dest.read_text() == "a,b\n1,2\n"
    assert dest.with_suffix(".csv.sha256").exists()
