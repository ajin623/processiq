"""Measure ProcessIQ cycle-time bottlenecks and marker associations.

The analysis uses duration-eligible cases only. It reports descriptive waiting
times, non-parametric marker comparisons, and effect sizes. None of these
associations is presented as proof that an activity causes delay.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.stats import mannwhitneyu


DEFAULT_CATEGORY = "3-way match, invoice after GR"
DEFAULT_CASES_INPUT = Path("data/processed/cases.csv")
DEFAULT_EVENTS_INPUT = Path("data/processed/events.csv")
DEFAULT_TIMING_INPUT = Path("data/processed/case_timing.csv")
DEFAULT_TRANSITION_OUTPUT = Path(
    "data/processed/transition_bottlenecks.csv"
)
DEFAULT_MARKER_OUTPUT = Path(
    "data/processed/marker_duration_comparison.csv"
)
DEFAULT_REPORT_OUTPUT = Path("data/interim/bottleneck_report.json")

REQUIRED_CASE_HEADERS = {"case_id", "item_category"}
REQUIRED_EVENT_HEADERS = {
    "case_id",
    "event_position",
    "activity",
    "event_timestamp",
}
REQUIRED_TIMING_HEADERS = {
    "case_id",
    "cycle_time_days",
    "event_count",
    "duration_eligible",
}

TRANSITION_OUTPUT_HEADERS = [
    "from_activity",
    "to_activity",
    "transition_count",
    "affected_cases",
    "zero_time_percentage",
    "median_wait_hours",
    "p75_wait_hours",
    "p90_wait_hours",
    "total_wait_days",
    "share_of_observed_wait",
]

MARKER_OUTPUT_HEADERS = [
    "marker",
    "cases_with_marker",
    "cases_without_marker",
    "median_days_with",
    "median_days_without",
    "median_difference_days",
    "p90_days_with",
    "p90_days_without",
    "average_events_with",
    "average_events_without",
    "mann_whitney_u",
    "raw_p_value",
    "adjusted_p_value",
    "rank_biserial_effect",
    "effect_magnitude",
    "statistically_significant",
]

MARKER_LABELS = {
    "multiple_goods_receipts": "Multiple goods receipts",
    "multiple_invoice_receipts": "Multiple invoice receipts",
    "multiple_service_entries": "Multiple service entries",
    "payment_block_intervention": "Payment-block intervention",
    "cancellation_activity": "Cancellation activity",
    "deletion_or_reactivation": "Deletion or reactivation",
    "change_activity": "Change activity",
}

OVERLAP_MARKERS = (
    "multiple_invoice_receipts",
    "cancellation_activity",
    "payment_block_intervention",
    "change_activity",
)


@dataclass
class TimingRecord:
    """Duration evidence used for one eligible case."""

    cycle_time_days: float
    event_count: int


@dataclass
class CaseFeatures:
    """Case-level diagnostic markers collected from source events."""

    goods_receipt_count: int = 0
    invoice_receipt_count: int = 0
    service_entry_count: int = 0
    payment_block_intervention: bool = False
    cancellation_activity: bool = False
    deletion_or_reactivation: bool = False
    change_activity: bool = False

    def record(self, activity: str) -> None:
        if activity == "Record Goods Receipt":
            self.goods_receipt_count += 1
        elif activity == "Record Invoice Receipt":
            self.invoice_receipt_count += 1
        elif activity == "Record Service Entry Sheet":
            self.service_entry_count += 1

        if activity in {"Set Payment Block", "Remove Payment Block"}:
            self.payment_block_intervention = True

        if activity.startswith("Cancel "):
            self.cancellation_activity = True

        if activity in {
            "Delete Purchase Order Item",
            "Reactivate Purchase Order Item",
        }:
            self.deletion_or_reactivation = True

        if activity.startswith("Change "):
            self.change_activity = True

    def marker_values(self) -> dict[str, bool]:
        return {
            "multiple_goods_receipts": self.goods_receipt_count > 1,
            "multiple_invoice_receipts": self.invoice_receipt_count > 1,
            "multiple_service_entries": self.service_entry_count > 1,
            "payment_block_intervention": self.payment_block_intervention,
            "cancellation_activity": self.cancellation_activity,
            "deletion_or_reactivation": self.deletion_or_reactivation,
            "change_activity": self.change_activity,
        }


def validate_input_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")


def validate_required_headers(
    reader: csv.DictReader,
    required_headers: set[str],
    path: Path,
) -> None:
    actual_headers = set(reader.fieldnames or [])
    missing_headers = sorted(required_headers - actual_headers)
    if missing_headers:
        raise ValueError(
            f"Missing required column(s) in {path}: "
            + ", ".join(missing_headers)
        )


def validate_distinct_paths(paths: Iterable[Path]) -> None:
    resolved_paths = [path.expanduser().resolve() for path in paths]
    if len(resolved_paths) != len(set(resolved_paths)):
        raise ValueError("Input and output paths must all be different.")


def parse_boolean(value: str, path: Path, line_number: int) -> bool:
    normalised = value.strip().lower()
    if normalised == "true":
        return True
    if normalised == "false":
        return False
    raise ValueError(
        f"Invalid Boolean in {path} at line {line_number}: {value!r}"
    )


def parse_timestamp(value: str, path: Path, line_number: int) -> datetime:
    normalised = value.strip()
    if normalised.endswith("Z"):
        normalised = f"{normalised[:-1]}+00:00"

    try:
        timestamp = datetime.fromisoformat(normalised)
    except ValueError as error:
        raise ValueError(
            f"Invalid timestamp in {path} at line {line_number}: {value!r}"
        ) from error

    if timestamp.tzinfo is None:
        raise ValueError(
            f"Timestamp lacks a timezone in {path} at line {line_number}."
        )
    return timestamp


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Cannot calculate a percentile for an empty group.")
    return float(np.quantile(np.asarray(values, dtype=float), probability))


def rounded(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def read_case_categories(
    cases_path: Path,
) -> tuple[dict[str, str], Counter[str]]:
    categories: dict[str, str] = {}
    category_counts: Counter[str] = Counter()

    with cases_path.open(encoding="utf-8", newline="") as cases_file:
        reader = csv.DictReader(cases_file)
        validate_required_headers(reader, REQUIRED_CASE_HEADERS, cases_path)

        for line_number, row in enumerate(reader, start=2):
            case_id = (row.get("case_id") or "").strip()
            category = (row.get("item_category") or "").strip()

            if not case_id or not category:
                raise ValueError(
                    f"Missing case_id or item_category in {cases_path} "
                    f"at line {line_number}."
                )
            if case_id in categories:
                raise ValueError(f"Duplicate case_id in {cases_path}: {case_id}")

            categories[case_id] = category
            category_counts[category] += 1

    return categories, category_counts


def read_case_timings(
    timing_path: Path,
    case_categories: dict[str, str],
    category_counts: Counter[str],
    selected_category: str,
) -> tuple[
    dict[str, TimingRecord],
    list[dict[str, object]],
]:
    category_durations: dict[str, list[float]] = defaultdict(list)
    category_event_counts: dict[str, list[float]] = defaultdict(list)
    eligible_counts: Counter[str] = Counter()
    timing_rows: Counter[str] = Counter()
    selected_timings: dict[str, TimingRecord] = {}

    with timing_path.open(encoding="utf-8", newline="") as timing_file:
        reader = csv.DictReader(timing_file)
        validate_required_headers(reader, REQUIRED_TIMING_HEADERS, timing_path)

        for line_number, row in enumerate(reader, start=2):
            case_id = (row.get("case_id") or "").strip()
            if case_id not in case_categories:
                raise ValueError(
                    f"Unknown case_id in {timing_path} at line "
                    f"{line_number}: {case_id!r}"
                )

            category = case_categories[case_id]
            timing_rows[category] += 1
            eligible = parse_boolean(
                row.get("duration_eligible") or "",
                timing_path,
                line_number,
            )
            if not eligible:
                continue

            try:
                duration = float(row.get("cycle_time_days") or "")
                event_count = int(row.get("event_count") or "")
            except ValueError as error:
                raise ValueError(
                    f"Invalid timing value in {timing_path} at line "
                    f"{line_number}."
                ) from error

            if duration < 0 or event_count <= 0:
                raise ValueError(
                    f"Invalid eligible timing in {timing_path} at line "
                    f"{line_number}."
                )

            eligible_counts[category] += 1
            category_durations[category].append(duration)
            category_event_counts[category].append(float(event_count))

            if category == selected_category:
                selected_timings[case_id] = TimingRecord(
                    cycle_time_days=duration,
                    event_count=event_count,
                )

    if sum(timing_rows.values()) != len(case_categories):
        raise ValueError("Case and timing row counts do not reconcile.")

    if not selected_timings:
        raise ValueError(
            "No duration-eligible cases found for category: "
            f"{selected_category}"
        )

    baseline: list[dict[str, object]] = []
    for category in sorted(category_counts):
        durations = category_durations[category]
        event_counts = category_event_counts[category]
        eligible_count = eligible_counts[category]

        baseline.append(
            {
                "item_category": category,
                "total_cases": category_counts[category],
                "eligible_cases": eligible_count,
                "excluded_cases": category_counts[category] - eligible_count,
                "median_days": rounded(percentile(durations, 0.50)),
                "p75_days": rounded(percentile(durations, 0.75)),
                "p90_days": rounded(percentile(durations, 0.90)),
                "p95_days": rounded(percentile(durations, 0.95)),
                "average_days": rounded(float(np.mean(durations))),
                "average_events": rounded(float(np.mean(event_counts))),
            }
        )

    baseline.sort(
        key=lambda row: float(row["median_days"]),
        reverse=True,
    )
    return selected_timings, baseline


def scan_selected_events(
    events_path: Path,
    selected_timings: dict[str, TimingRecord],
    progress_every: int,
) -> tuple[
    dict[str, CaseFeatures],
    dict[tuple[str, str], list[float]],
    dict[tuple[str, str], set[str]],
    Counter[tuple[str, str]],
    int,
    int,
]:
    selected_ids = set(selected_timings)
    features = {case_id: CaseFeatures() for case_id in selected_ids}
    previous_events: dict[str, tuple[int, str, datetime]] = {}
    transition_waits: dict[tuple[str, str], list[float]] = defaultdict(list)
    transition_cases: dict[tuple[str, str], set[str]] = defaultdict(set)
    zero_time_counts: Counter[tuple[str, str]] = Counter()
    events_scanned = 0
    selected_events = 0

    with events_path.open(encoding="utf-8", newline="") as events_file:
        reader = csv.DictReader(events_file)
        validate_required_headers(reader, REQUIRED_EVENT_HEADERS, events_path)

        for line_number, row in enumerate(reader, start=2):
            events_scanned += 1
            if progress_every and events_scanned % progress_every == 0:
                print(f"Scanned {events_scanned:,} events...")

            case_id = (row.get("case_id") or "").strip()
            if case_id not in selected_ids:
                continue

            selected_events += 1
            activity = (row.get("activity") or "").strip()
            if not activity:
                raise ValueError(
                    f"Missing activity in {events_path} at line {line_number}."
                )

            try:
                position = int(row.get("event_position") or "")
            except ValueError as error:
                raise ValueError(
                    f"Invalid event_position in {events_path} at line "
                    f"{line_number}."
                ) from error

            timestamp = parse_timestamp(
                row.get("event_timestamp") or "",
                events_path,
                line_number,
            )
            features[case_id].record(activity)

            previous = previous_events.get(case_id)
            if previous is not None:
                previous_position, previous_activity, previous_timestamp = previous
                if position <= previous_position:
                    raise ValueError(
                        f"Events are not ordered for case {case_id!r} in "
                        f"{events_path}."
                    )

                wait_hours = (
                    timestamp - previous_timestamp
                ).total_seconds() / 3600.0
                if wait_hours < 0:
                    raise ValueError(
                        f"Negative transition time for case {case_id!r}."
                    )

                transition = (previous_activity, activity)
                transition_waits[transition].append(wait_hours)
                transition_cases[transition].add(case_id)
                if wait_hours == 0:
                    zero_time_counts[transition] += 1

            previous_events[case_id] = (position, activity, timestamp)

    return (
        features,
        transition_waits,
        transition_cases,
        zero_time_counts,
        events_scanned,
        selected_events,
    )


def summarise_transitions(
    transition_waits: dict[tuple[str, str], list[float]],
    transition_cases: dict[tuple[str, str], set[str]],
    zero_time_counts: Counter[tuple[str, str]],
) -> list[dict[str, object]]:
    total_wait_hours = sum(
        sum(waits) for waits in transition_waits.values()
    )
    summaries: list[dict[str, object]] = []

    for transition, waits in transition_waits.items():
        from_activity, to_activity = transition
        transition_total = float(sum(waits))
        summaries.append(
            {
                "from_activity": from_activity,
                "to_activity": to_activity,
                "transition_count": len(waits),
                "affected_cases": len(transition_cases[transition]),
                "zero_time_percentage": rounded(
                    100.0 * zero_time_counts[transition] / len(waits)
                ),
                "median_wait_hours": rounded(percentile(waits, 0.50)),
                "p75_wait_hours": rounded(percentile(waits, 0.75)),
                "p90_wait_hours": rounded(percentile(waits, 0.90)),
                "total_wait_days": rounded(transition_total / 24.0),
                "share_of_observed_wait": rounded(
                    100.0 * transition_total / total_wait_hours
                    if total_wait_hours
                    else 0.0
                ),
            }
        )

    summaries.sort(
        key=lambda row: (
            float(row["total_wait_days"]),
            int(row["transition_count"]),
        ),
        reverse=True,
    )
    return summaries


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Control the false-discovery rate across related marker tests."""

    count = len(p_values)
    order = sorted(range(count), key=p_values.__getitem__)
    adjusted = [0.0] * count
    running_minimum = 1.0

    for reverse_rank, index in enumerate(reversed(order), start=1):
        rank = count - reverse_rank + 1
        candidate = p_values[index] * count / rank
        running_minimum = min(running_minimum, candidate)
        adjusted[index] = min(1.0, running_minimum)

    return adjusted


