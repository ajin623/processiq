# ProcessIQ Project Charter

## 1. Project Identity

- **Project name:** ProcessIQ
- **Project subtitle:** Purchase-to-Pay Process Intelligence
- **Domain:** Business analytics, process mining, financial operations, and decision support
- **Current status:** Project definition approved; data analysis has not started

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

ProcessIQ will aim to:

1. Validate the quality and usability of the event data.
2. Reconstruct actual purchase-to-pay process flows.
3. Identify common and unusual process variants.
4. Measure cycle time, waiting time, rework, and manual intervention.
5. Compare observed behaviour with documented process expectations.
6. Investigate factors associated with poor process performance.
7. Prioritise operational issues using transparent criteria.
8. Communicate findings, hypotheses, and limitations clearly.

## 7. In Scope

The project includes:

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

The BPI Challenge 2019 purchase-to-pay event log has been selected as the intended dataset.

At this stage:

- The dataset has not been downloaded into ProcessIQ.
- The dataset has not been profiled or validated.
- No analytical result has been produced.
- Published dataset descriptions are not treated as project findings.
- The original dataset will remain outside Git version control.

The project will record the official source, citation, licence, file integrity, and download date during the dataset-acquisition phase.

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

## 13. Planned Deliverables

The intended final deliverables are:

- Reproducible Python pipeline
- Data-quality report
- PostgreSQL analytical layer
- SQL validation queries
- Process-discovery analysis
- Process-variant analysis
- Conformance and compliance analysis
- Bottleneck and statistical analysis
- Improvement-priority matrix
- Focused Power BI management dashboard
- Automated tests
- Executive decision memo
- GitHub repository
- Portfolio case study
