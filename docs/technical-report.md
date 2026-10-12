# Technical report: public-data integration demonstration

This is a software and accounting demonstration, not client work, validated surplus detection, a procurement assessment or evidence of methodological novelty. Fleet savings and operational recommendations are withheld. Current tables, input receipts and charts are generated on the [Results page](results.md) from the same record as JSON and portable HTML.

Seattle supplies inventory, not observed mileage. The light-duty screen requires weight class 1/2 or LIGHT, recognized body class, and no identified specialist duty tokens. It preserves descriptions and weights in the exclusion ledger; a passing screen is not mission equivalence. Known weights and identified duty tokens screened; specialization remains unresolved. SERVICE BODY and CUTAWAY records can pass; source descriptions and explicit scope/upfit status are displayed in both ledgers. Department alone does not resolve mission.

NYC publisher aggregates supply the unweighted median of group-level miles per vehicle within each class; this is not a vehicle-weighted duty distribution. Seattle kilometres are invented using seeded Gaussian noise at 15% of that median and a 500 km floor. TRUCK uses NYC PICKUP calibration. All loaded records receive simulated mileage, but the reported flags and mileage chart use only estimated records, including screened light-duty TRUCK. Quartiles are recalculated within that cohort. Low quartile flags arise by construction and do not establish surplus. Service demand, dispatch, idling, engine hours, frequency, reserve and emergency coverage are missing.

NRCan catalogue matches preserve variants and use compatible-fuel arithmetic means. Engine and transmission remain unresolved; exact/year-adjacent/fuzzy means describe text matching, not verified specifications. Class proxies use arithmetic means with observed extrema. The substitutions are SEDAN to Compact, SUV to Sport utility vehicle: Small, VAN to Minivan, TRUCK to Pickup truck: Standard; upfitted bodies are not resolved by these mappings. Generic factors are unsupported and do not enter estimated totals. The chart separates factor provenance. Missing assets are exclusions, not zero emissions.

The composite uses reversed min-max mileage, age and annual emissions mass within equipment class, with weights 0.4/0.3/0.3. With fixed analysis year 2026, age = 2026 - model_year. The terms are:

- Mileage: `(class_max_km - km) / (class_max_km - class_min_km)`.
- Age: `(age - class_min_age) / (class_max_age - class_min_age)`.
- Emissions: `(annual_co2_kg - class_min_co2_kg) / (class_max_co2_kg - class_min_co2_kg)`.

Every term is zero for a constant group (zero span), including a one-record class. The composite is `0.4 * mileage + 0.3 * age + 0.3 * emissions`. Reversed linear mileage is not reciprocal mileage; 1,000/2,000/4,000 km gives 1, 2/3, 0. This wording documents the existing calculation; no ranking method changes. NYC diagnostics compare quartile and median labels on identical observations and composite versus g/km ranking. They do not test superiority, independent surplus labels or a held-out decision outcome. B2 implements only Toronto's kilometre component; engine hours and frequency are absent.

The row-bootstrap diagnostic holds mileage and factors fixed and targets the sum of iid empirical record draws. It cannot quantify uncertainty in the complete actual fleet. A separate assumption envelope uses chosen mileage multipliers 0.7/1.3 and observed factor extrema; it has no coverage guarantee and omits calibration and classification uncertainty.

Catalogue matches are illustrative options awaiting engineering review. Payload, body, seating, mission, upfits, range under duty conditions and current purchase availability are unverified. No asset is declared feasible and no fleet savings or ranked operational plan is released. A fictional two-vehicle cost example specifies uniform base capital, energy and maintenance assumptions; all six economic inputs change its NPV. Full service transfer to a BEV gives zero vehicle tailpipe CO2. Lifecycle emissions are outside scope.


NRCan factors are standard test-cycle ratings, not measured municipal duty-cycle consumption/emissions. No measured duty-cycle adjustment is available. Inventory and catalogue vintages differ; ICE ratings cover 2015-2024. These snapshots establish neither current fleet inventory nor current purchase availability. Fixed analysis year 2026 is the age reference, not a common source year.

Generated ingestion metadata reconciles raw/loaded/rejected rows for all six sources. Seattle's Total and Applied filters rows are publisher footers, not missing vehicles; Laval blank-year rows are rejected records. See Results and `results/ingestion_rejections.csv`. Catalogue text matches are 361/1,568 scope/fuel-eligible records (23.0%); 24 eligible records lack supported factors, leaving 1,544 estimated records. The numerator and denominator govern the gate; the estimated cohort governs reported emissions.

Laval is an ingestion check. The Canadian federal example has tested fiscal-year parsing and reports latest-year row and fuel coverage for scope-1 on-road gasoline/diesel. Its source CO2e/L is compared within each fuel against illustrative CO2/L references, with scope differences made explicit. It does not validate municipal tailpipe factors.

The frozen file is an analysis specification without proven pre-result chronology. See the [dated amendment](AMENDMENT_2026-10-01.md) for deviations and diagnostic continuation after a failed match gate. Publisher endpoints may change; hashes in `data/publication-inputs.json` identify observed inputs. Reproduction stops on changed publication inputs, whose permanent availability is not guaranteed.

Provider credit, licences and modification notices are in [attribution](attribution.md). See [scope comparisons](scope-comparisons.md) for bounded primary-source links and the Toronto validation opportunity.
