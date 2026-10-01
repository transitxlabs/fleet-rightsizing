# Current local validation record

Date: 2026-10-01. These are local macOS checks on Python 3.11.15, not Linux or remote CI results.

| Check | Observed result |
| --- | --- |
| `pytest tests/ --cov=fleet_rightsizing --cov-report=term-missing` | 77 passed; configured combined statement/branch coverage 94.50%, above the 90% gate |
| `ruff check` | Passed |
| `mypy src` | Passed, strict checking of 15 source files |
| `pyright src` | 0 errors or warnings |
| `mkdocs build --strict` | Passed; historical repair pages excluded from rendered site |
| Ordinary wheel, separate installed-package environment | Passed; tests import the installed package |
| `python scripts/run_pipeline.py` from a clean candidate checkout | Passed with supplied pinned ignored input cache |
| Documented analytical release comparison | Passed; JSON and four CSVs reconcile, figures and README byte-identical; Results differs only by declared run observations |

Input hashes and raw/loaded/rejected reconciliations are in generated Results and JSON. The small rejected-record ledger is public; detailed operational build/review logs and historical fix reports are retained privately. The analysis amendment and frozen specification bytes are preserved.

The offline reproduction reuses dependency modules from the constrained local environment and the exact SHA-256 pinned cache. It proves installed-package operation and cached-input regeneration. It does not establish a new cold download, fresh online dependency resolution, Python 3.12 execution, remote CI success or permanent source availability. The configured CI matrix remains available for Python 3.11/3.12.

The 50% catalogue gate fails: 361/1,568 matches (23.0%). Seattle mileage is simulated; class proxies contribute 80.0% of the estimated mass. Independent labels, held-out outcomes and measured municipal duty-cycle adjustments are absent. Measured Canadian validation is planned future work; no fleet savings, operational recommendation, client delivery or validated-rightsizing claim is established.

The public export is restricted to a fresh single-root publication candidate ancestry. An all-ref bounded pattern scan and enforced release inventory check cover that candidate; arbitrary encoded secrets and unexamined destination refs are outside the assurance. Inspect every destination ref before publication. Private source history and multi-ref delivery bundles must not be published.
