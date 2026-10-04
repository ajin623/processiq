"""Tests for transparent, case-level conformance analysis."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from processiq.analyze_conformance import analyze_conformance


SELECTED_CATEGORY = "3-way match, invoice after GR"
OTHER_CATEGORY = "2-way match"


class TestAnalyzeConformance(unittest.TestCase):
    """Check rule outcomes without treating diagnostic markers as failures."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.directory = Path(self.temporary_directory.name)
        self.cases_path = self.directory / "cases.csv"
        self.events_path = self.directory / "events.csv"
        self.case_output = self.directory / "case_conformance.csv"
        self.report_output = self.directory / "conformance_report.json"

        self._write_cases(
            [
                ("conforming", SELECTED_CATEGORY),
                ("early-clear", SELECTED_CATEGORY),
                ("clear-without-ir", SELECTED_CATEGORY),
                ("incomplete", SELECTED_CATEGORY),
                ("invoice-before-gr", SELECTED_CATEGORY),
                ("diagnostic-markers", SELECTED_CATEGORY),
                ("no-events", SELECTED_CATEGORY),
                ("other-category", OTHER_CATEGORY),
            ]
        )

        self._write_events(
            {
                "conforming": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
                "early-clear": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Clear Invoice",
                    "Record Invoice Receipt",
                ],
                "clear-without-ir": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Clear Invoice",
                ],
                "incomplete": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                ],
                "invoice-before-gr": [
                    "Create Purchase Order Item",
                    "Record Invoice Receipt",
                    "Record Goods Receipt",
                    "Clear Invoice",
                ],
                "diagnostic-markers": [
                    "Create Purchase Order Item",
                    "Vendor creates invoice",
                    "Record Goods Receipt",
                    "Record Goods Receipt",
                    "Record Service Entry Sheet",
                    "Record Service Entry Sheet",
                    "Record Invoice Receipt",
                    "Record Invoice Receipt",
                    "Set Payment Block",
                    "Remove Payment Block",
                    "Cancel Goods Receipt",
                    "Delete Purchase Order Item",
                    "Change Quantity",
                    "Clear Invoice",
                ],
                "other-category": [
                    "Create Purchase Order Item",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            }
        )

    def _write_cases(self, rows: list[tuple[str, str]]) -> None:
        with self.cases_path.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as cases_file:
            writer = csv.DictWriter(
                cases_file,
                fieldnames=["case_id", "item_category"],
            )
            writer.writeheader()
            for case_id, category in rows:
                writer.writerow(
                    {
                        "case_id": case_id,
                        "item_category": category,
                    }
                )

    def _write_events(
        self,
        case_activities: dict[str, list[str]],
    ) -> None:
        with self.events_path.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as events_file:
            writer = csv.DictWriter(
                events_file,
                fieldnames=[
                    "case_id",
                    "event_position",
                    "activity",
                ],
            )
            writer.writeheader()

            for case_id, activities in case_activities.items():
                for position, activity in enumerate(activities, start=1):
                    writer.writerow(
                        {
                            "case_id": case_id,
                            "event_position": position,
                            "activity": activity,
                        }
                    )

    def _run_analysis(self) -> dict[str, object]:
        return analyze_conformance(
            cases_path=self.cases_path,
            events_path=self.events_path,
            case_output=self.case_output,
            report_output=self.report_output,
            category=SELECTED_CATEGORY,
            progress_every=0,
        )

    def _read_output_rows(self) -> dict[str, dict[str, str]]:
        with self.case_output.open(
            encoding="utf-8",
            newline="",
        ) as case_file:
            return {
                row["case_id"]: row
                for row in csv.DictReader(case_file)
            }

    def test_case_statuses_follow_available_evidence(self) -> None:
        """Complete, contradictory, and incomplete traces must stay distinct."""

        self._run_analysis()
        rows = self._read_output_rows()

        self.assertEqual(rows["conforming"]["conformance_status"], "conforming")
        self.assertEqual(
            rows["early-clear"]["conformance_status"],
            "review_required",
        )
        self.assertEqual(
            rows["clear-without-ir"]["conformance_status"],
            "review_required",
        )
        self.assertEqual(
            rows["invoice-before-gr"]["conformance_status"],
            "review_required",
        )
        self.assertEqual(
            rows["incomplete"]["conformance_status"],
            "incomplete_evidence",
        )
        self.assertEqual(
            rows["no-events"]["conformance_status"],
            "incomplete_evidence",
        )

    def test_review_reasons_preserve_the_observed_problem(self) -> None:
        """Review cases should explain which recorded relationship triggered them."""

        self._run_analysis()
        rows = self._read_output_rows()

        self.assertEqual(
            rows["early-clear"]["review_reason"],
            "clearing_before_invoice_receipt",
        )
        self.assertEqual(
            rows["clear-without-ir"]["review_reason"],
            "clearing_without_invoice_receipt",
        )
        self.assertEqual(
            rows["invoice-before-gr"]["review_reason"],
            "invoice_receipt_before_goods_receipt",
        )
        self.assertEqual(rows["incomplete"]["review_reason"], "")

    def test_incomplete_trace_is_not_labelled_as_a_violation(self) -> None:
        """A missing clearing event should produce incomplete evidence."""

        self._run_analysis()
        row = self._read_output_rows()["incomplete"]

        self.assertEqual(
            row["goods_receipt_before_invoice_receipt_rule"],
            "pass",
        )
        self.assertEqual(
            row["invoice_receipt_before_clearing_rule"],
            "not_assessable",
        )
        self.assertEqual(row["conformance_status"], "incomplete_evidence")

    def test_diagnostic_markers_do_not_force_nonconformance(self) -> None:
        """Repeats and exception activities should remain investigation signals."""

        self._run_analysis()
        row = self._read_output_rows()["diagnostic-markers"]

        self.assertEqual(row["conformance_status"], "conforming")
        self.assertEqual(row["multiple_goods_receipts"], "true")
        self.assertEqual(row["multiple_invoice_receipts"], "true")
        self.assertEqual(row["multiple_service_entries"], "true")
        self.assertEqual(row["payment_block_intervention"], "true")
        self.assertEqual(row["cancellation_activity"], "true")
        self.assertEqual(row["deletion_or_reactivation"], "true")
        self.assertEqual(row["change_activity"], "true")

    def test_vendor_invoice_timing_is_only_an_observation(self) -> None:
        """Vendor creation timing must not be confused with formal receipt."""

        self._run_analysis()
        row = self._read_output_rows()["diagnostic-markers"]

        self.assertEqual(
            row["vendor_invoice_before_goods_receipt"],
            "true",
        )
        self.assertEqual(row["conformance_status"], "conforming")

    def test_report_and_case_output_reconcile(self) -> None:
        """Every selected case should appear once in both output totals."""

        returned_report = self._run_analysis()
        rows = self._read_output_rows()
        written_report = json.loads(
            self.report_output.read_text(encoding="utf-8")
        )

        self.assertEqual(len(rows), 7)
        self.assertEqual(returned_report["scope"]["selected_case_count"], 7)
        self.assertEqual(written_report["scope"]["selected_case_count"], 7)
        self.assertEqual(
            written_report["conformance"]["status_counts"],
            {
                "conforming": 2,
                "review_required": 3,
                "incomplete_evidence": 2,
            },
        )
        self.assertEqual(
            sum(
                written_report["conformance"]["status_counts"].values()
            ),
            written_report["scope"]["selected_case_count"],
        )
        self.assertEqual(
            written_report["completeness"]["cases_without_events"],
            1,
        )

    def test_unknown_category_is_rejected(self) -> None:
        """A misspelled or absent category should fail clearly."""

        with self.assertRaisesRegex(ValueError, "No cases found"):
            analyze_conformance(
                cases_path=self.cases_path,
                events_path=self.events_path,
                case_output=self.case_output,
                report_output=self.report_output,
                category="Not a real category",
                progress_every=0,
            )

    def test_negative_progress_interval_is_rejected(self) -> None:
        """Progress configuration cannot be negative."""

        with self.assertRaisesRegex(ValueError, "zero or greater"):
            analyze_conformance(
                cases_path=self.cases_path,
                events_path=self.events_path,
                case_output=self.case_output,
                report_output=self.report_output,
                category=SELECTED_CATEGORY,
                progress_every=-1,
            )

    def test_duplicate_paths_are_rejected(self) -> None:
        """An output must never overwrite a source table."""

        with self.assertRaisesRegex(ValueError, "must all be different"):
            analyze_conformance(
                cases_path=self.cases_path,
                events_path=self.events_path,
                case_output=self.cases_path,
                report_output=self.report_output,
                category=SELECTED_CATEGORY,
                progress_every=0,
            )


if __name__ == "__main__":
    unittest.main()
