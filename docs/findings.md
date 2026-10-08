# ProcessIQ Findings and Recommended Investigations

Result snapshot: **8 October 2026**. Evidence comes from the successful full dataset run and the committed [dashboard PDF](../reports/dashboard/ProcessIQ_Dashboard.pdf) and [images](images). The method is defined in [methodology](methodology.md), with implementation at commit `5e191f1`.

## Decision brief

Begin operational investigation with payment-block cases, invoice-receipt-to-clearing waits, and repeated formal invoice receipts. In parallel, review the nine cases flagged by recorded-order rules and investigate incomplete evidence separately. Preserve valid financial controls while determining which delays are avoidable.

This is a proposed investigation sequence. The project has not implemented these interventions or measured resulting savings.

## 1. Scope and reconciliation

| Population | Cases | Events | Use |
|---|---:|---:|---|
| Complete event log | 251,734 | 1,595,923 | Dataset profiling, validation, and category overview |
| Selected category: invoice after GR | 15,182 | 319,233 | Focused discovery and conformance |
| Duration-eligible selected category | 15,045 | 302,275 | Bottleneck and marker comparisons |

Across the complete log, 251,380 cases are duration-eligible and 354 are excluded from duration summaries. Within the selected category, 137 cases are excluded. Cases remain in the data; eligibility is a flag, not deletion.

| Item category | Cases |
|---|---:|
| 3-way match, invoice before GR | 221,010 |
| 3-way match, invoice after GR | 15,182 |
| Consignment | 14,498 |
| 2-way match | 1,044 |
| **Total** | **251,734** |

The selected eligible cohort has a median observed trace duration of **63.10 days** and P90 of **128.30 days**. These are elapsed first-to-last recorded event spans, not necessarily completed purchase-to-payment durations. The overall dashboard median of 64.03 days describes a different, all-category eligible population.

## 2. Ranked operational investigations

Reach uses the **15,045 duration-eligible selected cases** as denominator. Each row is a distinct investigation; case groups overlap.

| Rank | Investigation | Score | Band | Affected cases | Reach |
|---:|---|---:|---|---:|---:|
| 1 | Payment-block prevention and resolution | 78 | P1 | 2,252 | 14.97% |
| 2 | Invoice receipt to clearing | 77 | P1 | 7,718 | 51.30% |
| 3 | Repeated formal invoice receipts | 75 | P1 | 1,221 | 8.12% |
| 4 | Goods receipt to formal invoice receipt | 70 | P2 | 5,360 | 35.63% |
| 5 | Vendor invoice creation to formal receipt | 70 | P2 | 4,886 | 32.48% |

Scores combine reach, representative time, evidence, actionability, and confidence. They reflect an explicit analyst-designed framework; 78 does not mean 78% confidence or a 78% saving.

### Payment-block prevention and resolution

**Association:** Cases containing a payment-block intervention have a median trace duration **35.96 days higher** than cases without the marker in the eligible selected cohort. The marker covers recorded setting or removal of a payment block; it is not a direct measurement of time spent blocked.

**Next investigation:** Segment cases by supplier and purchasing attributes. Measure block-to-release and release-to-clearing intervals separately; inspect the reasons for blocks and distinguish preventable input issues from necessary controls.

**Decision caution:** The duration difference may reflect case complexity or other shared factors. Do not interpret it as time recoverable by removing payment blocks.

### Invoice receipt to clearing

**Finding:** The directly-follows transition `Record Invoice Receipt` to `Clear Invoice` appears in **7,718** eligible cases. Median wait is **21.96 days**, P90 is **65.03 days**, and its share of all observed transition waiting time is **24.32%**.

**Next investigation:** Add contractual due dates and payment terms. Separate expected payment waiting from overdue or avoidable processing delay before setting a reduction target.

**Decision caution:** A long calendar wait is not sufficient evidence of operational waste or late payment. The transition statistic excludes paths with intermediate recorded activities between those two events.

### Repeated formal invoice receipts

**Association:** **1,221** eligible cases contain more than one formal invoice-receipt event. Their median trace duration is **67.46 days higher** than that of cases without the marker.

**Next investigation:** Review representative traces and classify repeats as partial invoices, corrections, reversals, or possible duplicates. Only propose preventive controls once the business meanings are established.

**Decision caution:** Multiple receipt events do not prove duplicate invoices, duplicate payment, or user error. The marker comparison does not establish a causal effect.

### Goods receipt to formal invoice receipt

