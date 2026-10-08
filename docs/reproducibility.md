# Reproducing ProcessIQ

Reference implementation: commit `5e191f1`. On 8 October 2026, all **92 tests passed**, and a full source-to-dashboard-data run completed successfully in approximately **2 minutes 33 seconds** on the development machine. This guide describes that implemented workflow; it does not claim a fresh environment or live PostgreSQL run was independently tested during documentation preparation.

## 1. Environment

The pipeline runs in Bash with Python **3.12**. The development environment is Ubuntu 24.04 under WSL; Power BI Desktop runs on Windows.

For an Ubuntu environment missing the system prerequisites:

```bash
sudo apt update
sudo apt install python3.12-venv graphviz curl
```

Obtain the repository, or use the existing checkout:

```bash
git clone https://github.com/ajin623/processiq.git
cd processiq
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python --version
dot -V
```

The [project configuration](../pyproject.toml) pins direct Python dependencies. It is not a complete lockfile of transitive packages or operating-system tools. Record `python -m pip freeze`, Python version, and Graphviz version when comparing environments.

These commands run inside Ubuntu. Microsoft's distribution-listing command is `wsl.exe --list --quiet` from a suitable Windows/WSL environment; the Ubuntu package named `wsl` is a different tool and is not required for this project. See [Microsoft's WSL command reference](https://learn.microsoft.com/en-us/windows/wsl/basic-commands).

## 2. Source data

Download the XES using the source recorded in [data-source.md](data-source.md). The original and generated datasets are ignored by Git. From the repository root, the following downloads only when the target is absent or empty:

```bash
mkdir -p data/raw data/interim data/processed
if [ ! -s data/raw/BPI_Challenge_2019.xes ]; then
    curl --fail --location --retry 3 \
        https://ndownloader.figshare.com/files/24072995 \
        --output data/raw/BPI_Challenge_2019.xes
fi
```

Check the file against the recorded acquisition digest before using it:

```bash
printf '%s\n' 'af63bc687fc4152f2123b05c3af7772b37ef3fce2d3f67f812666c9e356baae7  data/raw/BPI_Challenge_2019.xes' | sha256sum --check
```

The recorded file is 728,558,522 bytes. A mismatch requires checking the download and source version; do not replace the expected digest merely to make the check pass. A partial interrupted download can leave a nonempty file, so the digest check matters.

## 3. Run tests

With the virtual environment active:

```bash
python -m unittest discover -s tests -v
```

Expected at the reference commit: `Ran 92 tests` followed by `OK`. Tests use small fixtures, including a synthetic XES log. Coverage includes extraction, malformed inputs, timing exclusions, conformance, marker statistics, ranking, dashboard joins, validation gates, and altered-file detection. The reported test count is tied to this version and can change with later development.

## 4. Run the pipeline

First run from the source XES:

```bash
time ./scripts/run_pipeline.sh full
```

Subsequent analytical rebuilds can reuse extracted raw CSVs:

```bash
time ./scripts/run_pipeline.sh fast
```

`fast` is the default. It still validates, transforms, discovers models, analyses conformance and bottlenecks, ranks investigations, and rebuilds dashboard data. It skips only source profiling and extraction. It requires `data/interim/cases_raw.csv` and `data/interim/events_raw.csv`; use `full` if they are missing.

The runner changes to the repository root automatically. An alternative Python executable can be supplied as one path:

```bash
PYTHON_COMMAND="$PWD/.venv/bin/python" ./scripts/run_pipeline.sh fast
```

Do not paste `run_stage` calls into an interactive terminal: the function is defined inside the runner. Use the runner or a module's documented command, such as `python -m processiq.analyze_bottlenecks --help`.

| Stage | Main output |
|---|---|
| Source profile, full mode | `data/interim/xes_profile.json` |
| Extraction, full mode | `data/interim/cases_raw.csv`, `events_raw.csv` |
| Validation and enforcement | `data/interim/data_quality_report.json` |
| Transformation | `data/processed/cases.csv`, `events.csv`, `case_timing.csv` |
| Discovery | `data/interim/process_discovery.json`; DFG and process-tree SVGs in `reports/figures` |
| Conformance | `data/processed/case_conformance.csv`, `data/interim/conformance_report.json` |
| Bottlenecks | `data/processed/transition_bottlenecks.csv`, `marker_duration_comparison.csv`, and `data/interim/bottleneck_report.json` |
| Prioritisation | `data/processed/improvement_priorities.csv`, `data/interim/improvement_priorities.json` |
| Dashboard build and checks | `data/processed/dashboard_cases.csv`, `dashboard_kpis.csv`, and `data/interim/dashboard_manifest.json` |

## 5. Interpret completion and validation

Expected reconciliations for the reference data:

| Check | Expected |
|---|---:|
| Cases / events | 251,734 / 1,595,923 |
| Duration-eligible / excluded cases, all categories | 251,380 / 354 |
| Selected-category cases / events | 15,182 / 319,233 |
| Selected eligible cases / events | 15,045 / 302,275 |
| Conforming / incomplete / review-required cases | 9,667 / 5,506 / 9 |
| Ranked opportunities | 5 |
| Dashboard cases | 251,734 rows, 48 columns |
| Dashboard KPIs | 45 rows, 9 columns |

`Timestamp review required: True` and `Duration metrics ready: False` in the raw validation report are expected for this dataset. Structural integrity and count reconciliation must pass; transformation then excludes flagged cases from duration summaries. Do not remove the exclusions to suppress the warning.

The runner stops on failed commands, checks required outputs are nonempty, and verifies both dashboard CSV sizes and SHA-256 hashes against the manifest. The individual checks can also be run after generation:

```bash
python scripts/check_pipeline.py validation
python scripts/check_pipeline.py dashboard
```

Only treat the rebuild as complete after the final success message. The pipeline writes stage outputs as it proceeds and is not a single atomic transaction; a failed run can leave a mixture of old and new outputs. Resolve the error and rerun successfully before refreshing the report. The full runner does not execute the automated test suite itself.

The manifest protects consistency of the two generated dashboard files. It does not verify the PBIX, PDF, every upstream file, or business interpretation. Generation timestamps can differ on repeated runs; bit-identical JSON or SVG output is not promised.

## 6. Optional PostgreSQL path

The repository includes three implemented SQL scripts. They are not called by the Python/Bash runner and are not required by the CSV-backed dashboard.

| Script | Purpose |
|---|---|
| [01_schema.sql](../sql/01_schema.sql) | Creates the `processiq` schema and constrained case, event, and timing tables |
| [02_load.sql](../sql/02_load.sql) | Loads the processed CSVs using client-side `\copy` |
| [03_analytical_layer.sql](../sql/03_analytical_layer.sql) | Creates indexes, case-overview and transition views, and prints reconciliation queries |

With PostgreSQL installed and a suitable local role available, use a dedicated database. Run from the repository root after successful transformation:

```bash
createdb processiq
psql -X -v ON_ERROR_STOP=1 -d processiq -f sql/01_schema.sql
psql -X -v ON_ERROR_STOP=1 -d processiq -f sql/02_load.sql
psql -X -v ON_ERROR_STOP=1 -d processiq -f sql/03_analytical_layer.sql
```

This sequence assumes a new database. Schema, indexes, and views are created without `IF NOT EXISTS`; do not blindly rerun creation scripts against an existing deployment. The loader explicitly truncates the three ProcessIQ tables before loading them within a transaction. Use it only for the dedicated analytical database whose contents you intend to replace.

Expected counts include 251,734 cases, 1,595,923 events, 251,734 timing rows, and 1,344,189 adjacent-event transitions. Inspect the printed reconciliation results. This database path needs its own execution evidence; a successful CSV pipeline run does not prove that the SQL scripts were executed.

## 7. Refresh and check Power BI

Open [ProcessIQ_Dashboard.pbix](../reports/dashboard/ProcessIQ_Dashboard.pbix) in Power BI Desktop. Update its source-file locations to the processed CSVs on your machine, then refresh. For WSL, use the Windows-visible location of the Ubuntu project files. A clone can display cached imported data even when its original local source paths no longer work.

Check explicit Power Query types rather than relying entirely on CSV detection:

| Fields | Intended type / handling |
|---|---|
| Case, item, document, and vendor identifiers | Text |
| Eligibility and scope flags | True/False |
| Counts and rank | Whole number |
| Duration, difference, score, effect, and p-value | Decimal number |
| Status, category, and marker | Text |
| Timestamp columns | Parse the recorded timezone consistently; preserve the intended instant |

If decimal text uses a dot while the workstation locale expects a comma, set a compatible conversion locale. Microsoft documents [Power Query data types and locale handling](https://learn.microsoft.com/en-us/power-query/data-types).

Before exporting, verify these report behaviours:

1. The executive total is 251,734 cases and 1,595,923 events; duration summaries exclude ineligible cases.
2. Conformance uses the 15,182-case scope: 9,667 conforming, 5,506 incomplete, and 9 review-required, with no out-of-scope blank slice.
3. Bottleneck duration measures use the 15,045-case eligible cohort and show 63.10 median and 128.30 P90 days.
4. Marker charts use the numeric difference or its measure, not `Count of median_difference_days`.
5. Percentages use consistent units: transition wait shares are already percentage points (for example, 24.32); a rate stored as 0.6367 can be formatted as 63.67%. Do not multiply by 100 twice.
6. Medians, percentiles, and scores are not summed across unrelated summary rows. Pre-aggregated evidence tables are not automatically recalculated by case-level slicers without a valid filtering design.
7. Long labels, recommendations, and decision cautions remain readable in the static export. Widen columns, enable wrapping, or give long text more space; visual scrollbars do not make off-screen text visible in a PDF.

The current PDF has four pages. Some table content is clipped in the committed snapshots; [findings.md](findings.md) supplies full explanations. Re-export the PDF and images after presentation changes. The pipeline does not refresh or export Power BI automatically.

## 8. Export images and record changes

After exporting the updated Power BI report as `reports/dashboard/ProcessIQ_Dashboard.pdf`, install `poppler-utils` if needed, then run:

```bash
mkdir -p docs/images
pdfinfo reports/dashboard/ProcessIQ_Dashboard.pdf
pdftoppm -png -r 120 reports/dashboard/ProcessIQ_Dashboard.pdf docs/images/processiq-dashboard
```

This generates page images with suffixes `-1.png` through `-4.png` for the four-page report. Keep filenames with a single `.pbix` or `.pdf` extension. The recorded export produced 1660 × 960 PNGs.

Review `git status --short` and `git diff --check`. Stage intended code, documentation, and report artifacts explicitly. Raw and processed data, generated JSON, and generated process SVGs remain ignored. A clean working tree confirms version-control state; it does not replace pipeline or report validation.
