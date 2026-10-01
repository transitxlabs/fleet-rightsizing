# Public-data integration case study

Which municipal fleet records can support transparent fuel and emissions accounting, and what evidence is still needed before deciding that a vehicle is surplus or replaceable?

TransitX Labs Inc. maintains this public-data integration work sample. It demonstrates typed CSV ingestion, reconciled source counts, conservative inventory screening, traceable factors and reproducible accounting reports. It is not client work or validated municipal decision performance. Fleet savings and operational recommendations are withheld.

## Source-to-output

```text
Seattle public inventory + NYC group mileage + NRCan test-cycle ratings
  -> SHA-256 pinned ingestion and rejection ledger
  -> scope/fuel screen -> simulated kilometres + factor provenance
  -> estimated cohort -> CSV/JSON ledgers -> tables, charts and HTML
Laval inventory -> raw/loaded/rejected reconciliation only
Federal fuel aggregates -> fiscal-year and scope filter -> CO2e/L accounting
```

## Coverage and exclusions

| Coverage | Observed snapshot result |
| --- | --- |
| Seattle ingestion | 4,255 raw; 4,253 loaded; 2 publisher footers removed |
| Seattle estimated cohort | 1,544 records; 2,709 excluded |
| Disjoint estimate exclusions | 602 BEV; 26 non-powered; 511 trailer; 1,570 other scope/factor exclusions |
| Catalogue gate | 361 / 1,568 scope/fuel-eligible matches (23.0%); 50% gate fails |
| Denominator reconciliation | 24 eligible records lack supported factors; 1,544 remain estimated |
| Factor coverage | Class proxies contribute 80.0% of simulated CO2 |
| Laval ingestion | 1,318 raw; 1,232 loaded; 86 blank-year records rejected |
| NYC mileage | 106 publisher model groups; unweighted class medians, no Seattle measurements |
| Federal accounting | 42 compatible fuel rows / 129 latest-year rows; fiscal year beginning 2024 |

A small reproducible result is **3,012.7 t simulated annual tailpipe CO2**, with a chosen assumption envelope of **1,470.0 to 5,539.4 t**. This is not measured fleet emissions; the envelope has no probability coverage claim. Analysis year is fixed at 2026. NRCan standard test-cycle factors have no measured duty-cycle adjustment; source vintages differ and do not establish current inventory or purchase availability. Variants, payload, seating, mission, upfits and dispatch/reserve requirements remain unresolved.

Read [generated results](results.md), the [current local validation record](validation.md), [technical report](technical-report.md) and [output dictionary](OUTPUT_DICTIONARY.md). The standalone `results/report.html` in the repository embeds its figures and notices: open it locally for a rendered preview. This case study is the GitHub Pages build of `docs/`, intended for https://transitxlabs.github.io/fleet-rightsizing/ when the repository is published and the Pages workflow deploys. No live deployment or remote CI execution is claimed.

## Next evidence

Measured Canadian validation is planned future work. Toronto utilization data is a cited lead only; it is not downloaded or evaluated here. A future case needs lawfully reusable measured utilization and service evidence, a prespecified decision target and comparator, held-out outcomes and reported failures before any validated-rightsizing claim.

## Reproduce and stewardship

Use Python 3.11 or 3.12, install with `pip install -c requirements-release.txt ".[dev]"`, then run `python scripts/run_pipeline.py`. Six input hashes are checked; endpoint availability is not guaranteed. See README for environment setup and analytical comparison.

Maintainer: **TransitX Labs Inc.** Contact: **info@transitxlabs.ca**. See [stewardship, licence and support scope](stewardship.md) and [provider attribution](attribution.md).