**Finding:** **5,360** eligible cases contain the directly-follows transition. Its median wait is **19.08 days**, P90 is **67.18 days**, and wait share is **18.52%**.

**Next investigation:** Compare suppliers and available purchasing attributes within the selected category; enrich with purchasing-organisation data if available. Review long waits for invoice arrival versus internal posting delays.

**Decision caution:** This is an adjacent-event measure. It does not represent every case's complete goods-receipt-to-invoice-receipt interval when other activities intervene.

### Vendor invoice creation to formal receipt

**Finding:** **4,886** eligible cases contain the directly-follows transition from `Vendor creates invoice` to `Record Invoice Receipt`. Median wait is **20.39 days**, P90 is **68.03 days**, and wait share is **14.42%**.

**Next investigation:** Validate the meaning and recording systems of both timestamps. Compare suppliers and processing groups where reliable group data is available.

**Decision caution:** Vendor creation and formal receipt are distinct milestones. Differences can reflect document transmission, source-system practices, or posting, rather than a single controllable internal delay.

## 3. Conformance and incomplete evidence

The denominator here is **all 15,182 selected-category cases**, including those excluded from duration statistics.

| Case status | Cases | Share | Interpretation |
|---|---:|---:|---|
| Conforming | 9,667 | 63.67% | Both implemented first-occurrence ordering rules pass |
| Incomplete evidence | 5,506 | 36.27% | Available records do not establish both rules, with no review outcome |
| Review required | 9 | 0.06% | At least one rule identifies evidence requiring investigation |
| **Total** | **15,182** | **100.00%** | Selected-category scope |

Review the nine cases individually, using their case identifiers, source event positions, and recorded review reasons. Confirm whether each outcome reflects a real control issue or logging semantics. Keep this review outside the operational score ranking.

Investigate the 5,506 incomplete-evidence cases as a separate evidence-coverage problem. Missing records can reflect unfinished cases or an incomplete observation window; they must not automatically be labelled non-conforming.

The rule charts provide an additional reconciliation:

| Rule | Pass | Not assessable | Review |
|---|---:|---:|---:|
| Goods receipt before formal invoice receipt | 11,128 | 4,054 | 0 |
| Formal invoice receipt before clearing | 9,667 | 5,506 | 9 |

A pass applies to the implemented ordering rule, not every possible financial control. Rule-level populations overlap and must not be added together.

## 4. Proposed follow-up and success measures

These are proposed responsibilities and measures, not completed work or agreed business targets.

| Follow-up | Suggested owner | Evidence needed before a decision |
|---|---|---|
| Review nine flagged cases | Finance control owner | Case-by-case review outcome and explanation of any logging issue |
| Explain incomplete evidence | Data owner with P2P operations | Coverage of required milestones and reasons for missing records |
| Investigate payment blocks | Accounts payable operations | Block reasons, block-to-release time, and control outcomes |
| Investigate clearing waits | Accounts payable with treasury | Due dates, terms, overdue days, and avoidable versus expected waiting |
| Classify repeated invoice receipts | Invoice processing owner | Repeat categories and confirmed exceptions, without assuming duplicates |
| Review receipt/posting handoffs | Procurement and invoice processing | Timestamp semantics and supplier/processing-group comparisons |

If a process change is justified, define a pilot and baseline before implementation. Compare appropriate cohorts, measure control outcomes alongside speed, and avoid claiming that observational differences are guaranteed improvements.

## 5. Evidence locations and limits

| Evidence | Local generated artifact |
|---|---|
| Source profile and field coverage | `data/interim/xes_profile.json` |
| Structural validation | `data/interim/data_quality_report.json` |
| Timing scope and exclusion reasons | `data/processed/case_timing.csv` |
| Conformance outcomes and reasons | `data/processed/case_conformance.csv`, `data/interim/conformance_report.json` |
| Transition waits and marker comparisons | `data/interim/bottleneck_report.json` and the corresponding processed CSVs |
| Ranking, component scores, and cautions | `data/processed/improvement_priorities.csv`, `data/interim/improvement_priorities.json` |
| Dashboard scope and file digests | `data/interim/dashboard_manifest.json` |

Generated data is excluded from Git and can be reproduced using the [pipeline guide](reproducibility.md). The committed report is a snapshot; refresh it after relevant data changes. Automated tests validate implemented behaviours and safeguards, but they do not establish causality or guarantee that every visual is configured correctly.

No savings, headcount reduction, implemented improvement, or prediction performance is claimed. Results should not be generalised to all purchasing categories, organisations, or present-day operations without further evidence.
