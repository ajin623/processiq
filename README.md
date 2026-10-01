# ProcessIQ — Purchase-to-Pay Process Intelligence

ProcessIQ is a business process analysis and decision-support project that uses real enterprise event data to investigate purchase-to-pay process behaviour.

## Project Status

The project is currently under development.

Current phase: Project foundation and environment setup.

## Problem

Purchase-to-pay processes do not always follow one clean sequence.

Purchase items may experience repeated activities, long waiting periods, unexpected event sequences, excessive manual intervention, reversals, or missing process steps.

Traditional dashboards can show that performance is poor, but they often cannot explain which process paths are associated with delays, rework, or compliance concerns.

## Business Question

Which purchase-to-pay process deviations should an operations manager investigate first to reduce delayed invoice clearing and manual rework without weakening financial controls?

## Solution

ProcessIQ will reconstruct actual purchase-to-pay process flows from enterprise event data.

The project will:

- Validate the quality of the event data.
- Identify common and unusual process variants.
- Measure cycle times and activity-level waiting times.
- Detect rework and unexpected event sequences.
- Compare actual behaviour with expected process rules.
- Investigate factors associated with poor process performance.
- Prioritise evidence-based operational improvement opportunities.
- Communicate findings through a management dashboard and executive report.

## Dataset

The project will use the BPI Challenge 2019 purchase-to-pay event log.

The dataset contains anonymised event data from the purchase-order handling process of a multinational organisation.

The original dataset will not be stored in this Git repository.

## Technology Stack

Planned technologies:

- Python
- pandas
- PM4Py
- PostgreSQL
- SQL
- Matplotlib or Plotly
- Power BI
- pytest
- Git
- GitHub Actions

Technologies will be introduced only when justified by the analytical problem.

## Repository Structure

```text
processiq/
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── docs/
├── notebooks/
├── reports/
│   └── figures/
├── sql/
├── src/
│   └── processiq/
├── tests/
├── .gitignore
└── README.md