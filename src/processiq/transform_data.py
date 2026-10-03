"""Create database-ready analytical tables from validated CSV data."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from processiq.extract_xes import CASE_HEADERS, EVENT_HEADERS
from processiq.validate_data import (
    ANALYSIS_END_YEAR,
    ANALYSIS_START_YEAR,
    LONG_CASE_THRESHOLD_DAYS,
    is_missing,
    parse_timestamp,
)


PROCESSED_CASE_HEADERS = [
    *CASE_HEADERS,
    "spend_data_complete",
]

PROCESSED_EVENT_HEADERS = [
    *EVENT_HEADERS,
    "resource_recorded",
    "timestamp_in_analysis_window",
]

CASE_TIMING_HEADERS = [
    "case_id",
    "first_event_timestamp",
    "last_event_timestamp",
    "cycle_time_seconds",
    "cycle_time_days",
    "event_count",
    "outside_analysis_window_event_count",
    "has_negative_timestamp",
    "exceeds_365_days",
    "duration_eligible",
    "duration_exclusion_reason",
]

BOOLEAN_CASE_COLUMNS = (
    "gr_based_invoice_verification",
    "goods_receipt_required",
)

SPEND_COLUMNS = (
    "spend_classification",
    "spend_area",
    "sub_spend_area",
)


def boolean_text(value: bool) -> str:
    """Convert a Python boolean to database-friendly text."""

    return "true" if value else "false"


def clean_text(value: str | None) -> str:
    """Convert recognised missing markers to an empty value."""

    if is_missing(value):
        return ""

    return value.strip()


def format_number(value: float) -> str:
    """Format a calculated number without unnecessary zeroes."""

    return f"{value:.6f}".rstrip("0").rstrip(".")


def validate_paths(
    cases_input: Path,
    events_input: Path,
    cases_output: Path,
    events_output: Path,
    timing_output: Path,
) -> None:
    """Check that input and output paths are safe."""

    for input_path in (cases_input, events_input):
        if not input_path.exists():
            raise FileNotFoundError(
                f"Input file does not exist: {input_path}"
            )

        if not input_path.is_file():
            raise ValueError(
                f"Input path is not a file: {input_path}"
            )

    all_paths = {
        cases_input.resolve(),
        events_input.resolve(),
        cases_output.resolve(),
        events_output.resolve(),
        timing_output.resolve(),
    }

    if len(all_paths) != 5:
        raise ValueError(
            "Inputs and outputs must use different paths."
        )


def validate_headers(
    reader: csv.DictReader,
    expected_headers: list[str],
    input_path: Path,
) -> None:
    """Require the input CSV to use the expected schema."""

    actual_headers = list(reader.fieldnames or [])

    if actual_headers != expected_headers:
        raise ValueError(
            f"Unexpected columns in {input_path}.\n"
            f"Expected: {expected_headers}\n"
            f"Actual:   {actual_headers}"
        )


def transform_data(
    cases_input: Path,
    events_input: Path,
    cases_output: Path,
    events_output: Path,
    timing_output: Path,
    progress_every: int = 250_000,
) -> dict[str, int]:
    """Create cleaned cases, events, and case-timing tables."""

    if progress_every < 0:
        raise ValueError("progress_every cannot be negative.")

    validate_paths(
        cases_input=cases_input,
        events_input=events_input,
        cases_output=cases_output,
        events_output=events_output,
        timing_output=timing_output,
    )

    for output_path in (
        cases_output,
        events_output,
        timing_output,
    ):
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    temporary_cases = cases_output.with_name(
        f"{cases_output.name}.tmp"
    )
    temporary_events = events_output.with_name(
        f"{events_output.name}.tmp"
    )
    temporary_timing = timing_output.with_name(
        f"{timing_output.name}.tmp"
    )

    case_count = 0
    event_count = 0
    timing_count = 0
    duration_eligible_cases = 0
    duration_ineligible_cases = 0

    try:
        with (
            cases_input.open(
                mode="r",
                encoding="utf-8",
                newline="",
            ) as cases_input_file,
            temporary_cases.open(
                mode="w",
                encoding="utf-8",
                newline="",
            ) as cases_output_file,
        ):
            cases_reader = csv.DictReader(
                cases_input_file
            )
            validate_headers(
                reader=cases_reader,
                expected_headers=CASE_HEADERS,
                input_path=cases_input,
            )

            cases_writer = csv.DictWriter(
                cases_output_file,
                fieldnames=PROCESSED_CASE_HEADERS,
            )
            cases_writer.writeheader()

            for row in cases_reader:
                processed_row = {
                    column: clean_text(row[column])
                    for column in CASE_HEADERS
                }

                for column in BOOLEAN_CASE_COLUMNS:
                    processed_row[column] = (
                        clean_text(row[column]).lower()
                    )

                spend_data_complete = all(
                    not is_missing(row[column])
                    for column in SPEND_COLUMNS
                )
                processed_row["spend_data_complete"] = (
                    boolean_text(spend_data_complete)
                )

                cases_writer.writerow(processed_row)
                case_count += 1

        with (
            events_input.open(
                mode="r",
                encoding="utf-8",
                newline="",
            ) as events_input_file,
            temporary_events.open(
                mode="w",
                encoding="utf-8",
                newline="",
            ) as events_output_file,
            temporary_timing.open(
                mode="w",
                encoding="utf-8",
                newline="",
            ) as timing_output_file,
        ):
            events_reader = csv.DictReader(
                events_input_file
            )
            validate_headers(
                reader=events_reader,
                expected_headers=EVENT_HEADERS,
                input_path=events_input,
            )

            events_writer = csv.DictWriter(
                events_output_file,
                fieldnames=PROCESSED_EVENT_HEADERS,
            )
            events_writer.writeheader()

            timing_writer = csv.DictWriter(
                timing_output_file,
                fieldnames=CASE_TIMING_HEADERS,
            )
            timing_writer.writeheader()

            current_case_id: str | None = None
            first_timestamp: datetime | None = None
            last_timestamp: datetime | None = None
            previous_timestamp: datetime | None = None

            case_event_count = 0
            outside_window_event_count = 0
            has_negative_timestamp = False

            def write_case_timing() -> None:
                """Write timing and eligibility for one case."""

                nonlocal timing_count
                nonlocal duration_eligible_cases
                nonlocal duration_ineligible_cases

                if (
                    current_case_id is None
                    or first_timestamp is None
                    or last_timestamp is None
                ):
                    return

                cycle_time_seconds = (
                    last_timestamp - first_timestamp
                ).total_seconds()
                cycle_time_days = (
                    cycle_time_seconds / 86_400
                )

                exceeds_365_days = (
                    cycle_time_days
                    > LONG_CASE_THRESHOLD_DAYS
                )

                exclusion_reasons: list[str] = []

                if outside_window_event_count > 0:
                    exclusion_reasons.append(
                        "timestamp_outside_2018_2019"
                    )

                if has_negative_timestamp:
                    exclusion_reasons.append(
                        "negative_timestamp_sequence"
                    )

                if exceeds_365_days:
                    exclusion_reasons.append(
                        "cycle_time_over_365_days"
                    )

                duration_eligible = (
                    len(exclusion_reasons) == 0
                )

                if duration_eligible:
                    duration_eligible_cases += 1
                else:
                    duration_ineligible_cases += 1

                timing_writer.writerow(
                    {
                        "case_id": current_case_id,
                        "first_event_timestamp": (
                            first_timestamp.isoformat()
                        ),
                        "last_event_timestamp": (
                            last_timestamp.isoformat()
                        ),
                        "cycle_time_seconds": (
                            format_number(
                                cycle_time_seconds
                            )
                        ),
                        "cycle_time_days": (
                            format_number(
                                cycle_time_days
                            )
                        ),
                        "event_count": case_event_count,
                        "outside_analysis_window_event_count": (
                            outside_window_event_count
                        ),
                        "has_negative_timestamp": (
                            boolean_text(
                                has_negative_timestamp
                            )
                        ),
                        "exceeds_365_days": (
                            boolean_text(
                                exceeds_365_days
                            )
                        ),
                        "duration_eligible": (
                            boolean_text(
                                duration_eligible
                            )
                        ),
                        "duration_exclusion_reason": (
                            ";".join(exclusion_reasons)
                        ),
                    }
                )

                timing_count += 1

            for row in events_reader:
                case_id = clean_text(row["case_id"])
                timestamp = parse_timestamp(
                    row["event_timestamp"]
                )

                if case_id != current_case_id:
                    write_case_timing()

                    current_case_id = case_id
                    first_timestamp = timestamp
                    last_timestamp = timestamp
                    previous_timestamp = None

                    case_event_count = 0
                    outside_window_event_count = 0
                    has_negative_timestamp = False

                case_event_count += 1

                timestamp_in_window = (
                    ANALYSIS_START_YEAR
                    <= timestamp.year
                    <= ANALYSIS_END_YEAR
                )

                if not timestamp_in_window:
                    outside_window_event_count += 1

                if (
                    previous_timestamp is not None
                    and timestamp < previous_timestamp
                ):
                    has_negative_timestamp = True

                if first_timestamp is None:
                    first_timestamp = timestamp

                last_timestamp = timestamp
                previous_timestamp = timestamp

                resource_recorded = not is_missing(
                    row["resource_id"]
                )

                amount = Decimal(
                    row["cumulative_net_worth"]
                )

                processed_event = {
                    "case_id": case_id,
                    "event_position": str(
                        int(row["event_position"])
                    ),
                    "activity": clean_text(
                        row["activity"]
                    ),
                    "event_timestamp": (
                        timestamp.isoformat()
                    ),
                    "resource_id": clean_text(
                        row["resource_id"]
                    ),
                    "user_id": clean_text(
                        row["user_id"]
                    ),
                    "cumulative_net_worth": str(amount),
                    "resource_recorded": boolean_text(
                        resource_recorded
                    ),
                    "timestamp_in_analysis_window": (
                        boolean_text(
                            timestamp_in_window
                        )
                    ),
                }

                events_writer.writerow(processed_event)
                event_count += 1

                if (
                    progress_every > 0
                    and event_count % progress_every == 0
                ):
                    print(
                        f"Transformed {event_count:,} "
                        "events..."
                    )

            write_case_timing()

        temporary_cases.replace(cases_output)
        temporary_events.replace(events_output)
        temporary_timing.replace(timing_output)

    except BaseException:
        temporary_cases.unlink(missing_ok=True)
        temporary_events.unlink(missing_ok=True)
        temporary_timing.unlink(missing_ok=True)
        raise

    return {
        "case_count": case_count,
        "event_count": event_count,
        "timing_count": timing_count,
        "duration_eligible_cases": (
            duration_eligible_cases
        ),
        "duration_ineligible_cases": (
            duration_ineligible_cases
        ),
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Create database-ready ProcessIQ analytical tables."
        )
    )

    parser.add_argument(
        "--cases-input",
        type=Path,
        default=Path(
            "data/interim/cases_raw.csv"
        ),
        help="Path to the validated raw cases CSV.",
    )
    parser.add_argument(
        "--events-input",
        type=Path,
        default=Path(
            "data/interim/events_raw.csv"
        ),
        help="Path to the validated raw events CSV.",
    )
    parser.add_argument(
        "--cases-output",
        type=Path,
        default=Path(
            "data/processed/cases.csv"
        ),
        help="Path for processed cases.",
    )
    parser.add_argument(
        "--events-output",
        type=Path,
        default=Path(
            "data/processed/events.csv"
        ),
        help="Path for processed events.",
    )
    parser.add_argument(
        "--timing-output",
        type=Path,
        default=Path(
            "data/processed/case_timing.csv"
        ),
        help="Path for case timing and eligibility.",
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
    """Run the transformation pipeline."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    result = transform_data(
        cases_input=arguments.cases_input,
        events_input=arguments.events_input,
        cases_output=arguments.cases_output,
        events_output=arguments.events_output,
        timing_output=arguments.timing_output,
        progress_every=arguments.progress_every,
    )

    print("Transformation completed.")
    print(
        f"Cases written: {result['case_count']:,}"
    )
    print(
        f"Events written: {result['event_count']:,}"
    )
    print(
        "Timing rows written: "
        f"{result['timing_count']:,}"
    )
    print(
        "Duration-eligible cases: "
        f"{result['duration_eligible_cases']:,}"
    )
    print(
        "Duration-ineligible cases: "
        f"{result['duration_ineligible_cases']:,}"
    )
    print(f"Cases file: {arguments.cases_output}")
    print(f"Events file: {arguments.events_output}")
    print(f"Timing file: {arguments.timing_output}")


if __name__ == "__main__":
    main()
