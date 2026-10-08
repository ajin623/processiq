# ProcessIQ Methodology

Implementation reference: commit `5e191f1`, reviewed 8 October 2026. Results are recorded in [findings](findings.md); commands are in [reproducibility](reproducibility.md).

## 1. Unit of analysis and scope

A case represents one purchase-document item. Events are keyed by `case_id` and source `event_position`; repeated activities remain separate events. Purchase documents can contain multiple related cases.

| Analysis | Scope |
|---|---|
| Ingestion, quality checks, category volumes, variant profiling | All 251,734 cases and 1,595,923 events |
| Timing eligibility | All cases; 251,380 eligible and 354 excluded from duration summaries |
| Focused discovery and rule conformance | All 15,182 cases in `3-way match, invoice after GR` |
| Focused duration, transition, and marker analysis | 15,045 eligible cases in that category, containing 302,275 events |
| Improvement ranking | Five configured investigations using the focused evidence |

These scopes differ intentionally. The full selected category contains 319,233 events. Its 137 duration-excluded cases remain available for category counts and rule assessment.

## 2. Extraction and validation

[inspect_xes.py](../src/processiq/inspect_xes.py) profiles the XML log. [extract_xes.py](../src/processiq/extract_xes.py) streams it into raw case and event CSVs, preserving source values and event positions.

[validate_data.py](../src/processiq/validate_data.py) checks headers, identifiers, event references, positions, values, timestamps, and expected counts. The pipeline's [validation gate](../scripts/check_pipeline.py) requires both `structural_integrity_passed` and `count_reconciliation_passed` to be Boolean `true`. A missing or failed flag stops the runner before transformation.

Timestamp warnings remain separate. The raw report can say `duration_metrics_ready: false` while structural validation passes. The transformation stage determines which cases can support duration analysis; the warning is not silently changed into a pass for all cases.

## 3. Transformation and duration eligibility

[transform_data.py](../src/processiq/transform_data.py) normalises missing markers, creates quality flags, and writes one timing row per case. Source data remains unchanged. Excluded cases remain in the analytical tables.

A case is duration-eligible only when:

1. Every event timestamp is within calendar years 2018–2019, inclusive.
2. No consecutive source-ordered timestamps move backwards.
3. The recorded first-to-last event span is at most 365 days.

Equal timestamps are allowed. The analysis does not guess replacement dates, remove events to shorten cases, or cap long durations. Exclusion reasons remain recorded.

`cycle_time_days = (last recorded timestamp - first recorded timestamp) / 86,400 seconds`.

This measures **observed trace duration**. Eligibility does not require a clearing event and does not establish completion. Missing starts or ends and the observation window can affect duration. The 365-day threshold is an analytical scope choice, not a business service-level agreement.

## 4. Process discovery

[discover_process.py](../src/processiq/discover_process.py) profiles activity-sequence variants by category and creates a PM4Py directly-follows graph and Inductive Miner process tree for the selected category.

Defaults are 10 reported variants per category, 20 reported transitions, an Inductive Miner noise threshold of 0.2, and at most 30 displayed DFG edges. The selected category has 38 activities and 303 distinct discovered transitions. The simplified diagram is not an inventory of every recorded path.

Source positions are retained for sequence analysis and timestamp-tie handling. Discovery describes observed behaviour; the project does not report model-alignment fitness as proof of business compliance.

## 5. Conformance rules

[analyze_conformance.py](../src/processiq/analyze_conformance.py) assesses first recorded positions of goods receipt, formal invoice receipt, and clearing in the selected category.

| Rule | Pass | Review | Not assessable |
|---|---|---|---|
| Goods receipt before formal invoice receipt | First goods receipt precedes first formal invoice receipt | Invoice receipt exists but goods receipt is missing or does not precede it | Formal invoice receipt is missing |
| Formal invoice receipt before clearing | First formal invoice receipt precedes first clearing | Clearing exists but invoice receipt is missing or does not precede it | Clearing is missing |

Case status is `review_required` if either rule produces review, `conforming` if both pass, and `incomplete_evidence` otherwise. Review takes precedence over incomplete evidence in the other rule.

These are recorded-order checks. They do not match every invoice to every receipt, reconcile quantities or money, prove fraud, or provide a general legal compliance assessment. `Vendor creates invoice` is distinct from `Record Invoice Receipt`. Repeats and exception activities remain diagnostic signals rather than automatic rule failures.

Cases outside the selected category have no assessed conformance result. Conformance visuals must use `conformance_in_scope = true`, rather than treating unassessed cases as a fourth outcome.

## 6. Transition waiting times

[analyze_bottlenecks.py](../src/processiq/analyze_bottlenecks.py) calculates elapsed time between adjacent events within eligible selected cases. A transition is **directly follows**: an intervening event means that occurrence is not part of that particular activity pair.

- `transition_count` counts occurrences; one case can contribute more than once.
- `affected_cases` counts distinct cases containing the transition.
- Median, P75, and P90 waits are calculated across transition occurrences using NumPy quantiles.
- `total_wait_days` sums observed elapsed time for the transition.
- `share_of_observed_wait` is 100 times the transition's total elapsed time divided by elapsed time across all observed transitions in this cohort.

The CSV contains all 297 distinct eligible-cohort transitions. The focused JSON defaults to transitions affecting at least 100 cases and reports up to 20, ordered by total observed waiting time. Duration analysis has fewer transitions than full-category discovery because the cohorts differ.

