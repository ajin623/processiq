"""Validate the extracted ProcessIQ case and event tables."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from processiq.extract_xes import (
    CASE_HEADERS,
    EVENT_HEADERS,
)


EXPECTED_CASE_COUNT = 251_734
EXPECTED_EVENT_COUNT = 1_595_923

ANALYSIS_START_YEAR = 2018
ANALYSIS_END_YEAR = 2019

LONG_CASE_THRESHOLD_DAYS = 365
EXTREME_CASE_THRESHOLD_DAYS = 730

MISSING_MARKERS = frozenset(
    {
        "",
        "NONE",
        "UNKNOWN",
    }
)

VALID_BOOLEAN_VALUES = frozenset(
    {
        "true",
        "false",
    }
)

EXPECTED_ITEM_CATEGORIES = frozenset(
    {
        "2-way match",
        "3-way match, invoice after GR",
        "3-way match, invoice before GR",
        "Consignment",
    }
)

BOOLEAN_CASE_COLUMNS = (
    "gr_based_invoice_verification",
    "goods_receipt_required",
)


def is_missing(value: str | None) -> bool:
    """Return whether a value uses a recognised missing marker."""

    if value is None:
        return True

    return value.strip().upper() in MISSING_MARKERS


def parse_timestamp(value: str) -> datetime:
    """Convert an ISO timestamp into a Python datetime."""

    normalised_value = value.strip()

    if normalised_value.endswith("Z"):
        normalised_value = (
            f"{normalised_value[:-1]}+00:00"
        )

    return datetime.fromisoformat(normalised_value)


def validate_headers(
    reader: csv.DictReader,
    expected_headers: list[str],
    input_path: Path,
) -> None:
    """Require the CSV columns to match the defined schema."""

    actual_headers = list(reader.fieldnames or [])

    if actual_headers != expected_headers:
        raise ValueError(
            f"Unexpected columns in {input_path}.\n"
            f"Expected: {expected_headers}\n"
            f"Actual:   {actual_headers}"
        )


def sorted_counter(
    counter: Counter[str],
) -> dict[str, int]:
    """Convert a Counter into a predictably ordered dictionary."""

    return dict(sorted(counter.items()))


def validate_input_paths(
    cases_path: Path,
    events_path: Path,
) -> None:
    """Check that both extracted CSV files are available."""

    for input_path in (cases_path, events_path):
        if not input_path.exists():
            raise FileNotFoundError(
                f"Input CSV file does not exist: {input_path}"
            )

        if not input_path.is_file():
            raise ValueError(
                f"Input CSV path is not a file: {input_path}"
            )

    if cases_path.resolve() == events_path.resolve():
        raise ValueError(
            "Cases and events must use different input files."
        )


def validate_extracted_data(
    cases_path: Path,
    events_path: Path,
    output_path: Path | None = None,
    expected_case_count: int | None = None,
    expected_event_count: int | None = None,
    progress_every: int = 250_000,
) -> dict[str, object]:
    """Validate extracted case and event CSV files."""

    if progress_every < 0:
        raise ValueError("progress_every cannot be negative.")

    validate_input_paths(
        cases_path=cases_path,
        events_path=events_path,
    )

    case_count = 0
    missing_case_id_rows = 0
    duplicate_case_id_rows = 0

    case_ids: set[str] = set()
    case_missing_values: Counter[str] = Counter()
    item_category_counts: Counter[str] = Counter()
    unexpected_item_categories: Counter[str] = Counter()
    invalid_boolean_counts: Counter[str] = Counter()

    with cases_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as cases_file:
        cases_reader = csv.DictReader(cases_file)

        validate_headers(
            reader=cases_reader,
            expected_headers=CASE_HEADERS,
            input_path=cases_path,
        )

        for row in cases_reader:
            case_count += 1

            for column in CASE_HEADERS:
                if is_missing(row.get(column)):
                    case_missing_values[column] += 1

            case_id = row["case_id"].strip()

            if is_missing(case_id):
                missing_case_id_rows += 1
            elif case_id in case_ids:
                duplicate_case_id_rows += 1
            else:
                case_ids.add(case_id)

            item_category = row["item_category"].strip()

            if not is_missing(item_category):
                item_category_counts[item_category] += 1

                if (
                    item_category
                    not in EXPECTED_ITEM_CATEGORIES
                ):
                    unexpected_item_categories[
                        item_category
                    ] += 1

            for column in BOOLEAN_CASE_COLUMNS:
                boolean_value = row[column].strip().lower()

                if (
                    not is_missing(boolean_value)
                    and boolean_value
                    not in VALID_BOOLEAN_VALUES
                ):
                    invalid_boolean_counts[column] += 1

    event_count = 0
    missing_event_case_id_rows = 0
    orphan_event_rows = 0
    invalid_event_position_rows = 0
    nonsequential_event_position_rows = 0
    noncontiguous_case_blocks = 0

    missing_activity_events = 0
    missing_timestamp_events = 0
    invalid_timestamp_events = 0
    naive_timestamp_events = 0
    missing_resource_events = 0
    missing_amount_events = 0
    invalid_amount_events = 0

    same_timestamp_transitions = 0
    negative_timestamp_transitions = 0

    outside_analysis_window_events = 0
    outside_analysis_window_case_ids: set[str] = set()
    outside_analysis_window_by_year: Counter[str] = Counter()
    outside_window_activity_counts: Counter[str] = Counter()

    cases_over_365_days = 0
    cases_over_730_days = 0
    case_year_range_counts: Counter[str] = Counter()
    longest_case_span: dict[str, object] | None = None

    event_case_ids: set[str] = set()
    completed_case_blocks: set[str] = set()

    event_missing_values: Counter[str] = Counter()
    timestamp_year_counts: Counter[str] = Counter()
    missing_resource_by_activity: Counter[str] = Counter()

    minimum_timestamp: datetime | None = None
    maximum_timestamp: datetime | None = None

    current_case_id: str | None = None
    expected_event_position = 1
    previous_timestamp: datetime | None = None

    case_first_timestamp: datetime | None = None
    case_last_timestamp: datetime | None = None
    case_first_activity: str | None = None
    case_last_activity: str | None = None

    def finish_case_timing() -> None:
        """Record timing evidence for the completed case."""

        nonlocal cases_over_365_days
        nonlocal cases_over_730_days
        nonlocal longest_case_span

        if (
            current_case_id is None
            or case_first_timestamp is None
            or case_last_timestamp is None
        ):
            return

        duration_days = (
            case_last_timestamp - case_first_timestamp
        ).total_seconds() / 86_400

        year_range = (
            f"{case_first_timestamp.year}"
            f"->{case_last_timestamp.year}"
        )
        case_year_range_counts[year_range] += 1

        if duration_days > LONG_CASE_THRESHOLD_DAYS:
            cases_over_365_days += 1

        if duration_days > EXTREME_CASE_THRESHOLD_DAYS:
            cases_over_730_days += 1

        if (
            longest_case_span is None
            or duration_days
            > longest_case_span["duration_days"]
        ):
            longest_case_span = {
                "case_id": current_case_id,
                "duration_days": duration_days,
                "first_timestamp": (
                    case_first_timestamp.isoformat()
                ),
                "last_timestamp": (
                    case_last_timestamp.isoformat()
                ),
                "first_activity": case_first_activity,
                "last_activity": case_last_activity,
            }

    with events_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as events_file:
        events_reader = csv.DictReader(events_file)

        validate_headers(
            reader=events_reader,
            expected_headers=EVENT_HEADERS,
            input_path=events_path,
        )

        for row in events_reader:
            event_count += 1

            if (
                progress_every > 0
                and event_count % progress_every == 0
            ):
                print(
                    f"Validated {event_count:,} events..."
                )

            for column in EVENT_HEADERS:
                if is_missing(row.get(column)):
                    event_missing_values[column] += 1

            case_id = row["case_id"].strip()
            activity = row["activity"].strip()
            timestamp_value = row[
                "event_timestamp"
            ].strip()
            resource_id = row["resource_id"].strip()
            amount_value = row[
                "cumulative_net_worth"
            ].strip()

            new_case_block = case_id != current_case_id

            if new_case_block:
                finish_case_timing()

                if current_case_id is not None:
                    completed_case_blocks.add(
                        current_case_id
                    )

                if case_id in completed_case_blocks:
                    noncontiguous_case_blocks += 1

                current_case_id = case_id
                expected_event_position = 1
                previous_timestamp = None

                case_first_timestamp = None
                case_last_timestamp = None
                case_first_activity = None
                case_last_activity = None

            if is_missing(case_id):
                missing_event_case_id_rows += 1
            else:
                event_case_ids.add(case_id)

                if case_id not in case_ids:
                    orphan_event_rows += 1

            try:
                event_position = int(
                    row["event_position"]
                )
            except (TypeError, ValueError):
                invalid_event_position_rows += 1
            else:
                if (
                    event_position
                    != expected_event_position
                ):
                    nonsequential_event_position_rows += 1

            expected_event_position += 1

            if is_missing(activity):
                missing_activity_events += 1

            if is_missing(resource_id):
                missing_resource_events += 1

                resource_activity = (
                    activity
                    if not is_missing(activity)
                    else "<missing activity>"
                )
                missing_resource_by_activity[
                    resource_activity
                ] += 1

            parsed_timestamp: datetime | None = None

            if is_missing(timestamp_value):
                missing_timestamp_events += 1
            else:
                try:
                    parsed_timestamp = parse_timestamp(
                        timestamp_value
                    )
                except ValueError:
                    invalid_timestamp_events += 1
                else:
                    timestamp_year = (
                        parsed_timestamp.year
                    )
                    timestamp_year_counts[
                        str(timestamp_year)
                    ] += 1

                    if (
                        timestamp_year
                        < ANALYSIS_START_YEAR
                        or timestamp_year
                        > ANALYSIS_END_YEAR
                    ):
                        outside_analysis_window_events += 1
                        outside_analysis_window_case_ids.add(
                            case_id
                        )
                        outside_analysis_window_by_year[
                            str(timestamp_year)
                        ] += 1
                        outside_window_activity_counts[
                            f"{timestamp_year} | {activity}"
                        ] += 1

                    if (
                        parsed_timestamp.utcoffset()
                        is None
                    ):
                        naive_timestamp_events += 1
                        parsed_timestamp = None

            if parsed_timestamp is not None:
                if (
                    minimum_timestamp is None
                    or parsed_timestamp
                    < minimum_timestamp
                ):
                    minimum_timestamp = parsed_timestamp

                if (
                    maximum_timestamp is None
                    or parsed_timestamp
                    > maximum_timestamp
                ):
                    maximum_timestamp = parsed_timestamp

                if previous_timestamp is not None:
                    if (
                        parsed_timestamp
                        == previous_timestamp
                    ):
                        same_timestamp_transitions += 1
                    elif (
                        parsed_timestamp
                        < previous_timestamp
                    ):
                        negative_timestamp_transitions += 1

                if case_first_timestamp is None:
                    case_first_timestamp = parsed_timestamp
                    case_first_activity = activity

                case_last_timestamp = parsed_timestamp
                case_last_activity = activity

            previous_timestamp = parsed_timestamp

            if is_missing(amount_value):
                missing_amount_events += 1
            else:
                try:
                    Decimal(amount_value)
                except InvalidOperation:
                    invalid_amount_events += 1

    finish_case_timing()

    cases_without_events = len(
        case_ids - event_case_ids
    )

    case_count_matches_expected = (
        None
        if expected_case_count is None
        else case_count == expected_case_count
    )
    event_count_matches_expected = (
        None
        if expected_event_count is None
        else event_count == expected_event_count
    )

    structural_integrity_passed = all(
        issue_count == 0
        for issue_count in (
            missing_case_id_rows,
            duplicate_case_id_rows,
            missing_event_case_id_rows,
            orphan_event_rows,
            cases_without_events,
            invalid_event_position_rows,
            nonsequential_event_position_rows,
            noncontiguous_case_blocks,
        )
    )

    timestamp_scope_review_required = any(
        issue_count > 0
        for issue_count in (
            outside_analysis_window_events,
            cases_over_365_days,
        )
    )

    duration_metrics_ready = (
        all(
            issue_count == 0
            for issue_count in (
                missing_timestamp_events,
                invalid_timestamp_events,
                naive_timestamp_events,
                negative_timestamp_transitions,
            )
        )
        and not timestamp_scope_review_required
    )

    reconciliation_results = [
        result
        for result in (
            case_count_matches_expected,
            event_count_matches_expected,
        )
        if result is not None
    ]

    count_reconciliation_passed = (
        all(reconciliation_results)
        if reconciliation_results
        else None
    )

    report: dict[str, object] = {
        "input_files": {
            "cases": str(cases_path),
            "events": str(events_path),
        },
        "case_summary": {
            "row_count": case_count,
            "unique_case_id_count": len(case_ids),
            "missing_case_id_rows": missing_case_id_rows,
            "duplicate_case_id_rows": duplicate_case_id_rows,
            "missing_value_counts": sorted_counter(
                case_missing_values
            ),
            "item_category_counts": sorted_counter(
                item_category_counts
            ),
            "unexpected_item_categories": sorted_counter(
                unexpected_item_categories
            ),
            "invalid_boolean_counts": sorted_counter(
                invalid_boolean_counts
            ),
        },
        "event_summary": {
            "row_count": event_count,
            "missing_event_case_id_rows": (
                missing_event_case_id_rows
            ),
            "missing_activity_events": (
                missing_activity_events
            ),
            "missing_timestamp_events": (
                missing_timestamp_events
            ),
            "missing_resource_events": (
                missing_resource_events
            ),
            "missing_amount_events": (
                missing_amount_events
            ),
            "invalid_amount_events": (
                invalid_amount_events
            ),
            "missing_value_counts": sorted_counter(
                event_missing_values
            ),
            "missing_resource_by_activity": sorted_counter(
                missing_resource_by_activity
            ),
        },
        "relationship_checks": {
            "orphan_event_rows": orphan_event_rows,
            "cases_without_events": cases_without_events,
            "invalid_event_position_rows": (
                invalid_event_position_rows
            ),
            "nonsequential_event_position_rows": (
                nonsequential_event_position_rows
            ),
            "noncontiguous_case_blocks": (
                noncontiguous_case_blocks
            ),
        },
        "timestamp_checks": {
            "analysis_window": {
                "start_year": ANALYSIS_START_YEAR,
                "end_year": ANALYSIS_END_YEAR,
            },
            "minimum_timestamp": (
                minimum_timestamp.isoformat()
                if minimum_timestamp is not None
                else None
            ),
            "maximum_timestamp": (
                maximum_timestamp.isoformat()
                if maximum_timestamp is not None
                else None
            ),
            "invalid_timestamp_events": (
                invalid_timestamp_events
            ),
            "naive_timestamp_events": (
                naive_timestamp_events
            ),
            "same_timestamp_transitions": (
                same_timestamp_transitions
            ),
            "negative_timestamp_transitions": (
                negative_timestamp_transitions
            ),
            "outside_analysis_window_events": (
                outside_analysis_window_events
            ),
            "outside_analysis_window_cases": len(
                outside_analysis_window_case_ids
            ),
            "outside_analysis_window_by_year": (
                sorted_counter(
                    outside_analysis_window_by_year
                )
            ),
            "outside_window_activity_counts": (
                sorted_counter(
                    outside_window_activity_counts
                )
            ),
            "cases_over_365_days": (
                cases_over_365_days
            ),
            "cases_over_730_days": (
                cases_over_730_days
            ),
            "case_year_range_counts": sorted_counter(
                case_year_range_counts
            ),
            "longest_case_span": longest_case_span,
            "timestamp_year_counts": sorted_counter(
                timestamp_year_counts
            ),
        },
        "reconciliation": {
            "expected_case_count": expected_case_count,
            "actual_case_count": case_count,
            "case_count_matches_expected": (
                case_count_matches_expected
            ),
            "expected_event_count": expected_event_count,
            "actual_event_count": event_count,
            "event_count_matches_expected": (
                event_count_matches_expected
            ),
        },
        "status": {
            "structural_integrity_passed": (
                structural_integrity_passed
            ),
            "count_reconciliation_passed": (
                count_reconciliation_passed
            ),
            "timestamp_scope_review_required": (
                timestamp_scope_review_required
            ),
            "duration_metrics_ready": (
                duration_metrics_ready
            ),
        },
    }

    if output_path is not None:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_output = output_path.with_name(
            f"{output_path.name}.tmp"
        )

        try:
            temporary_output.write_text(
                json.dumps(
                    report,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary_output.replace(output_path)
        except BaseException:
            temporary_output.unlink(missing_ok=True)
            raise

    return report


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Validate extracted ProcessIQ case and event tables."
        )
    )

    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/interim/cases_raw.csv"),
        help="Path to the extracted cases CSV file.",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("data/interim/events_raw.csv"),
        help="Path to the extracted events CSV file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/interim/data_quality_report.json"
        ),
        help="Path for the generated JSON report.",
    )
    parser.add_argument(
        "--expected-case-count",
        type=int,
        default=EXPECTED_CASE_COUNT,
        help="Expected number of case rows.",
    )
    parser.add_argument(
        "--expected-event-count",
        type=int,
        default=EXPECTED_EVENT_COUNT,
        help="Expected number of event rows.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=250_000,
        help=(
            "Print progress after this many events. "
            "Use 0 to disable progress messages."
        ),
    )

    return parser


def main() -> None:
    """Run validation from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    report = validate_extracted_data(
        cases_path=arguments.cases,
        events_path=arguments.events,
        output_path=arguments.output,
        expected_case_count=(
            arguments.expected_case_count
        ),
        expected_event_count=(
            arguments.expected_event_count
        ),
        progress_every=arguments.progress_every,
    )

    status = report["status"]
    reconciliation = report["reconciliation"]

    print("Validation completed.")
    print(
        "Cases checked: "
        f"{reconciliation['actual_case_count']:,}"
    )
    print(
        "Events checked: "
        f"{reconciliation['actual_event_count']:,}"
    )
    print(
        "Structural integrity passed: "
        f"{status['structural_integrity_passed']}"
    )
    print(
        "Count reconciliation passed: "
        f"{status['count_reconciliation_passed']}"
    )
    print(
        "Timestamp review required: "
        f"{status['timestamp_scope_review_required']}"
    )
    print(
        "Duration metrics ready: "
        f"{status['duration_metrics_ready']}"
    )
    print(f"Report written to: {arguments.output}")


if __name__ == "__main__":
    main()
