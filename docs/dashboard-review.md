# Dashboard Export Review

**Review date:** 8 October 2026
**Reviewed version:** commit `03072ab`
**Artifact:** [ProcessIQ dashboard PDF](../reports/dashboard/ProcessIQ_Dashboard.pdf), four pages, 742,502 bytes
**SHA-256:** `0a05e3c7f689cc44e3f5a5d61639db8c332746a4fc1de1565a411a97533a1a96`

The uploaded PDF matched the committed PDF byte-for-byte. All four pages were rendered and visually inspected; extracted text was compared with documented findings. This is an export review, not an independent rerun of the source-data analysis or inspection of every PBIX formula and relationship.

## Findings

| Page | Confirmed | Remaining presentation issue |
|---|---|---|
| Executive Overview | 251,734 cases, 1,595,923 events, 251,380 eligible cases, and correctly scoped conformance totals are displayed | Long category labels are abbreviated |
| Bottleneck Analysis | Full median/P90 card labels fit; 15,045 eligible cases, 302,275 events, 63.10 median days, and 128.30 P90 days match the findings | Several chart labels are abbreviated; the transition table still scrolls vertically and is sorted by transition name rather than wait share |
| Improvement Priorities | All five priorities, counts, reach values, and scores are visible; the full recommendation and caution texts now wrap and fit | Band wraps across two lines; a horizontal scrollbar remains on the lower table; the generic Delay (Days) label needs its metric distinction made explicit |
| Conformance & Controls | 9,667 + 5,506 + 9 reconciles to 15,182; the former out-of-scope blank slice is absent | Some legend text remains abbreviated |

The main clipping problem in the recommendations table is resolved in this version. It would be inaccurate to claim that every label or row in the full report is now visible without scrolling.

## Metric-label clarification

The Priority Evidence Summary's `Delay (Days)` column contains two different types of evidence:

| Rows | Meaning |
|---|---|
| Payment-block intervention; repeated invoice receipts | Difference between case-group median observed durations: with marker minus without marker |
| Invoice receipt to clearing; goods receipt to invoice receipt; vendor creation to receipt | Median wait across directly-follows transition occurrences |

Rename this column to **Evidence (days)** and add a visible note: **Transition rows show median waits; marker rows show with-minus-without median duration differences.** Alternatively, remove the column from the summary and retain the explicitly labelled measures on the bottleneck page. Neither type is guaranteed recoverable delay.

## Small follow-up edits

1. Widen Band enough to fit on one line; slightly narrow a neighbouring numeric column if necessary.
2. Rename the lower table's headers to Opportunity, Recommended investigation, and Decision caution; reduce combined widths slightly to remove its horizontal scrollbar.
3. Sort the bottleneck table by Wait Share (%) descending. If only a subset is intended in a static export, state that subset in its title and size it to display those rows completely.
4. Clarify the evidence-days column as above. The executive memo and case study already distinguish the measurements.

These edits can accompany the next report revision. The current export supports preparation of the written handoff, with the limitations recorded here. A later visual change should be re-exported and reviewed before marking these items resolved.