def effect_magnitude(effect: float) -> str:
    absolute_effect = abs(effect)
    if absolute_effect < 0.147:
        return "negligible"
    if absolute_effect < 0.330:
        return "small"
    if absolute_effect < 0.474:
        return "medium"
    return "large"


def compare_markers(
    selected_timings: dict[str, TimingRecord],
    features: dict[str, CaseFeatures],
) -> list[dict[str, object]]:
    comparisons: list[dict[str, object]] = []
    raw_p_values: list[float] = []

    for marker_key, marker_label in MARKER_LABELS.items():
        with_durations: list[float] = []
        without_durations: list[float] = []
        with_event_counts: list[float] = []
        without_event_counts: list[float] = []

        for case_id, timing in selected_timings.items():
            is_present = features[case_id].marker_values()[marker_key]
            if is_present:
                with_durations.append(timing.cycle_time_days)
                with_event_counts.append(float(timing.event_count))
            else:
                without_durations.append(timing.cycle_time_days)
                without_event_counts.append(float(timing.event_count))

        if not with_durations or not without_durations:
            raise ValueError(
                f"Marker comparison has an empty group: {marker_label}"
            )

        test_result = mannwhitneyu(
            with_durations,
            without_durations,
            alternative="two-sided",
            method="asymptotic",
        )
        u_statistic = float(test_result.statistic)
        raw_p_value = float(test_result.pvalue)
        rank_biserial = (
            2.0 * u_statistic
            / (len(with_durations) * len(without_durations))
            - 1.0
        )

        comparisons.append(
            {
                "marker": marker_label,
                "cases_with_marker": len(with_durations),
                "cases_without_marker": len(without_durations),
                "median_days_with": rounded(
                    percentile(with_durations, 0.50)
                ),
                "median_days_without": rounded(
                    percentile(without_durations, 0.50)
                ),
                "median_difference_days": rounded(
                    percentile(with_durations, 0.50)
                    - percentile(without_durations, 0.50)
                ),
                "p90_days_with": rounded(percentile(with_durations, 0.90)),
                "p90_days_without": rounded(
                    percentile(without_durations, 0.90)
                ),
                "average_events_with": rounded(
                    float(np.mean(with_event_counts))
                ),
                "average_events_without": rounded(
                    float(np.mean(without_event_counts))
                ),
                "mann_whitney_u": rounded(u_statistic, 1),
                "raw_p_value": raw_p_value,
                "adjusted_p_value": 0.0,
                "rank_biserial_effect": rounded(rank_biserial, 4),
                "effect_magnitude": effect_magnitude(rank_biserial),
                "statistically_significant": False,
            }
        )
        raw_p_values.append(raw_p_value)

    adjusted_values = benjamini_hochberg(raw_p_values)
    for comparison, adjusted_value in zip(
        comparisons,
        adjusted_values,
        strict=True,
    ):
        comparison["adjusted_p_value"] = adjusted_value
        comparison["statistically_significant"] = adjusted_value < 0.05

    comparisons.sort(
        key=lambda row: float(row["median_difference_days"]),
        reverse=True,
    )
    return comparisons


