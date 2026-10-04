"""Build dashboard-ready ProcessIQ tables and a reproducibility manifest.

The existing processed event table remains the event-level fact table. This
module creates a single case-level analytical table, a compact long-form KPI
table, and a manifest describing the dashboard model and generated artifacts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path("data/processed/cases.csv")
DEFAULT_EVENTS = Path("data/processed/events.csv")
DEFAULT_TIMING = Path("data/processed/case_timing.csv")
DEFAULT_CONFORMANCE = Path("data/processed/case_conformance.csv")
DEFAULT_BOTTLENECK_REPORT = Path("data/interim/bottleneck_report.json")
DEFAULT_CONFORMANCE_REPORT = Path("data/interim/conformance_report.json")
DEFAULT_PRIORITY_REPORT = Path("data/interim/improvement_priorities.json")
DEFAULT_CASE_OUTPUT = Path("data/processed/dashboard_cases.csv")
DEFAULT_KPI_OUTPUT = Path("data/processed/dashboard_kpis.csv")
DEFAULT_MANIFEST_OUTPUT = Path("data/interim/dashboard_manifest.json")

CASE_HEADERS = [
    "case_id",
    "purchasing_document_id",
    "item_id",
    "item_type",
    "gr_based_invoice_verification",
    "goods_receipt_required",
    "source_system_id",
    "purchasing_document_category",
    "company_id",
    "spend_classification",
    "spend_area",
    "sub_spend_area",
    "vendor_id",
    "vendor_name",
    "document_type",
    "item_category",
    "spend_data_complete",
]

EVENT_HEADERS = [
    "case_id",
    "event_position",
    "activity",
    "event_timestamp",
    "resource_id",
    "user_id",
    "cumulative_net_worth",
    "resource_recorded",
    "timestamp_in_analysis_window",
]

TIMING_HEADERS = [
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

CONFORMANCE_HEADERS = [
    "case_id",
    "item_category",
    "conformance_status",
    "goods_receipt_before_invoice_receipt_rule",
    "invoice_receipt_before_clearing_rule",
    "review_reason",
    "event_count",
    "first_purchase_order_position",
    "first_goods_receipt_position",
    "first_invoice_receipt_position",
    "first_clearing_position",
    "goods_receipt_count",
    "invoice_receipt_count",
    "clearing_count",
    "service_entry_count",
    "multiple_goods_receipts",
    "multiple_invoice_receipts",
    "multiple_service_entries",
    "payment_block_intervention",
    "cancellation_activity",
    "deletion_or_reactivation",
    "change_activity",
    "vendor_invoice_before_goods_receipt",
]

TIMING_OUTPUT_HEADERS = [
    header for header in TIMING_HEADERS if header != "case_id"
]

CONFORMANCE_OUTPUT_HEADERS = [
    header
    for header in CONFORMANCE_HEADERS
    if header not in {"case_id", "item_category", "event_count"}
]

DASHBOARD_CASE_HEADERS = [
    *CASE_HEADERS,
    *TIMING_OUTPUT_HEADERS,
    "conformance_in_scope",
    *CONFORMANCE_OUTPUT_HEADERS,
]

KPI_HEADERS = [
    "section",
    "metric_key",
    "metric_label",
    "value",
    "unit",
    "item_category",
    "source_artifact",
    "sort_order",
    "interpretation",
]


def validate_input_file(path: Path) -> None:
    """Reject a missing or non-file input path."""

    if not path.exists():
        raise FileNotFoundError(f"Required input does not exist: {path}")

    if not path.is_file():
        raise ValueError(f"Required input is not a file: {path}")


def resolved_path(path: Path) -> Path:
    """Return an absolute comparable path without requiring existence."""

    return path.expanduser().resolve(strict=False)


def validate_distinct_paths(
    input_paths: list[Path],
    output_paths: list[Path],
) -> None:
    """Prevent generated outputs from overwriting inputs or each other."""

    resolved_inputs = {resolved_path(path) for path in input_paths}
    resolved_outputs = [resolved_path(path) for path in output_paths]

    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ValueError("Dashboard output paths must be different.")

    for output_path in resolved_outputs:
        if output_path in resolved_inputs:
            raise ValueError(
                "A dashboard output must not overwrite an input: "
                f"{output_path}"
            )


def validate_csv_headers(
    reader: csv.DictReader,
    expected_headers: list[str],
    path: Path,
) -> None:
    """Require the exact upstream CSV data contract."""

    if reader.fieldnames != expected_headers:
        raise ValueError(
            f"Unexpected CSV headers in {path}. "
            f"Expected {expected_headers}, received {reader.fieldnames}."
        )


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON document and require an object at the root."""

    validate_input_file(path)

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error

    if not isinstance(content, dict):
        raise ValueError(f"JSON input must contain an object: {path}")

    return content


