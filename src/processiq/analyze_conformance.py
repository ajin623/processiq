"""Evaluate transparent, case-level conformance rules for ProcessIQ.

The module deliberately separates three ideas:

* conforming: the complete core sequence is present in the expected order;
* review_required: recorded events contradict that order or contain clearing
  without invoice-receipt evidence;
* incomplete_evidence: the trace does not contain enough events to decide.

Repeated activities and exception activities are retained as diagnostic markers.
They are not automatically treated as conformance failures.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_CATEGORY = "3-way match, invoice after GR"
DEFAULT_CASES_INPUT = Path("data/processed/cases.csv")
DEFAULT_EVENTS_INPUT = Path("data/processed/events.csv")
DEFAULT_CASE_OUTPUT = Path("data/processed/case_conformance.csv")
DEFAULT_REPORT_OUTPUT = Path("data/interim/conformance_report.json")

REQUIRED_CASE_HEADERS = {"case_id", "item_category"}
REQUIRED_EVENT_HEADERS = {
    "case_id",
    "event_position",
    "activity",
}

CASE_OUTPUT_HEADERS = [
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

PASS = "pass"
REVIEW = "review"
NOT_ASSESSABLE = "not_assessable"

CONFORMING = "conforming"
REVIEW_REQUIRED = "review_required"
INCOMPLETE_EVIDENCE = "incomplete_evidence"


def _minimum_position(current: int | None, candidate: int) -> int:
    if current is None:
        return candidate
    return min(current, candidate)


def _boolean_text(value: bool) -> str:
    return "true" if value else "false"


def _optional_position(value: int | None) -> str:
    return "" if value is None else str(value)


@dataclass
class CaseEvidence:
    """Evidence collected from the ordered events of one selected case."""

    event_count: int = 0
    first_purchase_order_position: int | None = None
    first_goods_receipt_position: int | None = None
    first_invoice_receipt_position: int | None = None
    first_clearing_position: int | None = None
    first_vendor_invoice_position: int | None = None
    goods_receipt_count: int = 0
    invoice_receipt_count: int = 0
    clearing_count: int = 0
    service_entry_count: int = 0
    payment_block_intervention: bool = False
    cancellation_activity: bool = False
    deletion_or_reactivation: bool = False
    change_activity: bool = False

    def record(self, event_position: int, activity: str) -> None:
        """Add one event without changing its source meaning."""

        self.event_count += 1

        if activity == "Create Purchase Order Item":
            self.first_purchase_order_position = _minimum_position(
                self.first_purchase_order_position,
                event_position,
            )

        if activity == "Record Goods Receipt":
            self.goods_receipt_count += 1
            self.first_goods_receipt_position = _minimum_position(
                self.first_goods_receipt_position,
                event_position,
            )

        if activity == "Record Invoice Receipt":
            self.invoice_receipt_count += 1
            self.first_invoice_receipt_position = _minimum_position(
                self.first_invoice_receipt_position,
                event_position,
            )

        if activity == "Clear Invoice":
            self.clearing_count += 1
            self.first_clearing_position = _minimum_position(
                self.first_clearing_position,
                event_position,
            )

        if activity == "Vendor creates invoice":
            self.first_vendor_invoice_position = _minimum_position(
                self.first_vendor_invoice_position,
                event_position,
            )

        if activity == "Record Service Entry Sheet":
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

    def goods_receipt_rule(self) -> str:
        """Evaluate whether receipt precedes formal invoice receipt."""

        invoice_position = self.first_invoice_receipt_position
        goods_position = self.first_goods_receipt_position

        if invoice_position is None:
            return NOT_ASSESSABLE

        if goods_position is None:
            return REVIEW

        if goods_position < invoice_position:
            return PASS

        return REVIEW

    def clearing_rule(self) -> str:
        """Evaluate whether formal invoice receipt precedes clearing."""

        clear_position = self.first_clearing_position
        invoice_position = self.first_invoice_receipt_position

        if clear_position is None:
            return NOT_ASSESSABLE

        if invoice_position is None:
            return REVIEW

        if invoice_position < clear_position:
            return PASS

        return REVIEW

    def review_reasons(self) -> list[str]:
        """Return transparent evidence labels for manual review."""

        reasons: list[str] = []
        goods_position = self.first_goods_receipt_position
        invoice_position = self.first_invoice_receipt_position
        clear_position = self.first_clearing_position

        if invoice_position is not None and goods_position is None:
            reasons.append("invoice_receipt_without_goods_receipt")
        elif (
            invoice_position is not None
            and goods_position is not None
            and invoice_position <= goods_position
        ):
            reasons.append("invoice_receipt_before_goods_receipt")

        if clear_position is not None and invoice_position is None:
            reasons.append("clearing_without_invoice_receipt")
        elif (
            clear_position is not None
            and invoice_position is not None
            and clear_position <= invoice_position
        ):
            reasons.append("clearing_before_invoice_receipt")

        return reasons

    def conformance_status(self) -> str:
        """Combine the two formal rules into one case-level status."""

        goods_rule = self.goods_receipt_rule()
        clearing_rule = self.clearing_rule()

        if REVIEW in {goods_rule, clearing_rule}:
            return REVIEW_REQUIRED

        if goods_rule == PASS and clearing_rule == PASS:
            return CONFORMING

        return INCOMPLETE_EVIDENCE

    def vendor_invoice_observation(self) -> str:
        """Describe vendor-invoice timing without calling it a violation."""

        vendor_position = self.first_vendor_invoice_position
        goods_position = self.first_goods_receipt_position

        if vendor_position is None or goods_position is None:
            return NOT_ASSESSABLE

        return _boolean_text(vendor_position < goods_position)

    def as_output_row(self, case_id: str, category: str) -> dict[str, object]:
        """Create one stable CSV row for downstream analysis."""

        return {
            "case_id": case_id,
            "item_category": category,
            "conformance_status": self.conformance_status(),
            "goods_receipt_before_invoice_receipt_rule": (
                self.goods_receipt_rule()
            ),
            "invoice_receipt_before_clearing_rule": self.clearing_rule(),
            "review_reason": ";".join(self.review_reasons()),
            "event_count": self.event_count,
            "first_purchase_order_position": _optional_position(
                self.first_purchase_order_position
            ),
            "first_goods_receipt_position": _optional_position(
                self.first_goods_receipt_position
            ),
            "first_invoice_receipt_position": _optional_position(
                self.first_invoice_receipt_position
            ),
            "first_clearing_position": _optional_position(
                self.first_clearing_position
            ),
            "goods_receipt_count": self.goods_receipt_count,
            "invoice_receipt_count": self.invoice_receipt_count,
            "clearing_count": self.clearing_count,
            "service_entry_count": self.service_entry_count,
            "multiple_goods_receipts": _boolean_text(
                self.goods_receipt_count > 1
            ),
            "multiple_invoice_receipts": _boolean_text(
                self.invoice_receipt_count > 1
            ),
            "multiple_service_entries": _boolean_text(
                self.service_entry_count > 1
            ),
            "payment_block_intervention": _boolean_text(
                self.payment_block_intervention
            ),
            "cancellation_activity": _boolean_text(
                self.cancellation_activity
            ),
            "deletion_or_reactivation": _boolean_text(
                self.deletion_or_reactivation
            ),
            "change_activity": _boolean_text(self.change_activity),
            "vendor_invoice_before_goods_receipt": (
                self.vendor_invoice_observation()
            ),
        }


def validate_input_file(path: Path) -> None:
    """Reject a missing or non-file input with a useful message."""

    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")


def validate_required_headers(
    reader: csv.DictReader,
    required_headers: set[str],
    path: Path,
) -> None:
    """Check only the columns this analysis actually depends on."""

    actual_headers = set(reader.fieldnames or [])
    missing_headers = sorted(required_headers - actual_headers)

    if missing_headers:
        missing_text = ", ".join(missing_headers)
        raise ValueError(
            f"Missing required column(s) in {path}: {missing_text}"
        )


def validate_distinct_paths(paths: Iterable[Path]) -> None:
    """Prevent an output from overwriting an input or another output."""

    resolved_paths = [path.expanduser().resolve() for path in paths]

    if len(resolved_paths) != len(set(resolved_paths)):
        raise ValueError("Input and output paths must all be different.")


def read_selected_cases(cases_path: Path, category: str) -> list[str]:
    """Read the case identifiers belonging to the requested category."""

    selected_case_ids: list[str] = []
    seen_case_ids: set[str] = set()

    with cases_path.open(encoding="utf-8", newline="") as cases_file:
        reader = csv.DictReader(cases_file)
        validate_required_headers(reader, REQUIRED_CASE_HEADERS, cases_path)

        for line_number, row in enumerate(reader, start=2):
            case_id = (row.get("case_id") or "").strip()

            if not case_id:
                raise ValueError(
                    f"Missing case_id in {cases_path} at line {line_number}."
                )

            if row.get("item_category") != category:
                continue

            if case_id in seen_case_ids:
                raise ValueError(
                    f"Duplicate selected case_id in {cases_path}: {case_id}"
                )

            selected_case_ids.append(case_id)
            seen_case_ids.add(case_id)

    if not selected_case_ids:
        raise ValueError(f"No cases found for category: {category}")

    return selected_case_ids


def collect_case_evidence(
    events_path: Path,
    selected_case_ids: list[str],
    progress_every: int,
) -> tuple[dict[str, CaseEvidence], int]:
    """Scan the event table once and retain only selected-case evidence."""

    evidence = {
        case_id: CaseEvidence()
        for case_id in selected_case_ids
    }
    selected_case_set = set(selected_case_ids)
    events_scanned = 0

    with events_path.open(encoding="utf-8", newline="") as events_file:
        reader = csv.DictReader(events_file)
        validate_required_headers(reader, REQUIRED_EVENT_HEADERS, events_path)

        for line_number, row in enumerate(reader, start=2):
            events_scanned += 1

            if progress_every and events_scanned % progress_every == 0:
                print(f"Scanned {events_scanned:,} events...")

            case_id = (row.get("case_id") or "").strip()
            if case_id not in selected_case_set:
                continue

            position_text = (row.get("event_position") or "").strip()
            activity = (row.get("activity") or "").strip()

            try:
                event_position = int(position_text)
            except ValueError as error:
                raise ValueError(
                    "Invalid event_position in "
                    f"{events_path} at line {line_number}: "
                    f"{position_text!r}"
                ) from error

            if event_position <= 0:
                raise ValueError(
                    "event_position must be positive in "
                    f"{events_path} at line {line_number}."
                )

            if not activity:
                raise ValueError(
                    f"Missing activity in {events_path} at line {line_number}."
                )

            evidence[case_id].record(event_position, activity)

    return evidence, events_scanned


def build_report(
    category: str,
    selected_case_ids: list[str],
    evidence: dict[str, CaseEvidence],
    events_scanned: int,
) -> dict[str, object]:
    """Summarise rule results without overstating diagnostic markers."""

    status_counts: Counter[str] = Counter()
    goods_rule_counts: Counter[str] = Counter()
    clearing_rule_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    selected_event_count = 0

    completeness = Counter()
    markers = Counter()
    vendor_observation = Counter()

    for case_id in selected_case_ids:
        case_evidence = evidence[case_id]
        selected_event_count += case_evidence.event_count
        status_counts[case_evidence.conformance_status()] += 1
        goods_rule_counts[case_evidence.goods_receipt_rule()] += 1
        clearing_rule_counts[case_evidence.clearing_rule()] += 1

        for reason in case_evidence.review_reasons():
            reason_counts[reason] += 1

        completeness["missing_purchase_order_creation"] += int(
            case_evidence.first_purchase_order_position is None
        )
        completeness["missing_goods_receipt"] += int(
            case_evidence.first_goods_receipt_position is None
        )
        completeness["missing_invoice_receipt"] += int(
            case_evidence.first_invoice_receipt_position is None
        )
        completeness["missing_invoice_clearing"] += int(
            case_evidence.first_clearing_position is None
        )
        completeness["cases_without_events"] += int(
            case_evidence.event_count == 0
        )

        markers["multiple_goods_receipts"] += int(
            case_evidence.goods_receipt_count > 1
        )
        markers["multiple_invoice_receipts"] += int(
            case_evidence.invoice_receipt_count > 1
        )
        markers["multiple_service_entries"] += int(
            case_evidence.service_entry_count > 1
        )
        markers["payment_block_intervention"] += int(
            case_evidence.payment_block_intervention
        )
        markers["cancellation_activity"] += int(
            case_evidence.cancellation_activity
        )
        markers["deletion_or_reactivation"] += int(
            case_evidence.deletion_or_reactivation
        )
        markers["change_activity"] += int(case_evidence.change_activity)

        vendor_observation[
            case_evidence.vendor_invoice_observation()
        ] += 1

    selected_case_count = len(selected_case_ids)
    ordered_status_counts = {
        status: status_counts[status]
        for status in (
            CONFORMING,
            REVIEW_REQUIRED,
            INCOMPLETE_EVIDENCE,
        )
    }
    status_percentages = {
        status: round(100 * count / selected_case_count, 2)
        for status, count in ordered_status_counts.items()
    }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "item_category": category,
            "selected_case_count": selected_case_count,
            "selected_event_count": selected_event_count,
            "all_events_scanned": events_scanned,
        },
        "conformance": {
            "status_counts": ordered_status_counts,
            "status_percentages": status_percentages,
            "review_reason_counts": dict(sorted(reason_counts.items())),
        },
        "rules": {
            "goods_receipt_before_invoice_receipt": {
                "description": (
                    "For this category, the first goods receipt should "
                    "precede the first formal invoice receipt."
                ),
                "status_counts": {
                    status: goods_rule_counts[status]
                    for status in (PASS, REVIEW, NOT_ASSESSABLE)
                },
            },
            "invoice_receipt_before_clearing": {
                "description": (
                    "The first formal invoice receipt should precede the "
                    "first clearing event."
                ),
                "status_counts": {
                    status: clearing_rule_counts[status]
                    for status in (PASS, REVIEW, NOT_ASSESSABLE)
                },
            },
        },
        "completeness": dict(sorted(completeness.items())),
        "diagnostic_markers": dict(sorted(markers.items())),
        "business_observations": {
            "vendor_invoice_before_goods_receipt": {
                "true": vendor_observation["true"],
                "false": vendor_observation["false"],
                NOT_ASSESSABLE: vendor_observation[NOT_ASSESSABLE],
                "interpretation": (
                    "Vendor invoice creation is distinct from formal invoice "
                    "receipt and is not treated as a conformance failure."
                ),
            }
        },
        "interpretation": {
            CONFORMING: (
                "Both core ordering rules passed with complete evidence."
            ),
            REVIEW_REQUIRED: (
                "Recorded ordering is contradictory or clearing exists "
                "without formal invoice-receipt evidence. Manual review is "
                "required; this is not proof of a control breach."
            ),
            INCOMPLETE_EVIDENCE: (
                "The trace lacks enough core events for a complete decision. "
                "It is not automatically non-conforming."
            ),
            "diagnostic_markers": (
                "Repeats, cancellations, changes, and payment-block events "
                "are investigation signals, not automatic violations."
            ),
        },
    }


def _temporary_path(output_path: Path) -> Path:
    return output_path.with_name(f".{output_path.name}.tmp")


def write_outputs(
    case_output: Path,
    report_output: Path,
    category: str,
    selected_case_ids: list[str],
    evidence: dict[str, CaseEvidence],
    report: dict[str, object],
) -> None:
    """Write both outputs through temporary files before replacing targets."""

    case_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.parent.mkdir(parents=True, exist_ok=True)

    case_temporary = _temporary_path(case_output)
    report_temporary = _temporary_path(report_output)

    try:
        with case_temporary.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as case_file:
            writer = csv.DictWriter(
                case_file,
                fieldnames=CASE_OUTPUT_HEADERS,
            )
            writer.writeheader()

            for case_id in selected_case_ids:
                writer.writerow(
                    evidence[case_id].as_output_row(case_id, category)
                )

        with report_temporary.open(
            mode="w",
            encoding="utf-8",
        ) as report_file:
            json.dump(report, report_file, indent=2, sort_keys=True)
            report_file.write("\n")

        os.replace(case_temporary, case_output)
        os.replace(report_temporary, report_output)
    finally:
        case_temporary.unlink(missing_ok=True)
        report_temporary.unlink(missing_ok=True)


def analyze_conformance(
    cases_path: Path,
    events_path: Path,
    case_output: Path,
    report_output: Path,
    category: str = DEFAULT_CATEGORY,
    progress_every: int = 0,
) -> dict[str, object]:
    """Run category-specific rule evaluation and write auditable outputs."""

    if progress_every < 0:
        raise ValueError("progress_every must be zero or greater.")

    if not category.strip():
        raise ValueError("category must not be empty.")

    validate_input_file(cases_path)
    validate_input_file(events_path)
    validate_distinct_paths(
        [
            cases_path,
            events_path,
            case_output,
            report_output,
        ]
    )

    selected_case_ids = read_selected_cases(cases_path, category)
    evidence, events_scanned = collect_case_evidence(
        events_path,
        selected_case_ids,
        progress_every,
    )
    report = build_report(
        category,
        selected_case_ids,
        evidence,
        events_scanned,
    )
    write_outputs(
        case_output,
        report_output,
        category,
        selected_case_ids,
        evidence,
        report,
    )
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate transparent conformance rules for a ProcessIQ category."
        )
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_INPUT,
        help="Path to the processed cases CSV.",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS_INPUT,
        help="Path to the processed events CSV.",
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Item category to evaluate.",
    )
    parser.add_argument(
        "--case-output",
        type=Path,
        default=DEFAULT_CASE_OUTPUT,
        help="Path for the case-level conformance CSV.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
        help="Path for the conformance summary JSON.",
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
    """Run the command-line workflow."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    try:
        report = analyze_conformance(
            cases_path=arguments.cases,
            events_path=arguments.events,
            case_output=arguments.case_output,
            report_output=arguments.report_output,
            category=arguments.category,
            progress_every=arguments.progress_every,
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        parser.error(str(error))

    scope = report["scope"]
    status_counts = report["conformance"]["status_counts"]

    print("Conformance analysis completed.")
    print(f"Category: {scope['item_category']}")
    print(f"Cases evaluated: {scope['selected_case_count']:,}")
    print(f"Selected events: {scope['selected_event_count']:,}")
    print(f"Conforming cases: {status_counts[CONFORMING]:,}")
    print(f"Review-required cases: {status_counts[REVIEW_REQUIRED]:,}")
    print(
        "Incomplete-evidence cases: "
        f"{status_counts[INCOMPLETE_EVIDENCE]:,}"
    )
    print(f"Case output: {arguments.case_output}")
    print(f"Report output: {arguments.report_output}")


if __name__ == "__main__":
    main()
