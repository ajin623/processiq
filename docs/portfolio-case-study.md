# ProcessIQ: Turning Purchase-to-Pay Events into Investigation Priorities

**Ajin Babu | M.Sc. Artificial Intelligence in Business | Independent portfolio project**
**Completed analytical baseline:** October 2026
**Focus:** Business analytics, process mining, statistical analysis, and decision support

[Repository](https://github.com/ajin623/processiq) · [Dashboard PDF](../reports/dashboard/ProcessIQ_Dashboard.pdf) · [Executive memo](../reports/ProcessIQ_Executive_Decision_Memo.pdf) · [Methods](methodology.md)

## The business problem

Purchase-to-pay managers need to understand which process patterns deserve investigation without weakening valid financial controls. A long case can reflect an operational problem, contractual payment terms, missing records, or a legitimate exception. Treating every repeat or missing activity as a failure would produce misleading recommendations.

I framed ProcessIQ around one question: **Which purchase-to-pay deviations should an operations manager investigate first to reduce delayed invoice clearing and manual rework without weakening financial controls?** The stakeholder is an analytical persona, not a real client engagement.

## What I built

I built a Python workflow that profiles and extracts an XES event log, validates case and event structure, creates analytical tables, discovers process models, evaluates explicit ordering rules, compares diagnostic markers, and ranks five investigation opportunities. A four-page Power BI report presents the results for management review.

The BPI Challenge 2019 dataset contains **251,734 purchase-item cases and 1,595,923 events**. I kept the full log for profiling and category comparisons, then focused detailed analysis on **3-way match, invoice after GR**. Its **15,182 cases** support conformance assessment; **15,045 duration-eligible cases** support the focused timing and marker analysis.

![ProcessIQ executive overview](images/processiq-dashboard-1.png)

## Engineering and analytical choices

| Challenge | My implementation choice | Why it matters |
|---|---|---|
| Large nested event log | Stream XES extraction into case/event tables and retain source event positions | Avoid unnecessary copies and preserve an auditable event sequence |
| Questionable timestamp spans | Retain every case, with explicit duration eligibility and exclusion reasons | Protect duration summaries without hiding excluded records |
| Ambiguous compliance signals | Separate conforming, review-required, and incomplete-evidence outcomes | Avoid treating missing evidence as a confirmed violation |
| Skewed durations and multiple comparisons | Report medians/P90s, Mann–Whitney U comparisons, adjusted p-values, and effect sizes | Make comparisons inspectable while retaining interpretation limits |
| Competing investigation opportunities | Use explicit weights, component scores, and decision cautions | Connect analysis to a transparent business decision |
| Repeatable execution | Provide full/fast pipeline modes, failure gates, and dashboard file checksums | Make failures visible and generated outputs traceable |

The stack includes Python 3.12, pandas, NumPy, SciPy, PM4Py, Graphviz, Bash, Power BI/DAX, and Git. I also implemented PostgreSQL schema, loading, analytical-view, and reconciliation scripts. That optional database path is separate from the verified CSV pipeline; I do not present the full pipeline run as proof of live database execution.

## What the analysis found

The focused eligible cohort has a median observed trace duration of **63.10 days** and P90 of **128.30 days**. These are first-to-last recorded event spans, not necessarily completed purchase-to-payment times.

The three highest-ranked investigations are:

1. **Payment-block prevention and resolution: score 78.** The marker appears in 2,252 eligible cases. Median duration is 35.96 days higher than for cases without it. This motivates investigation of block reasons and release intervals, not removal of valid controls.
2. **Invoice receipt to clearing: score 77.** The directly-follows transition appears in 7,718 eligible cases and accounts for 24.32% of observed waiting time. Its median wait is 21.96 days; payment terms and due dates are needed to interpret the delay.
3. **Repeated formal invoice receipts: score 75.** The marker appears in 1,221 eligible cases and is associated with a 67.46-day higher median duration. Partial invoices, corrections, reversals, and possible duplicates need to be distinguished.

Separately, the ordering rules identify **9 review-required cases**, **9,667 conforming cases**, and **5,506 cases with incomplete evidence**. I kept control review separate from operational scores so a small exception population would not disappear inside an impact ranking.

The output is a prioritised investigation brief. It is not evidence that these activities caused the full duration differences or that an intervention delivered savings.

## Verification and lessons learned

The recorded full-data run completed in approximately **2 minutes 33 seconds** on my development machine and passed the structural/count gate and dashboard checksum verification. **All 92 automated tests passed**, covering normal and malformed inputs, timing exclusions, joins, scoring boundaries, and pipeline failure behaviour. Runtime is an observation from this environment, not a general benchmark.

One useful engineering lesson came from a pipeline failure: embedded Python in a shell heredoc failed with an indentation error even though Bash syntax checking passed. I moved the validation and checksum logic into a dedicated Python script and added tests for those gates, including whether the runner stops before transformation when validation fails.

The main analytical lesson was to define populations and evidence types before interpreting a chart. The full-log population, conformance scope, and duration-eligible cohort answer different questions. A marker-group duration difference and a transition wait are different measurements even when both are expressed in days.

## What this demonstrates

This project demonstrates the ability to frame a business question, inspect imperfect process data, implement a tested analytical workflow, and communicate decisions with explicit assumptions. It connects ERP/process understanding with Python, statistical reasoning, SQL design, and BI reporting.

It does not train a predictive machine-learning model or implement a chatbot. I would extend it only when an additional method answers a concrete decision need. Sensible next investigations include payment-term enrichment, supplier segmentation, scoring sensitivity, and validation with a process owner.

## Short project description

ProcessIQ is a purchase-to-pay process-mining and decision-support project built with Python, PM4Py, statistical analysis, and Power BI. I analysed 1.60 million events across 251,734 purchase-item cases, developed explicit quality and conformance rules, and ranked five operational investigations. A reproducible pipeline with 92 passing tests supports the outputs. The project distinguishes incomplete evidence, control-review cases, and observational associations without claiming causal savings.

## CV-ready bullets

- Built a tested Python process-mining pipeline for 1.60 million events and 251,734 purchase-item cases, with structural validation, timing exclusions, and dashboard checksum checks.
- Analysed bottlenecks and seven diagnostic markers using PM4Py, SciPy, adjusted statistical tests, and effect sizes; produced five transparent investigation priorities.
- Developed a four-page Power BI report and executive brief separating operational opportunities from nine review-required cases and 5,506 incomplete-evidence cases in a 15,182-case category.

## Evidence and attribution

Analysis code: `5e191f1`; reviewed dashboard export: `03072ab`. See [findings](findings.md), [methodology](methodology.md), [reproducibility](reproducibility.md), and the [dashboard review](dashboard-review.md) for supporting details and remaining presentation limitations.

Dataset: van Dongen, B. (2019). *BPI Challenge 2019*, 4TU.Centre for Research Data, [DOI](https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1), CC BY 4.0. The project is an independent analysis, not an endorsement by the dataset publisher.