def require_mapping(value: Any, context: str) -> dict[str, Any]:
    """Require a mapping in a structured report."""

    if not isinstance(value, dict):
        raise ValueError(f"Expected an object for {context}.")

    return value


def require_list(value: Any, context: str) -> list[Any]:
    """Require a list in a structured report."""

    if not isinstance(value, list):
        raise ValueError(f"Expected a list for {context}.")

    return value


def require_string(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> str:
    """Read a required non-empty string."""

    value = mapping.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected a non-empty string at {context}.{key}.")

    return value


def require_number(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> int | float:
    """Read a required numeric value without accepting booleans."""

    value = mapping.get(key)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Expected a number at {context}.{key}.")

    return value


def require_non_negative_integer(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> int:
    """Read a required non-negative integer."""

    value = mapping.get(key)

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"Expected a non-negative integer at {context}.{key}."
        )

    return value


def load_conformance_rows(
    path: Path,
) -> dict[str, dict[str, str]]:
    """Load the selected-category conformance table for a case-level join."""

    validate_input_file(path)
    rows: dict[str, dict[str, str]] = {}

    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        validate_csv_headers(reader, CONFORMANCE_HEADERS, path)

        for row_number, row in enumerate(reader, start=2):
            case_id = row["case_id"]

            if not case_id:
                raise ValueError(
                    f"Missing case_id in {path} at row {row_number}."
                )

            if case_id in rows:
                raise ValueError(
                    f"Duplicate conformance case_id in {path}: {case_id}"
                )

            rows[case_id] = row

    return rows


def temporary_output_path(output_path: Path) -> Path:
    """Return a predictable sibling path for an incomplete generated file."""

    return output_path.with_name(f"{output_path.name}.tmp")


def build_dashboard_cases(
    cases_path: Path,
    timing_path: Path,
    conformance_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Stream a one-row-per-case dashboard table with strict reconciliation."""

    validate_input_file(cases_path)
    validate_input_file(timing_path)
    conformance_rows = load_conformance_rows(conformance_path)
    expected_conformance_count = len(conformance_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = temporary_output_path(output_path)

    case_count = 0
    conformance_join_count = 0
    eligible_case_count = 0
    excluded_case_count = 0
    category_counts: Counter[str] = Counter()

    try:
        with (
            cases_path.open(encoding="utf-8", newline="") as cases_file,
            timing_path.open(encoding="utf-8", newline="") as timing_file,
            temporary_path.open("w", encoding="utf-8", newline="") as output_file,
        ):
            cases_reader = csv.DictReader(cases_file)
            timing_reader = csv.DictReader(timing_file)
            validate_csv_headers(cases_reader, CASE_HEADERS, cases_path)
            validate_csv_headers(timing_reader, TIMING_HEADERS, timing_path)

            writer = csv.DictWriter(
                output_file,
                fieldnames=DASHBOARD_CASE_HEADERS,
            )
            writer.writeheader()

            for row_number, pair in enumerate(
                zip_longest(cases_reader, timing_reader),
                start=2,
            ):
                case_row, timing_row = pair

                if case_row is None or timing_row is None:
                    raise ValueError(
                        "Cases and timing files contain different row counts."
                    )

                case_id = case_row["case_id"]
                timing_case_id = timing_row["case_id"]

                if not case_id:
                    raise ValueError(
                        f"Missing case_id in {cases_path} at row {row_number}."
                    )

                if case_id != timing_case_id:
                    raise ValueError(
                        "Cases and timing rows are not aligned at row "
                        f"{row_number}: {case_id!r} != {timing_case_id!r}."
                    )

                conformance_row = conformance_rows.pop(case_id, None)

                if conformance_row is not None:
                    if conformance_row["item_category"] != case_row["item_category"]:
                        raise ValueError(
                            "Conformance category does not match the case table "
                            f"for case {case_id}."
                        )

                    if conformance_row["event_count"] != timing_row["event_count"]:
                        raise ValueError(
                            "Conformance event count does not match the timing "
                            f"table for case {case_id}."
                        )

                    conformance_join_count += 1

                output_row: dict[str, str] = {
                    **case_row,
                    **{
                        header: timing_row[header]
                        for header in TIMING_OUTPUT_HEADERS
                    },
                    "conformance_in_scope": (
                        "true" if conformance_row is not None else "false"
                    ),
                }

                for header in CONFORMANCE_OUTPUT_HEADERS:
                    output_row[header] = (
                        conformance_row[header]
                        if conformance_row is not None
                        else ""
                    )

                writer.writerow(output_row)
                case_count += 1
                category_counts[case_row["item_category"]] += 1

                if timing_row["duration_eligible"] == "true":
                    eligible_case_count += 1
                elif timing_row["duration_eligible"] == "false":
                    excluded_case_count += 1
                else:
                    raise ValueError(
                        "Unexpected duration_eligible value for case "
                        f"{case_id}: {timing_row['duration_eligible']!r}"
                    )

        if conformance_rows:
            example_case = next(iter(conformance_rows))
            raise ValueError(
                "Conformance data contains cases absent from the cases table. "
                f"Example: {example_case}"
            )

        if conformance_join_count != expected_conformance_count:
            raise ValueError(
                "Not every conformance row joined to the case dashboard."
            )

        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise

    return {
        "row_count": case_count,
        "conformance_join_count": conformance_join_count,
        "duration_eligible_cases": eligible_case_count,
        "duration_excluded_cases": excluded_case_count,
        "category_counts": dict(sorted(category_counts.items())),
    }


def add_kpi(
    rows: list[dict[str, Any]],
    seen_keys: set[str],
    *,
    section: str,
    metric_key: str,
    metric_label: str,
    value: int | float,
    unit: str,
    item_category: str,
    source_artifact: str,
    interpretation: str,
) -> None:
    """Append one unique long-form dashboard metric."""

    if metric_key in seen_keys:
        raise ValueError(f"Duplicate dashboard metric key: {metric_key}")

    seen_keys.add(metric_key)
    rows.append(
        {
            "section": section,
            "metric_key": metric_key,
            "metric_label": metric_label,
            "value": value,
            "unit": unit,
            "item_category": item_category,
            "source_artifact": source_artifact,
            "sort_order": len(rows) + 1,
            "interpretation": interpretation,
        }
    )


def build_kpi_rows(
    bottleneck_report: dict[str, Any],
    conformance_report: dict[str, Any],
    priority_report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create a compact metric table for cards and summary visuals."""

    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    bottleneck_scope = require_mapping(
        bottleneck_report.get("scope"),
        "bottleneck_report.scope",
    )
    category_baseline = require_list(
        bottleneck_report.get("category_cycle_time_baseline"),
        "bottleneck_report.category_cycle_time_baseline",
    )

    total_cases = 0
    eligible_cases = 0
    excluded_cases = 0

    for index, value in enumerate(category_baseline):
        category = require_mapping(
            value,
            f"category_cycle_time_baseline[{index}]",
        )
        total_cases += require_non_negative_integer(
            category,
            "total_cases",
            f"category_cycle_time_baseline[{index}]",
        )
        eligible_cases += require_non_negative_integer(
            category,
            "eligible_cases",
            f"category_cycle_time_baseline[{index}]",
        )
        excluded_cases += require_non_negative_integer(
            category,
            "excluded_cases",
            f"category_cycle_time_baseline[{index}]",
        )

    overall_metrics = [
        (
            "scope_total_cases",
            "Total cases",
            total_cases,
            "cases",
            "One case represents one purchasing-document item.",
        ),
        (
            "scope_total_events",
            "Total events",
            require_non_negative_integer(
                bottleneck_scope,
                "all_events_scanned",
                "bottleneck_report.scope",
            ),
            "events",
            "All retained events across the processed event log.",
        ),
        (
            "scope_duration_eligible_cases",
            "Duration-eligible cases",
            eligible_cases,
            "cases",
            "Cases included in cycle-time comparisons.",
        ),
        (
            "scope_duration_excluded_cases",
            "Duration-excluded cases",
            excluded_cases,
            "cases",
            "Cases retained but excluded from duration statistics.",
        ),
    ]

    for metric_key, label, value, unit, interpretation in overall_metrics:
        add_kpi(
            rows,
            seen_keys,
            section="Overall scope",
            metric_key=metric_key,
            metric_label=label,
            value=value,
            unit=unit,
            item_category="All categories",
            source_artifact="bottleneck_report.json",
            interpretation=interpretation,
        )

    category_metric_definitions = [
        ("total_cases", "Cases", "cases"),
        ("eligible_cases", "Duration-eligible cases", "cases"),
        ("median_days", "Median cycle time", "days"),
        ("p90_days", "P90 cycle time", "days"),
        ("average_events", "Average events per case", "events per case"),
    ]

    for index, value in enumerate(category_baseline):
        category = require_mapping(
            value,
            f"category_cycle_time_baseline[{index}]",
        )
        item_category = require_string(
            category,
            "item_category",
            f"category_cycle_time_baseline[{index}]",
        )
        category_key = (
            item_category.lower()
            .replace(" ", "_")
            .replace(",", "")
            .replace("-", "_")
        )

        for source_key, label, unit in category_metric_definitions:
            add_kpi(
                rows,
                seen_keys,
                section="Category performance",
                metric_key=f"category_{category_key}_{source_key}",
                metric_label=label,
                value=require_number(
                    category,
                    source_key,
                    f"category_cycle_time_baseline[{index}]",
                ),
                unit=unit,
                item_category=item_category,
                source_artifact="bottleneck_report.json",
                interpretation=(
                    "Cycle-time metrics use only duration-eligible cases."
                ),
            )

    conformance_scope = require_mapping(
        conformance_report.get("scope"),
        "conformance_report.scope",
    )
    conformance = require_mapping(
        conformance_report.get("conformance"),
        "conformance_report.conformance",
    )
    status_counts = require_mapping(
        conformance.get("status_counts"),
        "conformance_report.conformance.status_counts",
    )
    status_percentages = require_mapping(
        conformance.get("status_percentages"),
        "conformance_report.conformance.status_percentages",
    )
    selected_category = require_string(
        conformance_scope,
        "item_category",
        "conformance_report.scope",
    )

    status_labels = {
        "conforming": "Conforming cases",
        "review_required": "Review-required cases",
        "incomplete_evidence": "Incomplete-evidence cases",
    }

    for status, label in status_labels.items():
        add_kpi(
            rows,
            seen_keys,
            section="Conformance",
            metric_key=f"conformance_{status}_cases",
            metric_label=label,
            value=require_non_negative_integer(
                status_counts,
                status,
                "conformance_report.conformance.status_counts",
            ),
            unit="cases",
            item_category=selected_category,
            source_artifact="conformance_report.json",
            interpretation=(
                "Incomplete evidence is not automatically non-conforming; "
                "review-required cases need manual validation."
            ),
        )
        add_kpi(
            rows,
            seen_keys,
            section="Conformance",
            metric_key=f"conformance_{status}_percentage",
            metric_label=f"{label} percentage",
            value=require_number(
                status_percentages,
                status,
                "conformance_report.conformance.status_percentages",
            ),
            unit="percent",
            item_category=selected_category,
            source_artifact="conformance_report.json",
            interpretation=(
                "Percentage of selected-category cases under the transparent "
                "rule-based assessment."
            ),
        )

    priority_scope = require_mapping(
        priority_report.get("scope"),
        "priority_report.scope",
    )
    priority_category = require_string(
        priority_scope,
        "item_category",
        "priority_report.scope",
    )
    opportunities = require_list(
        priority_report.get("ranked_operational_opportunities"),
        "priority_report.ranked_operational_opportunities",
    )

    for index, value in enumerate(opportunities):
        opportunity = require_mapping(
            value,
            f"ranked_operational_opportunities[{index}]",
        )
        opportunity_id = require_string(
            opportunity,
            "opportunity_id",
            f"ranked_operational_opportunities[{index}]",
        )
        title = require_string(
            opportunity,
            "title",
            f"ranked_operational_opportunities[{index}]",
        )
        caution = require_string(
            opportunity,
            "decision_caution",
            f"ranked_operational_opportunities[{index}]",
        )

        priority_metrics = [
            (
                "score",
                f"{title}: priority score",
                require_number(
                    opportunity,
                    "overall_score",
                    f"ranked_operational_opportunities[{index}]",
                ),
                "score",
            ),
            (
                "reach",
                f"{title}: case reach",
                require_number(
                    opportunity,
                    "reach_percentage",
                    f"ranked_operational_opportunities[{index}]",
                ),
                "percent",
            ),
            (
                "delay",
                f"{title}: representative delay",
                require_number(
                    opportunity,
                    "representative_delay_days",
                    f"ranked_operational_opportunities[{index}]",
                ),
                "days",
            ),
        ]

        for suffix, label, metric_value, unit in priority_metrics:
            add_kpi(
                rows,
                seen_keys,
                section="Improvement priorities",
                metric_key=f"priority_{opportunity_id}_{suffix}",
                metric_label=label,
                value=metric_value,
                unit=unit,
                item_category=priority_category,
                source_artifact="improvement_priorities.json",
                interpretation=caution,
            )

    return rows


def write_csv_rows(
    output_path: Path,
    headers: list[str],
    rows: list[dict[str, Any]],
) -> None:
    """Write a complete CSV through a temporary sibling file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = temporary_output_path(output_path)

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def file_sha256(path: Path) -> str:
    """Calculate a file checksum without loading the whole file into memory."""

    digest = hashlib.sha256()

    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(
    output_path: Path,
    content: dict[str, Any],
) -> None:
    """Write a formatted JSON document through a temporary file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = temporary_output_path(output_path)

    try:
        temporary_path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise


def run_dashboard_build(
    cases_path: Path = DEFAULT_CASES,
    events_path: Path = DEFAULT_EVENTS,
    timing_path: Path = DEFAULT_TIMING,
    conformance_path: Path = DEFAULT_CONFORMANCE,
    bottleneck_report_path: Path = DEFAULT_BOTTLENECK_REPORT,
    conformance_report_path: Path = DEFAULT_CONFORMANCE_REPORT,
    priority_report_path: Path = DEFAULT_PRIORITY_REPORT,
    case_output_path: Path = DEFAULT_CASE_OUTPUT,
    kpi_output_path: Path = DEFAULT_KPI_OUTPUT,
    manifest_output_path: Path = DEFAULT_MANIFEST_OUTPUT,
) -> dict[str, Any]:
    """Build dashboard tables, reconcile them, and write a manifest."""

    input_paths = [
        cases_path,
        events_path,
        timing_path,
        conformance_path,
        bottleneck_report_path,
        conformance_report_path,
        priority_report_path,
    ]
    output_paths = [
        case_output_path,
        kpi_output_path,
        manifest_output_path,
    ]
    validate_distinct_paths(input_paths, output_paths)

    for input_path in input_paths:
        validate_input_file(input_path)

    with events_path.open(encoding="utf-8", newline="") as events_file:
        events_reader = csv.DictReader(events_file)
        validate_csv_headers(events_reader, EVENT_HEADERS, events_path)

    bottleneck_report = read_json_object(bottleneck_report_path)
    conformance_report = read_json_object(conformance_report_path)
    priority_report = read_json_object(priority_report_path)

    bottleneck_scope = require_mapping(
        bottleneck_report.get("scope"),
        "bottleneck_report.scope",
    )
    conformance_scope = require_mapping(
        conformance_report.get("scope"),
        "conformance_report.scope",
    )
    priority_scope = require_mapping(
        priority_report.get("scope"),
        "priority_report.scope",
    )
    categories = {
        require_string(
            bottleneck_scope,
            "selected_category",
            "bottleneck_report.scope",
        ),
        require_string(
            conformance_scope,
            "item_category",
            "conformance_report.scope",
        ),
        require_string(
            priority_scope,
            "item_category",
            "priority_report.scope",
        ),
    }

    if len(categories) != 1:
        raise ValueError(
            "Bottleneck, conformance, and priority report categories must match."
        )

    selected_category = next(iter(categories))
    case_summary = build_dashboard_cases(
        cases_path,
        timing_path,
        conformance_path,
        case_output_path,
    )
    kpi_rows = build_kpi_rows(
        bottleneck_report,
        conformance_report,
        priority_report,
    )
    write_csv_rows(kpi_output_path, KPI_HEADERS, kpi_rows)

    expected_total_cases = sum(
        require_non_negative_integer(
            require_mapping(
                value,
                f"category_cycle_time_baseline[{index}]",
            ),
            "total_cases",
            f"category_cycle_time_baseline[{index}]",
        )
        for index, value in enumerate(
            require_list(
                bottleneck_report.get("category_cycle_time_baseline"),
                "bottleneck_report.category_cycle_time_baseline",
            )
        )
    )
    expected_conformance_cases = require_non_negative_integer(
        conformance_scope,
        "selected_case_count",
        "conformance_report.scope",
    )

    if case_summary["row_count"] != expected_total_cases:
        raise ValueError(
            "Dashboard case count does not match the category baseline: "
            f"{case_summary['row_count']} != {expected_total_cases}"
        )

    if case_summary["conformance_join_count"] != expected_conformance_cases:
        raise ValueError(
            "Dashboard conformance count does not match the report: "
            f"{case_summary['conformance_join_count']} != "
            f"{expected_conformance_cases}"
        )

    expected_events = require_non_negative_integer(
        bottleneck_scope,
        "all_events_scanned",
        "bottleneck_report.scope",
    )
    generated_at_utc = datetime.now(timezone.utc).isoformat()

    manifest: dict[str, Any] = {
        "generated_at_utc": generated_at_utc,
        "scope": {
            "total_cases": case_summary["row_count"],
            "total_events": expected_events,
            "duration_eligible_cases": case_summary[
                "duration_eligible_cases"
            ],
            "duration_excluded_cases": case_summary[
                "duration_excluded_cases"
            ],
            "conformance_selected_category": selected_category,
            "conformance_cases": case_summary["conformance_join_count"],
            "category_counts": case_summary["category_counts"],
        },
        "generated_outputs": {
            "dashboard_cases": {
                "path": str(case_output_path),
                "row_count": case_summary["row_count"],
                "column_count": len(DASHBOARD_CASE_HEADERS),
                "columns": DASHBOARD_CASE_HEADERS,
                "size_bytes": case_output_path.stat().st_size,
                "sha256": file_sha256(case_output_path),
            },
            "dashboard_kpis": {
                "path": str(kpi_output_path),
                "row_count": len(kpi_rows),
                "column_count": len(KPI_HEADERS),
                "columns": KPI_HEADERS,
                "size_bytes": kpi_output_path.stat().st_size,
                "sha256": file_sha256(kpi_output_path),
            },
        },
        "existing_dashboard_tables": {
            "events": {
                "path": str(events_path),
                "row_count": expected_events,
                "columns": EVENT_HEADERS,
                "role": "Event-level fact table",
            },
            "transition_bottlenecks": {
                "path": "data/processed/transition_bottlenecks.csv",
                "role": "Aggregated transition waiting-time evidence",
            },
            "marker_duration_comparison": {
                "path": "data/processed/marker_duration_comparison.csv",
                "role": "Case-marker duration associations",
            },
            "improvement_priorities": {
                "path": "data/processed/improvement_priorities.csv",
                "role": "Ranked decision-support opportunities",
            },
        },
        "recommended_relationships": [
            {
                "from": "events.case_id",
                "to": "dashboard_cases.case_id",
                "cardinality": "many-to-one",
                "filter_direction": "dashboard_cases to events",
            }
        ],
        "data_model_notes": [
            (
                "dashboard_cases contains one row per purchasing-document item "
                "and should be the case-level dimension/fact table."
            ),
            (
                "events remains separate to avoid duplicating the 1.6-million-row "
                "event dataset."
            ),
            (
                "Conformance columns are populated only for the selected "
                "invoice-after-GR category; use conformance_in_scope when filtering."
            ),
            (
                "Cycle-time visuals should filter duration_eligible to true."
            ),
            (
                "Priority scores are transparent decision-support scores, not "
                "financial returns or causal estimates."
            ),
        ],
        "source_artifacts": [str(path) for path in input_paths],
    }

    write_json(manifest_output_path, manifest)
    return manifest


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Build dashboard-ready ProcessIQ case and KPI tables with a "
            "reproducibility manifest."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--timing", type=Path, default=DEFAULT_TIMING)
    parser.add_argument(
        "--conformance",
        type=Path,
        default=DEFAULT_CONFORMANCE,
    )
    parser.add_argument(
        "--bottleneck-report",
        type=Path,
        default=DEFAULT_BOTTLENECK_REPORT,
    )
    parser.add_argument(
        "--conformance-report",
        type=Path,
        default=DEFAULT_CONFORMANCE_REPORT,
    )
    parser.add_argument(
        "--priority-report",
        type=Path,
        default=DEFAULT_PRIORITY_REPORT,
    )
    parser.add_argument(
        "--case-output",
        type=Path,
        default=DEFAULT_CASE_OUTPUT,
    )
    parser.add_argument(
        "--kpi-output",
        type=Path,
        default=DEFAULT_KPI_OUTPUT,
    )
    parser.add_argument(
        "--manifest-output",
        type=Path,
        default=DEFAULT_MANIFEST_OUTPUT,
    )
    return parser


def main() -> None:
    """Run the dashboard data build from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()
    manifest = run_dashboard_build(
        cases_path=arguments.cases,
        events_path=arguments.events,
        timing_path=arguments.timing,
        conformance_path=arguments.conformance,
        bottleneck_report_path=arguments.bottleneck_report,
        conformance_report_path=arguments.conformance_report,
        priority_report_path=arguments.priority_report,
        case_output_path=arguments.case_output,
        kpi_output_path=arguments.kpi_output,
        manifest_output_path=arguments.manifest_output,
    )

    scope = require_mapping(manifest.get("scope"), "manifest.scope")
    outputs = require_mapping(
        manifest.get("generated_outputs"),
        "manifest.generated_outputs",
    )

    print("Dashboard data build completed.")
    print(f"Cases: {scope['total_cases']:,}")
    print(f"Events referenced: {scope['total_events']:,}")
    print(f"Conformance cases joined: {scope['conformance_cases']:,}")
    print(
        "Dashboard case table: "
        f"{outputs['dashboard_cases']['path']}"
    )
    print(
        "Dashboard KPI table: "
        f"{outputs['dashboard_kpis']['path']}"
    )
    print(f"Manifest: {arguments.manifest_output}")


if __name__ == "__main__":
    main()
