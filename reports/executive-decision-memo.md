# ProcessIQ: Executive Decision Memo

**Prepared by:** Ajin Babu | **Date:** 8 October 2026
**Proposed audience:** Purchase-to-Pay Operations Manager and Finance Control Owner
**Context:** Independent portfolio analysis of the BPI Challenge 2019 event log

## Decision requested

Commission three focused investigations: payment-block handling, invoice-receipt-to-clearing waits, and repeated formal invoice receipts. Assign a separate owner to review the nine cases flagged by ordering rules. Validate business context before changing controls or setting improvement targets.

## Evidence and scope

The complete log contains **251,734 purchase-item cases and 1,595,923 events**. Detailed conformance covers **15,182** cases in the category **3-way match, invoice after GR**. Duration analysis uses **15,045** eligible cases, containing **302,275** events.

The eligible selected cohort has a **63.10-day median** and **128.30-day P90** observed trace duration. These measure the first-to-last recorded event span; they do not establish that every case completed. Timing exclusions retain cases in the data while excluding unreliable spans from duration summaries.

## Investigation priorities

| Rank | Investigation | Score / band | Cases / reach | Evidence in days |
|---:|---|---|---|---|
| 1 | Payment-block prevention and resolution | 78 / P1 | 2,252 / 14.97% | +35.96 median duration difference: with marker minus without marker |
| 2 | Invoice receipt to clearing | 77 / P1 | 7,718 / 51.30% | 21.96 median directly-follows wait; 65.03 P90 wait |
| 3 | Repeated formal invoice receipts | 75 / P1 | 1,221 / 8.12% | +67.46 median duration difference: with marker minus without marker |
| 4 | Goods receipt to formal invoice receipt | 70 / P2 | 5,360 / 35.63% | 19.08 median directly-follows wait |
| 5 | Vendor invoice creation to formal receipt | 70 / P2 | 4,886 / 32.48% | 20.39 median directly-follows wait |

Reach uses the 15,045-case eligible cohort. Groups overlap. Marker differences describe associations between case groups; transition waits describe elapsed time between adjacent recorded events. Neither is an estimate of recoverable time.

Invoice receipt to clearing accounts for **24.32% of observed transition waiting time**. Agreed payment terms may explain part of this interval; due dates are needed to distinguish expected waiting from avoidable delay.

## Protect controls and separate missing evidence

Within all 15,182 selected-category cases, **9,667 (63.67%)** pass both implemented ordering rules, **5,506 (36.27%)** have incomplete evidence, and **9 (0.06%)** require review. Rule outcomes are not a comprehensive financial-control audit.

Review each flagged case against original event positions and review reasons. Do not classify the 5,506 incomplete cases as confirmed violations. Do not remove payment blocks merely because cases containing them have longer durations.

## Proposed follow-up

The following sequence and owners are proposals, not agreed deadlines or implemented work.

| Sequence | Suggested owner | Deliverable before a process-change decision |
|---|---|---|
| First | Finance control owner with data owner | Evidence-backed disposition of all nine review cases; explanation of missing milestones in incomplete cases |
| Next | Accounts payable operations | Payment-block reasons and separate block-to-release / release-to-clearing measures; identification of necessary versus preventable blocks |
| Next | Accounts payable with treasury | Payment terms and due dates joined where reliable; expected versus overdue/avoidable waiting distinguished |
| Next | Invoice processing owner | Repeated receipts classified as partial invoices, corrections, reversals, or possible duplicates |
| Then | P2P manager and data owner | Decision on a scoped pilot, with a baseline, comparison approach, and control measures agreed before intervention |

Candidate pilot measures include avoidable or overdue days, repeat-posting reasons, and exception-resolution time, alongside control outcomes. Numeric reduction targets should follow validation of these measures. There is no supported savings estimate at this stage.

## Why this ranking is useful, and where it stops

Scores combine reach (25%), time impact (25%), evidence strength (25%), actionability (15%), and confidence (10%). Components are rated 1–5 and scaled to 100 points; P1 begins at 75 and P2 at 65. Weights and business ratings are analyst choices, not externally validated probabilities or returns.

Seven diagnostic-marker comparisons use two-sided Mann–Whitney U tests, Benjamini–Hochberg adjustment, and rank-biserial effect sizes. This supports transparent association analysis; it does not remove confounding, overlap, or dependence between purchase items. The analysis describes one historical category in an anonymised organisation.

The recorded full pipeline run passed validation and dashboard checksum gates. All 92 automated tests passed. These checks support implementation reliability; they do not establish causal effects or independently validate every Power BI measure.

## Evidence trail

- [Detailed findings](../docs/findings.md), [methodology](../docs/methodology.md), and [reproduction guide](../docs/reproducibility.md).
- [Four-page dashboard](dashboard/ProcessIQ_Dashboard.pdf), export committed at `03072ab`; analysis implementation `5e191f1`.
- van Dongen, B. (2019). *BPI Challenge 2019*. 4TU.Centre for Research Data. [Dataset DOI](https://doi.org/10.4121/uuid:d06aff4b-79f0-45e6-8ec8-e19730c248f1). Source dataset: CC BY 4.0.
