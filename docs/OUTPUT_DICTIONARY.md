# Output and data dictionary

All operational recommendations are withheld. Units and interpretation:

| Output / field | Meaning |
| --- | --- |
| `results.json`, `baseline` | Loaded count and estimated light-duty count; simulated annual L, tailpipe CO2 tonnes and CAD fuel cost; disjoint exclusions |
| `inputs` | SHA-256, bytes, raw CSV rows and observation UTC per input; observation is not acquisition time |
| `provenance_totals` | Text-match/class-proxy/unsupported records and estimated CO2 kg; excluded assets carry no estimate |
| `uncertainty` | Conditional empirical row-bootstrap estimand and chosen mileage/factor envelope; no real-fleet coverage guarantee |
| `federal_factor_check` | Latest fiscal-year beginning, latest/compatible/excluded rows, gasoline/diesel litres, kt CO2e, kg CO2e/L and illustrative CO2 comparison |
| `seattle_scored.csv` | Public inventory identity, source description/weight/body, powertrain, scope and exclusion reason; simulated km, class quartile, factors, provenance, compatible variant/class extrema, annual kg/L/CAD |
| `match_provenance` | `exact`, `year_adjacent`, `fuzzy` are catalogue text matches with unresolved variants; `class_mean` is a proxy; `generic` and `not_applicable` are unsupported |
| `scenario_ledger.csv` | Illustrative catalogue screen for top 10% of composite scores, not a plan; `illustrative_screen_flag`, BEV range/energy; `engineering_status` not reviewed; `bev_feasible` false, fleet `tco_savings_10yr` and `scenario_ghg_reduction_factor` zero; `hypothetical_npv_delta_cad` uses uniform base capital |
| `sensitivity.csv` | Two fictional equivalent base vehicles; one-at-a-time changes in six economic parameters; hypothetical NPV totals/delta in CAD and invariant 100% tailpipe reduction |
| `replacement_plan.csv` | Withheld and removed during regeneration |
| `report.html` | Standalone case-study preview with embedded figures, input receipts and provider notices |
| `RESULTS.md`, `docs/results.md` | Byte-identical case-study tables from same results record; README case paragraph from that record |
| Figures | Simulated CO2 by factor provenance, invented mileage with class quartiles, synthetic two-vehicle economic sensitivity (`fictional_sensitivity.png`), with no public asset IDs |
| `stage_memory_mb`, `peak_memory_mb` | Process high-water RSS in MiB, not isolated per-stage memory |
| `timings_seconds` | Instrumented stage sum, before-output time, and time through CSV/HTML output; imports/startup/final metadata serialization excluded |

Interpret excluded zero-valued emissions as missing estimates, not measured zero emissions. No source license plate, people/student/client records or private contact exports are required for these outputs. A municipal analyst must supply measured mileage, service/dispatch/reserve requirements, engine/transmission/fuel variants, mission-compatible replacement specifications, upfits and current quotes before decision analysis.

## Implemented screen and proxy assumptions

Known weights and identified duty tokens screened; specialization remains unresolved. Known weight CLASS 1, CLASS 2 or LIGHT and SEDAN/SUV/VAN/TRUCK are required. The fixed duty-token screen is defined in `baseline.light_duty_scope`; it is not a complete specialist classifier. SERVICE BODY and CUTAWAY can pass, including descriptions such as CARGO - CUTAWAY VAN - SPARTAN BODY. Department alone does not establish duty.

`scope_status` records whether the inventory screen passed, with specialization unresolved. `upfit_status` marks identified SERVICE BODY/CUTAWAY descriptions as compatibility unresolved; all other upfits remain unverified. Both scored and catalogue ledgers preserve these statuses. No status establishes engineering feasibility.

Actual fallback mapping: SEDAN -> Compact; SUV -> Sport utility vehicle: Small; VAN -> Minivan; TRUCK -> Pickup truck: Standard. These coarse substitutions are not validated body or payload equivalence. Fuel-compatible catalogue arithmetic means/extrema are used for emissions. NYC calibration is the unweighted median of aggregate model-group miles per vehicle within each class, not a vehicle-weighted duty distribution; TRUCK uses NYC PICKUP.

`diagnostic_cohort` and `evaluation.diagnostic_cohort_count` identify the estimated records used by age, kilometre-only and quartile diagnostics and the utilization chart. Light-duty TRUCK is included. Excluded records receive no descriptive flag and no quartile threshold. Simulated mileage remains available in the full ledger for provenance, not as a reported equipment utilization result. Quartiles are recalculated within the estimated cohort.

`scenario_value_status` labels the legacy zero fleet savings and reduction fields as withheld placeholders; not evaluated fleet outcomes. Zero engineering-feasible rows means no feasibility established, not proof that replacement is impossible.

## Analysis and ingestion metadata

- `analysis_year`: fixed 2026 reference used by age flags and composite age, independent of source vintages.
- `ingestion`: per source, `raw_rows`, parser `loaded_rows`, `rejected_rows`, counts by `rejection_reasons`, and `rejected_records`. Raw = loaded + rejected; loaded is before analytical filtering.
- `ingestion_rejections.csv`: source, `source_row` (1-based data-record ordinal after header, not physical line number), rejection reason, field and offending value only. It omits full raw records. `publisher_footer` identifies Seattle Total/Applied filters metadata; `blank_year` and `unparseable_year` distinguish missing from invalid inventory years. NYC invalid counts/miles, NRCan invalid numeric fields and federal invalid fiscal labels have explicit reasons. An unknown source class/schema still stops ingestion.
- `catalogue_coverage`: `matched_records` / `eligible_records` is the gate (361/1,568); `estimated_records` is 1,544; `eligible_without_supported_factors` is 24. Scope/fuel eligibility precedes factor support.

Composite terms and constant-group behavior are specified in the [technical report](technical-report.md). NRCan standard test-cycle factors have no measured municipal duty-cycle adjustment. Source vintages differ and cannot establish current fleet or replacement availability.

Figure source records in `figures/*.data.json` contain the exact plotted labels and numerical values: emissions group sums; utilization samples, histogram counts/edges and class quartile thresholds; fictional sensitivity low/high endpoints. Renderers consume these same records. The release check compares their bytes, reconciles them to the analytical CSVs with round-trip float parsing, and fully decodes each PNG at its expected dimensions. Raster bytes can differ across platforms.
