#!/usr/bin/env bash

set -Eeuo pipefail

REPOSITORY_ROOT="$(
    cd "$(dirname "${BASH_SOURCE[0]}")/.."
    pwd
)"

cd "$REPOSITORY_ROOT"

PYTHON_COMMAND="${PYTHON_COMMAND:-python}"
MODE="${1:-fast}"
RAW_XES="data/raw/BPI_Challenge_2019.xes"
CURRENT_STAGE="initialisation"
PIPELINE_START=$SECONDS

usage() {
    printf '%s\n' \
        "Usage: ./scripts/run_pipeline.sh [fast|full]" \
        "" \
        "Modes:" \
        "  fast  Reuse extracted CSV files and rebuild analytical outputs." \
        "  full  Reprofile and re-extract the XES file before rebuilding." \
        "" \
        "The default mode is fast."
}

fail() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

handle_error() {
    local exit_status=$?
    printf \
        '\nERROR: Pipeline failed during "%s" near line %s.\n' \
        "$CURRENT_STAGE" \
        "$1" \
        >&2
    exit "$exit_status"
}

trap 'handle_error "$LINENO"' ERR

run_stage() {
    local stage_name="$1"
    shift

    local stage_start=$SECONDS
    CURRENT_STAGE="$stage_name"

    printf '\n[%s]\n' "$stage_name"
    "$@"

    printf \
        'Completed: %s (%s seconds)\n' \
        "$stage_name" \
        "$((SECONDS - stage_start))"
}

if (( $# > 1 ))
then
    usage >&2
    fail "Expected at most one argument: fast or full."
fi

case "$MODE" in
    -h|--help)
        usage
        exit 0
        ;;
    fast|full)
        ;;
    *)
        usage >&2
        fail "Mode must be either 'fast' or 'full'."
        ;;
esac

command -v "$PYTHON_COMMAND" >/dev/null 2>&1 ||
    fail "Python command not found: $PYTHON_COMMAND"

[[ -f "pyproject.toml" ]] ||
    fail "pyproject.toml is missing from the ProcessIQ repository."

[[ -f "scripts/check_pipeline.py" ]] ||
    fail "Missing scripts/check_pipeline.py. Copy both repair scripts."

"$PYTHON_COMMAND" -c "import processiq" ||
    fail "The processiq package is unavailable. Activate the virtual environment."

if [[ "$MODE" == "full" ]]
then
    [[ -s "$RAW_XES" ]] ||
        fail "Source XES file is missing: $RAW_XES"

    run_stage \
        "Profile source XES" \
        "$PYTHON_COMMAND" \
        -m processiq.inspect_xes \
        "$RAW_XES" \
        --output data/interim/xes_profile.json

    [[ -s "data/interim/xes_profile.json" ]] ||
        fail "Source profile is missing or empty."

    run_stage \
        "Extract XES tables" \
        "$PYTHON_COMMAND" \
        -m processiq.extract_xes \
        "$RAW_XES" \
        --progress-every 50000
else
    printf '%s\n' \
        "Fast mode: existing extracted CSV files will be reused."
fi

run_stage \
    "Validate extracted data" \
    "$PYTHON_COMMAND" \
    -m processiq.validate_data \
    --output data/interim/data_quality_report.json \
    --progress-every 250000

run_stage \
    "Enforce validation checks" \
    "$PYTHON_COMMAND" \
    scripts/check_pipeline.py validation

run_stage \
    "Build analytical tables" \
    "$PYTHON_COMMAND" \
    -m processiq.transform_data \
    --progress-every 250000

run_stage \
    "Discover process variants and models" \
    "$PYTHON_COMMAND" \
    -m processiq.discover_process

run_stage \
    "Analyse conformance" \
    "$PYTHON_COMMAND" \
    -m processiq.analyze_conformance \
    --progress-every 250000

run_stage \
    "Analyse bottlenecks" \
    "$PYTHON_COMMAND" \
    -m processiq.analyze_bottlenecks \
    --progress-every 250000

run_stage \
    "Prioritise improvement opportunities" \
    "$PYTHON_COMMAND" \
    -m processiq.prioritize_improvements

run_stage \
    "Build dashboard data" \
    "$PYTHON_COMMAND" \
    -m processiq.build_dashboard_data

CURRENT_STAGE="output verification"

REQUIRED_OUTPUTS=(
    "data/processed/cases.csv"
    "data/processed/events.csv"
    "data/processed/case_timing.csv"
    "data/processed/case_conformance.csv"
    "data/processed/transition_bottlenecks.csv"
    "data/processed/marker_duration_comparison.csv"
    "data/processed/improvement_priorities.csv"
    "data/processed/dashboard_cases.csv"
    "data/processed/dashboard_kpis.csv"
    "data/interim/conformance_report.json"
    "data/interim/bottleneck_report.json"
    "data/interim/improvement_priorities.json"
    "data/interim/dashboard_manifest.json"
    "data/interim/data_quality_report.json"
    "data/interim/process_discovery.json"
    "reports/figures/dfg_invoice_after_gr.svg"
    "reports/figures/process_tree_invoice_after_gr.svg"
)

MISSING_OUTPUT=0

for output_path in "${REQUIRED_OUTPUTS[@]}"
do
    if [[ ! -s "$output_path" ]]
    then
        printf 'Missing or empty output: %s\n' "$output_path" >&2
        MISSING_OUTPUT=1
    fi
done

if [[ "$MISSING_OUTPUT" -ne 0 ]]
then
    fail "Pipeline output verification failed."
fi

run_stage \
    "Verify dashboard checksums" \
    "$PYTHON_COMMAND" \
    scripts/check_pipeline.py dashboard

PIPELINE_ELAPSED=$((SECONDS - PIPELINE_START))

printf \
    '\nProcessIQ pipeline completed successfully in %sm %ss.\n' \
    "$((PIPELINE_ELAPSED / 60))" \
    "$((PIPELINE_ELAPSED % 60))"
