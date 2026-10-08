# ProcessIQ Project Charter

## 1. Project Identity

- **Project name:** ProcessIQ
- **Project subtitle:** Purchase-to-Pay Process Intelligence
- **Domain:** Business analytics, process mining, financial operations, and decision support
- **Current status, 8 October 2026:** Analysis pipeline and four-page Power BI dashboard implemented; full pipeline and 92 tests passed. Documentation aligned with implementation commit `5e191f1`.

## 2. Business Context

Purchase-to-pay is the process through which an organisation requests goods or services, creates a purchase order, records receipt, processes an invoice, and clears the resulting payment obligation.

The intended process may appear simple, but real purchase items can follow different paths. Some differences are valid because different purchasing categories require different controls. Other differences may indicate rework, delays, excessive manual intervention, or possible compliance concerns.

A normal performance dashboard can show that cases are slow. It may not explain which sequences of activities are associated with that poor performance.

## 3. Problem Statement

Purchase-to-pay managers need evidence showing how purchase items actually move through the process, where important deviations occur, and which deviations deserve investigation first.

The project must distinguish legitimate process variation from potentially inefficient or non-conforming behaviour.

## 4. Decision Owner

The primary decision owner is a Finance Shared Services or Purchase-to-Pay Operations Manager.

This manager is assumed to be responsible for:

- Processing efficiency
- Invoice and purchase-order controls
- Operational quality
- Compliance monitoring
- Process-improvement prioritisation

This is a realistic analytical persona. The project is not being developed for a real named company or individual.

## 5. Primary Business Decision

Which purchase-to-pay process deviations should an operations manager investigate first to reduce delayed invoice clearing and manual rework without weakening financial controls?

## 6. Project Objectives

The project objectives are:

1. Validate the quality and usability of the event data.
2. Reconstruct actual purchase-to-pay process flows.
3. Identify common and unusual process variants.
4. Measure cycle time, waiting time, rework, and manual intervention.
5. Compare observed behaviour with documented process expectations.
6. Investigate factors associated with poor process performance.
7. Prioritise operational issues using transparent criteria.
8. Communicate findings, hypotheses, and limitations clearly.

## 7. Original Scope and Current Delivery

The original scope included:

- Event-log ingestion
- Data-quality validation
- Data cleaning and transformation
- PostgreSQL storage
- SQL-based metric calculation
- Process discovery
- Process-variant analysis
- Rework analysis
- Bottleneck analysis
- Conformance and compliance checks
- Human-versus-automated activity analysis
- Statistical comparison of relevant groups
- Scenario-based improvement estimates
- Management reporting
- Automated testing
- Reproducible documentation

The implemented scope covers ingestion, quality checks, transformation, discovery, variants, diagnostic markers, ordering-rule conformance, bottleneck statistics, prioritisation, dashboard reporting, and automated tests. PostgreSQL schema, loading, analytical views, and reconciliation SQL are present as a separate optional path; the Bash pipeline uses CSVs and does not execute those scripts.

Human-versus-automated activity performance analysis and scenario-based improvement estimates remain deferred. Missing-resource coverage was profiled, but missing resources are not automatically interpreted as automated events. Control assessment is limited to the explicit rules in [methodology.md](methodology.md); it is not a comprehensive compliance audit.

## 8. Out of Scope

The project will not include:

- Predictive machine-learning models without a justified decision need
- Generative-AI summaries
- A chatbot
- Real-time event streaming
- A public web application
- Automated operational decisions
- Claims of proven causality from observational data
- Claims of realised financial savings
- Publication of the complete raw dataset
- Identification of anonymised organisations, vendors, or employees

## 9. Evidence Standards

All published findings must be supported by reproducible calculations.

The project will clearly separate:

- **Verified finding:** directly supported by validated data and reproducible calculations
- **Association:** two characteristics appear related, without proving causation
- **Hypothesis:** a possible explanation requiring additional evidence
- **Scenario estimate:** a conditional calculation based on stated assumptions
- **Limitation:** a factor restricting interpretation or generalisation

No result, saving, improvement, or performance claim will be written before it has been calculated and checked.

## 10. Dataset Status

The BPI Challenge 2019 purchase-to-pay log was acquired on 2 October 2026 and has been profiled, extracted, validated, and analysed.

- The full run reconciles 251,734 purchase-item cases and 1,595,923 events.
- Duration summaries use 251,380 eligible cases overall; 354 cases remain in the data with exclusion flags.
- Focused conformance covers 15,182 invoice-after-GR cases; focused duration analysis covers 15,045 eligible cases.
- Source-provided metadata remains distinguished from project calculations.
- Original and generated datasets remain outside Git version control.

The [source record](data-source.md) contains citation, licence, acquisition details, and the recorded file digest. [Findings](findings.md) and [methodology](methodology.md) describe the results and their limits.

## 11. Success Criteria

ProcessIQ will be considered successful if it can:

1. Reproduce the principal analysis from documented instructions.
2. Produce a transparent data-quality assessment.
3. Reconstruct meaningful process paths.
4. Identify and quantify important process variants.
5. Detect and measure relevant rework or conformance deviations.
6. Identify material bottlenecks using frequency and severity.
7. Produce at least one substantial evidence-backed operational finding.
8. Prioritise three defensible investigation opportunities.
9. Distinguish evidence from assumptions and hypotheses.
10. Communicate the results in language understandable to a business stakeholder.

A complicated process map or a large technology stack will not count as success by itself.

## 12. Constraints

- The WSL environment has approximately 7.5 GiB of memory.
- Memory-intensive operations must be designed carefully.
- The source event log is large and must not be copied unnecessarily.
- Raw and processed datasets will not be committed to Git.
- The historical data is anonymised.
- The data may support association analysis but not automatic causal conclusions.
- Recommendations will be analytical proposals, not evidence of implemented business change.

## 13. Delivery Record and Remaining Work

| Deliverable | Status |
|---|---|
| Reproducible Python pipeline and quality gates | Implemented; full source-data run passed on 8 October 2026 |
| Data-quality, discovery, variant, conformance, and bottleneck outputs | Generated by the pipeline; scope documented |
| PostgreSQL analytical layer and reconciliation SQL | Scripts implemented; execution is separate from the verified CSV pipeline |
| Improvement-priority matrix | Five investigations ranked; control review remains separate |
| Power BI management report | Four pages, PBIX, PDF, and PNG snapshots committed |
| Automated tests | 92 passing tests at the reference implementation |
| Methodology, findings, and reproduction instructions | Documented in this repository |
| GitHub repository | Maintained under version control |
| Standalone executive memo and portfolio case study | Prepared from documented findings; see the [memo](../reports/ProcessIQ_Executive_Decision_Memo.pdf) and [case study](portfolio-case-study.md) |
| Operational pilot, financial savings, production deployment | Not delivered or claimed |

The written handoff now includes an executive decision memo and portfolio case study. Remaining follow-up includes the small presentation and metric-label items in the [dashboard review](dashboard-review.md), and recording any separate database validation. Operational enrichment, pilot design, and scoring sensitivity are proposed extensions, not delivered results. Additional technologies should be introduced only when they support the business question.
