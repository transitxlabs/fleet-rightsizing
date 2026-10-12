# Current local validation record

Date: 2026-10-01. These are local macOS checks on Python 3.11.15, not Linux or remote CI results.

| Check | Observed result |
| --- | --- |
| `pytest tests/ --cov=fleet_rightsizing --cov-report=term-missing` | 103 passed; configured combined statement/branch coverage 94.61%, above the 90% gate |
| `ruff check` | Passed |
| `mypy src` | Passed, strict checking of 15 source files |
| `pyright src` | 0 errors or warnings |
| `mkdocs build --strict` | Passed; historical repair pages excluded from rendered site |
| Ordinary wheel build | Passed with pinned local build backend; no new isolated installed-package run |
| `python scripts/run_pipeline.py` from a clean candidate checkout | Passed with supplied pinned ignored input cache |
| Documented analytical release comparison | Passed; normalized analytical JSON and four CSVs byte-identical with zero numerical tolerance; three figure source records byte-identical and reconciled to CSVs; valid PNGs at expected dimensions; README and table text exact except declared table observations |

Input hashes and raw/loaded/rejected reconciliations are in generated Results and JSON. The small rejected-record ledger is public; detailed operational build/review logs and historical fix reports are retained privately. The analysis amendment and frozen specification bytes are preserved.

The offline reproduction uses the local environment, whose installed versions match every constraint in `requirements-release.txt`, and the exact SHA-256 pinned cache. It proves cached-input regeneration. It does not establish a new cold download, fresh online dependency resolution, Python 3.12 execution, remote CI success or permanent source availability. The configured CI matrix remains available for Python 3.11/3.12.

The first public CI failure was reported at the PNG digest assertion for `ghg_by_department.png`. Reaching that assertion means the old JSON/CSV comparisons passed, but those checks used tolerances and did not prove exact Linux equality. Local regeneration against public commit `458bba1` confirms exact analytical JSON values and all four CSV byte sequences (4,253 scored, 1,544 scenario, 12 sensitivity and 88 rejected rows). All three original PNGs also match locally. No analytical discrepancy was observed. The evidence supports a rendering portability defect; the exact Linux font/rasterizer cause and exact Linux numerical equality remain unverified. Matplotlib documents that [FreeType versions can change glyph rendering](https://matplotlib.org/stable/users/explain/text/fonts.html).

The repaired comparator requires canonical analytical JSON bytes, every analytical CSV byte and generated table text to match exactly after the existing observation exclusions. There is no numerical tolerance. Figure source records include emissions group labels/sums; utilization samples, histogram edges/counts and quartile thresholds; and paired fictional sensitivity labels/endpoints. Renderers consume these recorded values. Every source record must match the reference byte for byte and reconcile exactly to the corresponding CSVs. Each root and documentation image must verify as PNG and fully decode at 1500 x 900 (emissions/sensitivity) or 1200 x 750 (utilization). Documentation copies must match their root image within each run. Cross-platform PNG byte equality is not promised.

The 24 new regression cases accept changed raster pixels with identical source records for all three figures, reject changed source records and changed analytical CSV inputs for each figure, reject stale records, and enforce image validity, dimensions, documentation copies, exact analytical JSON/CSVs and table values. The same checks are set up to run in CI on GitHub-hosted Linux runners for Python 3.11 and 3.12.

The 50% catalogue gate fails: 361/1,568 matches (23.0%). Seattle mileage is simulated; class proxies contribute 80.0% of the estimated mass. Independent labels, held-out outcomes and measured municipal duty-cycle adjustments are absent. Measured Canadian validation is planned future work; no fleet savings, operational recommendation, client delivery or validated-rightsizing claim is established.
