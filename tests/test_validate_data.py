"""Tests for the extracted-data validation rules."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from processiq.extract_xes import (
    CASE_HEADERS,
    EVENT_HEADERS,
)
from processiq.validate_data import (
    validate_extracted_data,
)


class TestValidateExtractedData(unittest.TestCase):
    """Verify the ProcessIQ data-quality checks."""

    def setUp(self) -> None:
        """Create valid temporary case and event tables."""

        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.output_directory = Path(
            self.temporary_directory.name
        )
        self.cases_path = (
            self.output_directory / "cases_raw.csv"
        )
        self.events_path = (
            self.output_directory / "events_raw.csv"
        )
        self.report_path = (
            self.output_directory
            / "data_quality_report.json"
        )

        self.case_rows = [
            self.make_case_row(
                case_id="case-1",
                purchasing_document_id="po-1",
                item_id="00001",
                item_category="2-way match",
            ),
            self.make_case_row(
                case_id="case-2",
                purchasing_document_id="po-2",
                item_id="00001",
                item_category=(
                    "3-way match, invoice before GR"
                ),
            ),
        ]

        self.event_rows = [
            self.make_event_row(
                case_id="case-1",
                event_position="1",
                activity="Create Purchase Order",
                event_timestamp=(
                    "2018-01-01T10:00:00+00:00"
                ),
                resource_id="user-1",
                cumulative_net_worth="100.00",
            ),
            self.make_event_row(
                case_id="case-1",
                event_position="2",
                activity="Clear Invoice",
                event_timestamp=(
                    "2018-01-01T11:00:00+00:00"
                ),
                resource_id="user-2",
                cumulative_net_worth="100.00",
            ),
            self.make_event_row(
                case_id="case-2",
                event_position="1",
                activity="Create Purchase Order",
                event_timestamp=(
                    "2018-01-02T09:30:00+00:00"
                ),
                resource_id="batch-1",
                cumulative_net_worth="250.00",
            ),
        ]

        self.write_csv(
            path=self.cases_path,
            headers=CASE_HEADERS,
            rows=self.case_rows,
        )
        self.write_csv(
            path=self.events_path,
            headers=EVENT_HEADERS,
            rows=self.event_rows,
        )

    @staticmethod
    def make_case_row(
        case_id: str,
        purchasing_document_id: str,
        item_id: str,
        item_category: str,
    ) -> dict[str, str]:
        """Create one complete test case row."""

        row = {
            header: ""
            for header in CASE_HEADERS
        }

        row.update(
            {
                "case_id": case_id,
                "purchasing_document_id": (
                    purchasing_document_id
                ),
                "item_id": item_id,
                "item_type": "Standard",
                "gr_based_invoice_verification": "false",
                "goods_receipt_required": "true",
                "source_system_id": "system-1",
                "purchasing_document_category": (
                    "Purchase order"
                ),
                "company_id": "company-1",
                "spend_classification": "NPR",
                "spend_area": "Operations",
                "sub_spend_area": "Services",
                "vendor_id": "vendor-1",
                "vendor_name": "Vendor One",
                "document_type": "Purchase order",
                "item_category": item_category,
            }
        )

        return row

    @staticmethod
    def make_event_row(
        case_id: str,
        event_position: str,
        activity: str,
        event_timestamp: str,
        resource_id: str,
        cumulative_net_worth: str,
    ) -> dict[str, str]:
        """Create one complete test event row."""

        row = {
            header: ""
            for header in EVENT_HEADERS
        }

        row.update(
            {
                "case_id": case_id,
                "event_position": event_position,
                "activity": activity,
                "event_timestamp": event_timestamp,
                "resource_id": resource_id,
                "user_id": resource_id,
                "cumulative_net_worth": (
                    cumulative_net_worth
                ),
            }
        )

        return row

    @staticmethod
    def write_csv(
        path: Path,
        headers: list[str],
        rows: list[dict[str, str]],
    ) -> None:
        """Write test rows using a defined CSV schema."""

        with path.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=headers,
            )
            writer.writeheader()

            for row in rows:
                writer.writerow(
                    {
                        header: row.get(header, "")
                        for header in headers
                    }
                )

    def run_validation(self) -> dict[str, object]:
        """Run validation with the expected test counts."""

        return validate_extracted_data(
            cases_path=self.cases_path,
            events_path=self.events_path,
            output_path=self.report_path,
            expected_case_count=2,
            expected_event_count=3,
            progress_every=0,
        )

    def rewrite_cases(self) -> None:
        """Save the current in-memory case rows."""

        self.write_csv(
            path=self.cases_path,
            headers=CASE_HEADERS,
            rows=self.case_rows,
        )

    def rewrite_events(self) -> None:
        """Save the current in-memory event rows."""

        self.write_csv(
            path=self.events_path,
            headers=EVENT_HEADERS,
            rows=self.event_rows,
        )

    def test_valid_tables_pass_core_checks(self) -> None:
        """Valid tables should pass structural checks."""

        report = self.run_validation()

        self.assertTrue(
            report["status"][
                "structural_integrity_passed"
            ]
        )
        self.assertTrue(
            report["status"][
                "count_reconciliation_passed"
            ]
        )
        self.assertFalse(
            report["status"][
                "timestamp_scope_review_required"
            ]
        )
        self.assertTrue(
            report["status"]["duration_metrics_ready"]
        )

        self.assertEqual(
            report["case_summary"]["row_count"],
            2,
        )
        self.assertEqual(
            report["event_summary"]["row_count"],
            3,
        )

        self.assertTrue(self.report_path.is_file())

        saved_report = json.loads(
            self.report_path.read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(saved_report, report)

    def test_missing_resource_is_reported(self) -> None:
        """A missing marker should count as a missing resource."""

        self.event_rows[1]["resource_id"] = "NONE"
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["event_summary"][
                "missing_resource_events"
            ],
            1,
        )
        self.assertEqual(
            report["event_summary"][
                "missing_resource_by_activity"
            ]["Clear Invoice"],
            1,
        )

    def test_duplicate_case_id_fails_structure(
        self,
    ) -> None:
        """A duplicate case identifier should be detected."""

        duplicate_row = dict(self.case_rows[0])
        self.case_rows.append(duplicate_row)
        self.rewrite_cases()

        report = self.run_validation()

        self.assertEqual(
            report["case_summary"][
                "duplicate_case_id_rows"
            ],
            1,
        )
        self.assertFalse(
            report["status"][
                "structural_integrity_passed"
            ]
        )

    def test_orphan_event_is_detected(self) -> None:
        """An event referencing an unknown case is invalid."""

        self.event_rows[2]["case_id"] = "case-3"
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["relationship_checks"][
                "orphan_event_rows"
            ],
            1,
        )
        self.assertEqual(
            report["relationship_checks"][
                "cases_without_events"
            ],
            1,
        )
        self.assertFalse(
            report["status"][
                "structural_integrity_passed"
            ]
        )

    def test_broken_event_position_is_detected(
        self,
    ) -> None:
        """Event positions must be consecutive per case."""

        self.event_rows[1]["event_position"] = "3"
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["relationship_checks"][
                "nonsequential_event_position_rows"
            ],
            1,
        )
        self.assertFalse(
            report["status"][
                "structural_integrity_passed"
            ]
        )

    def test_negative_timestamp_is_detected(
        self,
    ) -> None:
        """A later event must not silently move backward."""

        self.event_rows[1]["event_timestamp"] = (
            "2018-01-01T09:00:00+00:00"
        )
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["timestamp_checks"][
                "negative_timestamp_transitions"
            ],
            1,
        )
        self.assertFalse(
            report["status"]["duration_metrics_ready"]
        )
        self.assertTrue(
            report["status"][
                "structural_integrity_passed"
            ]
        )

    def test_equal_timestamps_are_allowed(self) -> None:
        """Equal event times are valid but should be counted."""

        self.event_rows[1]["event_timestamp"] = (
            self.event_rows[0]["event_timestamp"]
        )
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["timestamp_checks"][
                "same_timestamp_transitions"
            ],
            1,
        )
        self.assertTrue(
            report["status"]["duration_metrics_ready"]
        )

    def test_outside_window_timestamp_requires_review(
        self,
    ) -> None:
        """A timestamp outside 2018-2019 needs review."""

        self.event_rows[0]["event_timestamp"] = (
            "2017-12-31T10:00:00+00:00"
        )
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["timestamp_checks"][
                "outside_analysis_window_events"
            ],
            1,
        )
        self.assertEqual(
            report["timestamp_checks"][
                "outside_analysis_window_cases"
            ],
            1,
        )
        self.assertEqual(
            report["timestamp_checks"][
                "outside_analysis_window_by_year"
            ]["2017"],
            1,
        )
        self.assertTrue(
            report["status"][
                "timestamp_scope_review_required"
            ]
        )
        self.assertFalse(
            report["status"]["duration_metrics_ready"]
        )
        self.assertTrue(
            report["status"][
                "structural_integrity_passed"
            ]
        )

    def test_long_case_requires_duration_review(
        self,
    ) -> None:
        """A case longer than one year needs review."""

        self.event_rows[1]["event_timestamp"] = (
            "2019-02-02T11:00:00+00:00"
        )
        self.rewrite_events()

        report = self.run_validation()

        timestamp_checks = report["timestamp_checks"]

        self.assertEqual(
            timestamp_checks["outside_analysis_window_events"],
            0,
        )
        self.assertEqual(
            timestamp_checks["cases_over_365_days"],
            1,
        )
        self.assertEqual(
            timestamp_checks["cases_over_730_days"],
            0,
        )
        self.assertEqual(
            timestamp_checks["case_year_range_counts"][
                "2018->2019"
            ],
            1,
        )
        self.assertEqual(
            timestamp_checks["longest_case_span"][
                "case_id"
            ],
            "case-1",
        )
        self.assertTrue(
            report["status"][
                "timestamp_scope_review_required"
            ]
        )
        self.assertFalse(
            report["status"]["duration_metrics_ready"]
        )

    def test_invalid_business_values_are_reported(
        self,
    ) -> None:
        """Unexpected categories and invalid types need flags."""

        self.case_rows[0]["item_category"] = (
            "Unexpected category"
        )
        self.case_rows[0][
            "goods_receipt_required"
        ] = "maybe"
        self.event_rows[0][
            "cumulative_net_worth"
        ] = "not-a-number"

        self.rewrite_cases()
        self.rewrite_events()

        report = self.run_validation()

        self.assertEqual(
            report["case_summary"][
                "unexpected_item_categories"
            ]["Unexpected category"],
            1,
        )
        self.assertEqual(
            report["case_summary"][
                "invalid_boolean_counts"
            ]["goods_receipt_required"],
            1,
        )
        self.assertEqual(
            report["event_summary"][
                "invalid_amount_events"
            ],
            1,
        )

    def test_wrong_headers_are_rejected(self) -> None:
        """A changed CSV schema should stop validation."""

        wrong_headers = CASE_HEADERS[:-1]

        self.write_csv(
            path=self.cases_path,
            headers=wrong_headers,
            rows=self.case_rows,
        )

        with self.assertRaises(ValueError):
            self.run_validation()

    def test_missing_input_is_rejected(self) -> None:
        """A missing CSV file should produce a clear error."""

        missing_path = (
            self.output_directory / "missing.csv"
        )

        with self.assertRaises(FileNotFoundError):
            validate_extracted_data(
                cases_path=missing_path,
                events_path=self.events_path,
                progress_every=0,
            )

    def test_negative_progress_interval_is_rejected(
        self,
    ) -> None:
        """A negative progress interval is invalid."""

        with self.assertRaises(ValueError):
            validate_extracted_data(
                cases_path=self.cases_path,
                events_path=self.events_path,
                progress_every=-1,
            )


if __name__ == "__main__":
    unittest.main()
