# Preregistration: municipal fleet rightsizing on public data

Frozen: 2026-10-01 (do not edit; amendments go in dated AMENDMENT files)

## Research question

On published municipal fleet open data, does a transparent utilization-and-emissions pipeline with bootstrap uncertainty outperform simple rules of thumb for identifying surplus units and ranking high-emission replacement candidates, while producing defensible TCO and GHG scenario estimates using official NRCan factors?

## Data (fixed before any results)

| ID | Source | Use |
| --- | --- | --- |
| D1 | Seattle Active Fleet Complement CSV | Primary vehicle inventory (rightsizing, replacement ranking) |
| D2 | NYC Real-World Fuel Efficiency CSV | Measured telematics summary; calibration of utilization thresholds |
| D3 | City of Laval vehicle inventory CSV | Canadian municipal replication (inventory-only) |
| D4 | NRCan 2015-2024 fuel consumption ratings CSV | Fuel and CO2 factors for ICE/Hybrid matches |
| D5 | NRCan 2012-2026 battery electric vehicles CSV | ZEV replacement options by vehicle class |
| D6 | Canada federal fleet fuel CSV (latest FY row subset) | Emissions factor sanity check only |

No synthetic data in evaluation runs. Test fixtures may use tiny synthetic CSV samples.

## Primary metrics

1. **Surplus detection agreement rate** on NYC measured groups: fraction of groups flagged by the package that fall below the preregistered miles-per-vehicle threshold (ground truth = telematics miles / vehicle count).
2. **GHG ranking stability**: Spearman correlation between package-ranked vehicle groups and ranking by `(CO2 g/km from NRCan) × (proxy annual km)` with 95% bootstrap CI over NYC groups.
3. **Scenario delta**: Percent change in fleet GHG and 10-year TCO between baseline and preregistered ZEV replacement scenario for Seattle inventory matches, with bootstrap CI on totals.
4. **Peak memory (MB)** and **runtime (s)** per pipeline stage on Mac Studio M3 Ultra, measured on full data.

## Baselines (must run as documented)

| Baseline | Rule |
| --- | --- |
| B1 Age-only | Flag vehicles with age ≥ 12 years for early replacement; no utilization |
| B2 Toronto threshold proxy | Flag light-duty proxy km < 5,000 km/year equivalent (from Toronto Fleet Services public report threshold) |
| B3 High emitters only | Rank by NRCan CO2 g/km only, ignore utilization |

Package method (P): preregistered composite score combining normalized proxy utilization (bottom quartile within equipment class), age, and emissions intensity, with weights 0.4 / 0.3 / 0.3.

## Utilization rules (package)

- **Measured mode (NYC only):** underutilized if miles per vehicle < 25th percentile within `STANDARD TYPE` across NYC groups.
- **Proxy mode (Seattle, Laval):** map equipment type to NYC standard type; assign class-level miles distribution sampled with seed 42; underutilized if proxy km < class 25th percentile. Report 95% CI via bootstrap (500 resamples, seed 42) at fleet summary level.

## TCO and GHG assumptions

| Parameter | Value | Sensitivity range |
| --- | --- | --- |
| Gasoline price | CAD 1.65/L | 1.40 to 1.90 |
| Diesel price | CAD 1.75/L | 1.50 to 2.00 |
| Electricity (fleet depot) | CAD 0.14/kWh | 0.10 to 0.20 |
| Discount rate | 5% real | 3% to 7% |
| Analysis horizon | 10 years | fixed |
| ICE maintenance | CAD 0.05/km | 0.03 to 0.08 |
| BEV maintenance | CAD 0.03/km | 0.02 to 0.05 |
| Charger amortization (BEV) | CAD 3,500 per unit over 10 years | fixed |
| Annual km proxy (when unmeasured) | Class median from NYC telematics | bootstrap |

ZEV feasibility: replacement option must exist in D5 with matching vehicle class and range ≥ 200 km.

## Stop rules

1. Stop and report if peak memory exceeds 12 GB on any stage.
2. Stop and report if fewer than 50% of Seattle light-duty rows match NRCan D4 on make/model/year (±1 year).
3. Stop and report if bootstrap CI width on fleet GHG total exceeds 40% of point estimate.
4. Do not claim "manual" labels; NYC telematics summaries are **publisher-reported aggregates**, not independent human annotation.

## Reproducibility

Single command: `python scripts/run_pipeline.py --output results/`

Results JSON and figures written to `results/` and `figures/`. Numbers in RESULTS.md must match JSON only.

## Scorer integrity tests (required)

- Perfect ranker on synthetic keys scores 1.0
- Empty ranker scores 0.0
- Resampling unit: whole vehicle records (bootstrap rows with replacement)