def summarise_marker_overlap(
    selected_timings: dict[str, TimingRecord],
    features: dict[str, CaseFeatures],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    score_durations: dict[int, list[float]] = defaultdict(list)
    score_event_counts: dict[int, list[float]] = defaultdict(list)
    combinations: dict[tuple[str, ...], list[float]] = defaultdict(list)

    for case_id, timing in selected_timings.items():
        marker_values = features[case_id].marker_values()
        present_markers = tuple(
            MARKER_LABELS[key]
            for key in OVERLAP_MARKERS
            if marker_values[key]
        )
        score = len(present_markers)
        score_durations[score].append(timing.cycle_time_days)
        score_event_counts[score].append(float(timing.event_count))
        combinations[present_markers].append(timing.cycle_time_days)

    score_summary = [
        {
            "marker_count": score,
            "case_count": len(durations),
            "median_days": rounded(percentile(durations, 0.50)),
            "p90_days": rounded(percentile(durations, 0.90)),
            "average_events": rounded(float(np.mean(score_event_counts[score]))),
        }
        for score, durations in sorted(score_durations.items())
    ]

    combination_summary = []
    for combination, durations in combinations.items():
        combination_summary.append(
            {
                "markers": list(combination),
                "marker_count": len(combination),
                "case_count": len(durations),
                "median_days": rounded(percentile(durations, 0.50)),
                "p90_days": rounded(percentile(durations, 0.90)),
            }
        )

    combination_summary.sort(
        key=lambda row: (
            int(row["case_count"]),
            -int(row["marker_count"]),
        ),
        reverse=True,
    )
    return score_summary, combination_summary


def write_csv(
    path: Path,
    headers: list[str],
    rows: list[dict[str, object]],
) -> None:
    with path.open(mode="w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def temporary_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.tmp")


def write_outputs(
    transition_output: Path,
    marker_output: Path,
    report_output: Path,
    transition_rows: list[dict[str, object]],
    marker_rows: list[dict[str, object]],
    report: dict[str, object],
) -> None:
    for path in (transition_output, marker_output, report_output):
        path.parent.mkdir(parents=True, exist_ok=True)

    transition_temporary = temporary_path(transition_output)
    marker_temporary = temporary_path(marker_output)
    report_temporary = temporary_path(report_output)

    try:
        write_csv(
            transition_temporary,
            TRANSITION_OUTPUT_HEADERS,
            transition_rows,
        )
        write_csv(marker_temporary, MARKER_OUTPUT_HEADERS, marker_rows)
        with report_temporary.open(mode="w", encoding="utf-8") as report_file:
            json.dump(report, report_file, indent=2, sort_keys=True)
            report_file.write("\n")

        os.replace(transition_temporary, transition_output)
        os.replace(marker_temporary, marker_output)
        os.replace(report_temporary, report_output)
    finally:
        transition_temporary.unlink(missing_ok=True)
        marker_temporary.unlink(missing_ok=True)
        report_temporary.unlink(missing_ok=True)


def analyze_bottlenecks(
    cases_path: Path,
    events_path: Path,
    timing_path: Path,
    transition_output: Path,
    marker_output: Path,
    report_output: Path,
    category: str = DEFAULT_CATEGORY,
    minimum_transition_cases: int = 100,
    top_transitions: int = 20,
    progress_every: int = 0,
) -> dict[str, object]:
    if minimum_transition_cases <= 0:
        raise ValueError("minimum_transition_cases must be positive.")
    if top_transitions <= 0:
        raise ValueError("top_transitions must be positive.")
    if progress_every < 0:
        raise ValueError("progress_every must be zero or greater.")
    if not category.strip():
        raise ValueError("category must not be empty.")

    for path in (cases_path, events_path, timing_path):
        validate_input_file(path)
    validate_distinct_paths(
        (
            cases_path,
            events_path,
            timing_path,
            transition_output,
            marker_output,
            report_output,
        )
    )

    case_categories, category_counts = read_case_categories(cases_path)
    if category not in category_counts:
        raise ValueError(f"No cases found for category: {category}")

    selected_timings, category_baseline = read_case_timings(
        timing_path,
        case_categories,
        category_counts,
        category,
    )
    (
        features,
        transition_waits,
        transition_cases,
        zero_time_counts,
        events_scanned,
        selected_events,
    ) = scan_selected_events(
        events_path,
        selected_timings,
        progress_every,
    )

    observed_case_ids = set()
    for case_ids in transition_cases.values():
        observed_case_ids.update(case_ids)
    single_event_or_missing_cases = len(selected_timings) - len(observed_case_ids)

    transition_rows = summarise_transitions(
        transition_waits,
        transition_cases,
        zero_time_counts,
    )
    marker_rows = compare_markers(selected_timings, features)
    overlap_scores, marker_combinations = summarise_marker_overlap(
        selected_timings,
        features,
    )

    focused_transitions = [
        row
        for row in transition_rows
        if int(row["affected_cases"]) >= minimum_transition_cases
    ][:top_transitions]

    report: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "selected_category": category,
            "total_selected_cases": category_counts[category],
            "duration_eligible_selected_cases": len(selected_timings),
            "duration_excluded_selected_cases": (
                category_counts[category] - len(selected_timings)
            ),
            "selected_events_in_eligible_cases": selected_events,
            "all_events_scanned": events_scanned,
            "single_event_or_missing_selected_cases": (
                single_event_or_missing_cases
            ),
        },
        "category_cycle_time_baseline": category_baseline,
        "transition_analysis": {
            "unique_transitions": len(transition_rows),
            "minimum_affected_cases_for_focus": minimum_transition_cases,
            "top_transition_limit": top_transitions,
            "focused_transitions": focused_transitions,
        },
        "marker_comparisons": marker_rows,
        "overlap_marker_definition": [
            MARKER_LABELS[key] for key in OVERLAP_MARKERS
        ],
        "overlap_score_summary": overlap_scores,
        "marker_combination_summary": marker_combinations,
        "statistical_method": {
            "test": "Two-sided Mann-Whitney U",
            "multiple_testing_adjustment": "Benjamini-Hochberg",
            "effect_size": (
                "Rank-biserial correlation; positive values indicate longer "
                "durations among cases with the marker."
            ),
            "significance_threshold": 0.05,
        },
        "limitations": [
            "Waiting times are calendar time, not working time.",
            "Associations do not establish causation.",
            "A purchase-order-item case can contain multiple related documents.",
            "Repeated receipt or service-entry events can be legitimate batch postings.",
            "Incomplete traces are not interpreted as completed-process durations.",
        ],
    }

    write_outputs(
        transition_output,
        marker_output,
        report_output,
        transition_rows,
        marker_rows,
        report,
    )
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse ProcessIQ cycle-time bottlenecks and marker associations."
        )
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_INPUT,
        help="Path to processed cases.",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS_INPUT,
        help="Path to processed events.",
    )
    parser.add_argument(
        "--timing",
        type=Path,
        default=DEFAULT_TIMING_INPUT,
        help="Path to processed case timing.",
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Item category used for detailed analysis.",
    )
    parser.add_argument(
        "--transition-output",
        type=Path,
        default=DEFAULT_TRANSITION_OUTPUT,
        help="Path for transition waiting-time results.",
    )
    parser.add_argument(
        "--marker-output",
        type=Path,
        default=DEFAULT_MARKER_OUTPUT,
        help="Path for marker duration comparisons.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
        help="Path for the JSON bottleneck report.",
    )
    parser.add_argument(
        "--minimum-transition-cases",
        type=int,
        default=100,
        help="Minimum affected cases for a focused transition.",
    )
    parser.add_argument(
        "--top-transitions",
        type=int,
        default=20,
        help="Maximum focused transitions in the JSON report.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=250_000,
        help=(
            "Print progress after this many scanned events. "
            "Use 0 to disable progress messages."
        ),
    )
    return parser


def main() -> None:
    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        report = analyze_bottlenecks(
            cases_path=arguments.cases,
            events_path=arguments.events,
            timing_path=arguments.timing,
            transition_output=arguments.transition_output,
            marker_output=arguments.marker_output,
            report_output=arguments.report_output,
            category=arguments.category,
            minimum_transition_cases=arguments.minimum_transition_cases,
            top_transitions=arguments.top_transitions,
            progress_every=arguments.progress_every,
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        parser.error(str(error))

    scope = report["scope"]
    transition_analysis = report["transition_analysis"]
    print("Bottleneck analysis completed.")
    print(f"Category: {scope['selected_category']}")
    print(
        "Duration-eligible cases: "
        f"{scope['duration_eligible_selected_cases']:,}"
    )
    print(
        "Selected events analysed: "
        f"{scope['selected_events_in_eligible_cases']:,}"
    )
    print(
        "Unique transitions: "
        f"{transition_analysis['unique_transitions']:,}"
    )
    print(f"Transition output: {arguments.transition_output}")
    print(f"Marker output: {arguments.marker_output}")
    print(f"Report output: {arguments.report_output}")


if __name__ == "__main__":
    main()
