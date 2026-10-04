"""Tests for dashboard-ready ProcessIQ data generation."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from processiq.build_dashboard_data import (
    CASE_HEADERS,
    CONFORMANCE_HEADERS,
    DASHBOARD_CASE_HEADERS,
    EVENT_HEADERS,
    KPI_HEADERS,
    TIMING_HEADERS,
    file_sha256,
    run_dashboard_build,
)


class TestBuildDashboardData(unittest.TestCase):
    """Verify dashboard joins, metrics, safeguards, and manifest evidence."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base_path = Path(self.temporary_directory.name)

        self.cases_path = self.base_path / "cases.csv"
        self.events_path = self.base_path / "events.csv"
        self.timing_path = self.base_path / "case_timing.csv"
        self.conformance_path = self.base_path / "case_conformance.csv"
        self.bottleneck_report_path = self.base_path / "bottleneck_report.json"
        self.conformance_report_path = self.base_path / "conformance_report.json"
        self.priority_report_path = self.base_path / "priority_report.json"
        self.case_output_path = self.base_path / "dashboard_cases.csv"
        self.kpi_output_path = self.base_path / "dashboard_kpis.csv"
        self.manifest_output_path = self.base_path / "dashboard_manifest.json"

        self.cases = [
            self.make_case(
                "case-1",
                "3-way match, invoice after GR",
                "vendor-1",
            ),
            self.make_case(
                "case-2",
                "Consignment",
                "vendor-2",
            ),
        ]
        self.events = [
            self.make_event("case-1", "1", "Create Purchase Order Item"),
            self.make_event("case-1", "2", "Clear Invoice"),
            self.make_event("case-2", "1", "Record Goods Receipt"),
        ]
        self.timing = [
            self.make_timing("case-1", "2", "1.0", "true"),
            self.make_timing("case-2", "1", "0.0", "true"),
        ]
        self.conformance = [
            self.make_conformance(
                "case-1",
                "3-way match, invoice after GR",
                "2",
            )
        ]

        self.bottleneck_report = {
            "generated_at_utc": "2026-10-04T22:39:40+00:00",
            "scope": {
                "selected_category": "3-way match, invoice after GR",
                "all_events_scanned": 3,
            },
            "category_cycle_time_baseline": [
                {
                    "average_days": 1.0,
                    "average_events": 2.0,
                    "eligible_cases": 1,
                    "excluded_cases": 0,
                    "item_category": "3-way match, invoice after GR",
                    "median_days": 1.0,
                    "p75_days": 1.0,
                    "p90_days": 1.0,
                    "p95_days": 1.0,
                    "total_cases": 1,
                },
                {
                    "average_days": 0.0,
                    "average_events": 1.0,
                    "eligible_cases": 1,
                    "excluded_cases": 0,
                    "item_category": "Consignment",
                    "median_days": 0.0,
                    "p75_days": 0.0,
                    "p90_days": 0.0,
                    "p95_days": 0.0,
                    "total_cases": 1,
                },
            ],
        }
        self.conformance_report = {
            "generated_at_utc": "2026-10-04T21:39:11+00:00",
            "scope": {
                "item_category": "3-way match, invoice after GR",
                "selected_case_count": 1,
            },
            "conformance": {
                "status_counts": {
                    "conforming": 1,
                    "review_required": 0,
                    "incomplete_evidence": 0,
                },
                "status_percentages": {
                    "conforming": 100.0,
                    "review_required": 0.0,
                    "incomplete_evidence": 0.0,
                },
            },
        }
        self.priority_report = {
            "generated_at_utc": "2026-10-04T23:00:00+00:00",
            "scope": {
                "item_category": "3-way match, invoice after GR",
            },
            "ranked_operational_opportunities": [
                {
                    "opportunity_id": "payment_block_intervention",
                    "title": "Investigate payment blocks",
                    "decision_caution": "Association does not prove causation.",
                    "overall_score": 78.0,
                    "reach_percentage": 15.0,
                    "representative_delay_days": 36.0,
                }
            ],
        }

        self.write_valid_inputs()

    @staticmethod
    def make_case(
        case_id: str,
        item_category: str,
        vendor_id: str,
    ) -> dict[str, str]:
        return {
            "case_id": case_id,
            "purchasing_document_id": f"po-{case_id}",
            "item_id": "00001",
            "item_type": "Standard",
            "gr_based_invoice_verification": "true",
            "goods_receipt_required": "true",
            "source_system_id": "source-1",
            "purchasing_document_category": "Purchase order",
            "company_id": "company-1",
            "spend_classification": "NPR",
            "spend_area": "Operations",
            "sub_spend_area": "Services",
            "vendor_id": vendor_id,
            "vendor_name": vendor_id,
            "document_type": "Purchase order",
            "item_category": item_category,
            "spend_data_complete": "true",
        }

    @staticmethod
    def make_event(
        case_id: str,
        position: str,
        activity: str,
    ) -> dict[str, str]:
        return {
            "case_id": case_id,
            "event_position": position,
            "activity": activity,
            "event_timestamp": "2018-01-01T00:00:00+00:00",
            "resource_id": "resource-1",
            "user_id": "resource-1",
            "cumulative_net_worth": "100.0",
            "resource_recorded": "true",
            "timestamp_in_analysis_window": "true",
        }

    @staticmethod
    def make_timing(
        case_id: str,
        event_count: str,
        cycle_time_days: str,
        duration_eligible: str,
    ) -> dict[str, str]:
        return {
            "case_id": case_id,
            "first_event_timestamp": "2018-01-01T00:00:00+00:00",
            "last_event_timestamp": "2018-01-02T00:00:00+00:00",
            "cycle_time_seconds": "86400",
            "cycle_time_days": cycle_time_days,
            "event_count": event_count,
            "outside_analysis_window_event_count": "0",
            "has_negative_timestamp": "false",
            "exceeds_365_days": "false",
            "duration_eligible": duration_eligible,
            "duration_exclusion_reason": "",
        }

    @staticmethod
    def make_conformance(
        case_id: str,
        item_category: str,
        event_count: str,
    ) -> dict[str, str]:
        row = {header: "" for header in CONFORMANCE_HEADERS}
        row.update(
            {
                "case_id": case_id,
                "item_category": item_category,
                "conformance_status": "conforming",
                "goods_receipt_before_invoice_receipt_rule": "pass",
                "invoice_receipt_before_clearing_rule": "pass",
                "event_count": event_count,
                "goods_receipt_count": "1",
                "invoice_receipt_count": "1",
                "clearing_count": "1",
                "service_entry_count": "0",
                "multiple_goods_receipts": "false",
                "multiple_invoice_receipts": "false",
                "multiple_service_entries": "false",
                "payment_block_intervention": "false",
                "cancellation_activity": "false",
                "deletion_or_reactivation": "false",
                "change_activity": "false",
                "vendor_invoice_before_goods_receipt": "false",
            }
        )
        return row

    @staticmethod
    def write_csv(
        path: Path,
        headers: list[str],
        rows: list[dict[str, str]],
    ) -> None:
        with path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def write_json(path: Path, content: dict[str, object]) -> None:
        path.write_text(
            json.dumps(content, indent=2) + "\n",
            encoding="utf-8",
        )

    def write_valid_inputs(self) -> None:
        self.write_csv(self.cases_path, CASE_HEADERS, self.cases)
        self.write_csv(self.events_path, EVENT_HEADERS, self.events)
        self.write_csv(self.timing_path, TIMING_HEADERS, self.timing)
        self.write_csv(
            self.conformance_path,
            CONFORMANCE_HEADERS,
            self.conformance,
        )
        self.write_json(
            self.bottleneck_report_path,
            self.bottleneck_report,
        )
        self.write_json(
            self.conformance_report_path,
            self.conformance_report,
        )
        self.write_json(
            self.priority_report_path,
            self.priority_report,
        )

    def run_build(self) -> dict[str, object]:
        return run_dashboard_build(
            cases_path=self.cases_path,
            events_path=self.events_path,
            timing_path=self.timing_path,
            conformance_path=self.conformance_path,
            bottleneck_report_path=self.bottleneck_report_path,
            conformance_report_path=self.conformance_report_path,
            priority_report_path=self.priority_report_path,
            case_output_path=self.case_output_path,
            kpi_output_path=self.kpi_output_path,
            manifest_output_path=self.manifest_output_path,
        )

    def read_csv(self, path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as input_file:
            return list(csv.DictReader(input_file))

    def test_case_dashboard_joins_available_conformance(self) -> None:
        """Every case should remain, with scoped conformance joined once."""

        manifest = self.run_build()
        rows = self.read_csv(self.case_output_path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(list(rows[0]), DASHBOARD_CASE_HEADERS)
        self.assertEqual(rows[0]["case_id"], "case-1")
        self.assertEqual(rows[0]["conformance_in_scope"], "true")
        self.assertEqual(rows[0]["conformance_status"], "conforming")
        self.assertEqual(rows[1]["case_id"], "case-2")
        self.assertEqual(rows[1]["conformance_in_scope"], "false")
        self.assertEqual(rows[1]["conformance_status"], "")
        self.assertEqual(manifest["scope"]["conformance_cases"], 1)

    def test_kpis_include_scope_category_conformance_and_priority(self) -> None:
        """The long-form table should support executive dashboard visuals."""

        self.run_build()
        rows = self.read_csv(self.kpi_output_path)
        values = {
            row["metric_key"]: row["value"]
            for row in rows
        }

        self.assertEqual(list(rows[0]), KPI_HEADERS)
        self.assertEqual(values["scope_total_cases"], "2")
        self.assertEqual(values["scope_total_events"], "3")
        self.assertEqual(values["conformance_conforming_cases"], "1")
        self.assertEqual(
            values["priority_payment_block_intervention_score"],
            "78.0",
        )
        self.assertEqual(
            values["priority_payment_block_intervention_delay"],
            "36.0",
        )

    def test_manifest_records_counts_relationship_and_checksums(self) -> None:
        """The manifest should make generated dashboard data auditable."""

        returned_manifest = self.run_build()
        written_manifest = json.loads(
            self.manifest_output_path.read_text(encoding="utf-8")
        )

        self.assertEqual(written_manifest, returned_manifest)
        self.assertEqual(returned_manifest["scope"]["total_cases"], 2)
        self.assertEqual(returned_manifest["scope"]["total_events"], 3)
        self.assertEqual(
            returned_manifest["recommended_relationships"][0]["cardinality"],
            "many-to-one",
        )
        self.assertEqual(
            returned_manifest["generated_outputs"]["dashboard_cases"]["sha256"],
            file_sha256(self.case_output_path),
        )
        self.assertEqual(
            returned_manifest["generated_outputs"]["dashboard_kpis"]["sha256"],
            file_sha256(self.kpi_output_path),
        )

    def test_misaligned_case_and_timing_rows_are_rejected(self) -> None:
        """A position-based join must stop if upstream rows are reordered."""

        self.write_csv(
            self.timing_path,
            TIMING_HEADERS,
            list(reversed(self.timing)),
        )

        with self.assertRaisesRegex(ValueError, "not aligned"):
            self.run_build()

        self.assertFalse(self.case_output_path.exists())
        self.assertFalse(
            self.case_output_path.with_name(
                f"{self.case_output_path.name}.tmp"
            ).exists()
        )

    def test_conformance_event_count_must_match_timing(self) -> None:
        """Joined case evidence should reconcile to the timing table."""

        changed_rows = deepcopy(self.conformance)
        changed_rows[0]["event_count"] = "99"
        self.write_csv(
            self.conformance_path,
            CONFORMANCE_HEADERS,
            changed_rows,
        )

        with self.assertRaisesRegex(ValueError, "event count does not match"):
            self.run_build()

    def test_report_categories_must_match(self) -> None:
        """Dashboard evidence must come from the same selected category."""

        changed_report = deepcopy(self.priority_report)
        changed_report["scope"]["item_category"] = "2-way match"
        self.write_json(self.priority_report_path, changed_report)

        with self.assertRaisesRegex(ValueError, "categories must match"):
            self.run_build()

    def test_output_must_not_overwrite_an_input(self) -> None:
        """Dashboard generation must preserve every upstream artifact."""

        with self.assertRaisesRegex(
            ValueError,
            "must not overwrite an input",
        ):
            run_dashboard_build(
                cases_path=self.cases_path,
                events_path=self.events_path,
                timing_path=self.timing_path,
                conformance_path=self.conformance_path,
                bottleneck_report_path=self.bottleneck_report_path,
                conformance_report_path=self.conformance_report_path,
                priority_report_path=self.priority_report_path,
                case_output_path=self.cases_path,
                kpi_output_path=self.kpi_output_path,
                manifest_output_path=self.manifest_output_path,
            )

    def test_event_schema_is_validated_without_copying_events(self) -> None:
        """The existing event fact should be checked but not duplicated."""

        wrong_headers = EVENT_HEADERS[:-1]
        reduced_events = [
            {
                header: row[header]
                for header in wrong_headers
            }
            for row in self.events
        ]
        self.write_csv(
            self.events_path,
            wrong_headers,
            reduced_events,
        )

        with self.assertRaisesRegex(ValueError, "Unexpected CSV headers"):
            self.run_build()

    def test_duplicate_conformance_cases_are_rejected(self) -> None:
        """A case-level join cannot safely accept duplicate case records."""

        duplicate_rows = [
            self.conformance[0],
            deepcopy(self.conformance[0]),
        ]
        self.write_csv(
            self.conformance_path,
            CONFORMANCE_HEADERS,
            duplicate_rows,
        )

        with self.assertRaisesRegex(ValueError, "Duplicate conformance case_id"):
            self.run_build()


if __name__ == "__main__":
    unittest.main()