Calendar elapsed time can include weekends, agreed payment terms, missing logged activity, or legitimate processing intervals. It is not staff effort or guaranteed removable delay. Medians and P90s must not be summed across transitions. Summed affected-case counts can double-count cases.

## 7. Marker associations

Each eligible selected case receives seven Boolean markers:

| Marker | Definition |
|---|---|
| Multiple goods receipts | More than one `Record Goods Receipt` event |
| Multiple invoice receipts | More than one `Record Invoice Receipt` event |
| Multiple service entries | More than one `Record Service Entry Sheet` event |
| Payment-block intervention | A `Set Payment Block` or `Remove Payment Block` event |
| Cancellation activity | Activity name begins with `Cancel ` |
| Deletion or reactivation | `Delete Purchase Order Item` or `Reactivate Purchase Order Item` |
| Change activity | Activity name begins with `Change ` |

Cases with each marker are compared with cases without it. The report includes group sizes, median and P90 trace durations, average event counts, and the descriptive median difference: **with marker minus without marker**.

The implementation applies a two-sided asymptotic Mann–Whitney U test, then Benjamini–Hochberg adjustment across all seven tests. Adjusted p-values below 0.05 are flagged as statistically significant. Mann–Whitney examines rank/distribution differences; it is not, without additional assumptions, a direct test of the displayed difference in medians.

The signed rank-biserial effect is `2U / (n_with * n_without) - 1`. Positive values indicate higher duration ranks in the marker group. The code labels absolute effects below 0.147 negligible, below 0.330 small, below 0.474 medium, and otherwise large. These are reporting conventions, not business-impact thresholds.

The report also describes combinations of four markers: repeated invoice receipts, cancellation, payment-block intervention, and change activity. This exposes overlap; it is not an adjusted causal model. Shared purchase documents, supplier mix, process complexity, overlapping markers, and incomplete traces can confound comparisons. Multiple-testing adjustment does not remove these limitations. A negative association does not mean an activity should be introduced to shorten cases.

## 8. Improvement prioritisation

[prioritize_improvements.py](../src/processiq/prioritize_improvements.py) scores three configured transition investigations and two configured marker investigations. It does not automatically discover every possible improvement.

Each component receives an integer score from 1 to 5:

| Component | Weight | Basis |
|---|---:|---|
| Reach | 25% | Affected distinct cases divided by 15,045 eligible cases |
| Time impact | 25% | Transition median wait, or marker-group median duration difference |
| Evidence strength | 25% | Transition wait share, or marker effect magnitude and significance |
| Actionability | 15% | Explicit analyst rating |
| Confidence | 10% | Explicit analyst rating |

`overall_score = 20 * sum(component_score * component_weight)`.

The score is expressed on a 100-point scale. With components restricted to 1–5, its attainable range is 20–100. It is not a probability, monetary value, or expected percentage improvement.

| Score | Reach | Representative time | Transition evidence: wait share |
|---:|---|---|---|
| 5 | At least 40% | At least 60 days | At least 20% |
| 4 | 25% to below 40% | 30 to below 60 days | 15% to below 20% |
| 3 | 10% to below 25% | 15 to below 30 days | 10% to below 15% |
| 2 | 5% to below 10% | 5 to below 15 days | 5% to below 10% |
| 1 | Below 5% | Below 5 days | Below 5% |

Marker evidence scores are large = 5, medium = 4, small = 3, and negligible = 2. A non-significant adjusted result reduces the score by one, with a floor of one. Configured marker investigations require a positive median difference.

| Investigation | Actionability | Confidence |
|---|---:|---:|
| Payment-block prevention and resolution | 4 | 3 |
| Invoice receipt to clearing | 2 | 3 |
| Repeated formal invoice receipts | 3 | 3 |
| Goods receipt to formal invoice receipt | 3 | 3 |
| Vendor invoice creation to formal receipt | 4 | 4 |

P1 means score at least 75; P2 means at least 65 but below 75; P3 is below 65. Ties are ordered by `opportunity_id`. Different time/evidence definitions enable an explicit heuristic comparison but do not make transition waits and marker differences interchangeable effects. Weights and ratings require review with process owners before operational use; no sensitivity study has been claimed.

The nine control-review cases and incomplete-evidence follow-up remain separate from operational ranking. Small case counts do not remove the need for control investigation.

## 9. Dashboard data and auditability

[build_dashboard_data.py](../src/processiq/build_dashboard_data.py) combines case, timing, and available conformance information without multiplying case rows. It validates case/timing alignment, rejects duplicate conformance rows, and requires matching selected categories across source reports.

The manifest records scope, schemas, output sizes, and SHA-256 digests for `dashboard_cases.csv` and `dashboard_kpis.csv`. The runner verifies those two files after generation. This checks consistency against the manifest, not independent correctness of every metric or PBIX visual. JSON timestamps can change on each run.

Optional PostgreSQL scripts create constrained tables and analytical views from processed CSVs. They are separate from the Bash runner. The successful full pipeline run does not by itself verify a live database load.

## 10. Evidence boundaries

Findings are descriptive or associational. Proposed segmentation, document review, payment-term enrichment, and pilot interventions are future work. The project has not demonstrated causal effects, implemented changes, realised savings, predictive accuracy, or production deployment.
