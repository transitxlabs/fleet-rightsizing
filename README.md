# fleet-rightsizing

A public-data integration demonstration with conservative light-duty screening, factor provenance, simulated mileage, scoped Canadian aggregate accounting, and a fictional cost example. This work sample does not represent client engagements. Operational recommendations and fleet savings are withheld.

Code is Apache-2.0. Written prose is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by TransitX Labs Inc. Source-derived CSV/JSON, figures and report data retain provider rights and conditions; see [ATTRIBUTION.md](ATTRIBUTION.md). Raw downloads are excluded from Git, while derivatives retain public source fields.

## Current case study (generated)

<!-- CASE_STUDY_START -->
Simulated light-duty cohort: 1,544 of 4,253 loaded Seattle records; 3,012.7 t tailpipe CO2 under proxy assumptions. NRCan catalogue matches: 361/1,568 (23.0%). Stop rules passed: False. Fleet savings and operational recommendations are withheld.
<!-- CASE_STUDY_END -->

Start with the [rendered municipal case study](https://transitxlabs.github.io/fleet-rightsizing/), the GitHub Pages build of `docs/`. This intended address becomes available when the repository is published and its Pages workflow deploys; no live page is claimed yet. Repository reading starts with the [case-study source](docs/index.md), [local validation record](docs/validation.md) and [stewardship](docs/stewardship.md) (maintainer: TransitX Labs Inc.; contact info@transitxlabs.ca). Read the [generated case study](docs/results.md) with charts, exclusions, factor contributions, input hashes and failed gates. The portable [HTML report](results/report.html) embeds its figures and licence notices. [Technical report](docs/technical-report.md), [output dictionary](docs/OUTPUT_DICTIONARY.md) and [dated amendment](docs/AMENDMENT_2026-10-01.md) explain scope and assumptions.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -c requirements-release.txt ".[dev]"
python scripts/run_pipeline.py
```

One command downloads and checks publication input hashes, generates JSON/CSV/HTML, charts, RESULTS.md, docs/results.md and this case summary. Inherited-cache retrieval dates are unknown; observed hashes/dates are recorded. Public snapshots may become unavailable. A changed endpoint fails the release hash check; intentional updates require replacing the input receipt and reviewing the new outputs. An explicitly supplied cache is pinned when its parent contains `publication-inputs.json`.

To compare a regenerated checkout against a saved release tree, run `python scripts/publication_checks.py compare --reference SAVED_TREE --candidate .`. Analytical JSON and CSVs use relative tolerance 1e-10 and absolute tolerance 1e-8 (only floating-point tails); pinned hashes/counts and categorical fields must agree. PNGs and the generated README must be byte-identical. Run observations (timestamps, timings, RSS, environment) vary. CI now includes pinned regeneration and comparison on both configured Python versions; no remote execution is claimed.

## Scope and comparison

This is CSV integration and transparent illustrative accounting. Novelty is unverified. [Primary-source scope comparisons](docs/scope-comparisons.md) describe eFleetPlan, eflips-impact, SMaRTE and REVOL-E-TION without claiming equivalent optimization capability or a comprehensive market gap. [Toronto utilization summaries](https://open.toronto.ca/dataset/light-duty-city-vehicle-utilization-data/) are a future validation lead; they are not downloaded or used here.

Seattle mileage is simulated from NYC aggregates; its quartile flags do not establish surplus. Catalogue variants and mission compatibility remain unresolved. Laval is ingestion only. The Canadian federal example checks aggregate fuel accounting, not municipal factors. No independent labels, holdout evaluation, operational savings, lifecycle emissions or superiority are demonstrated.
