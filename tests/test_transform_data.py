"""Tests for the ProcessIQ transformation pipeline."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from processiq.extract_xes import CASE_HEADERS, EVENT_HEADERS
from processiq.transform_data import (
    CASE_TIMING_HEADERS,
    PROCESSED_CASE_HEADERS,
    PROCESSED_EVENT_HEADERS,
    transform_data,
)


class TestTransformData(unittest.TestCase):
    """Verify cleaning, preservation, and eligibility rules."""

    def setUp(self) -> None:
        """Create small raw tables and transform them."""

        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.directory = Path(self.temporary_directory.name)

        self.cases_input = self.directory / "cases_raw.csv"
        self.events_input = self.directory / "events_raw.csv"
        self.cases_output = self.directory / "cases.csv"
        self.events_output = self.directory / "events.csv"
        self.timing_output = self.directory / "case_timing.csv"

        self.case_rows = [
            self.make_case_row(case_id="case-1"),
            self.make_case_row(
                case_id="case-2",
                spend_classification="UNKNOWN",
                spend_area="",
                sub_spend_area="NONE",
                gr_based_invoice_verification="TRUE",
                goods_receipt_required="FALSE",
            ),
            self.make_case_row(case_id="case-3"),
        ]

        self.event_rows = [
            self.make_event_row(
                case_id="case-1",
                event_position="1",
                activity="Create Purchase Order",
                event_timestamp="2018-01-01T10:00:00.000Z",
                resource_id="user-1",
                user_id="user-1",
                amount="100.00",
            ),
            self.make_event_row(
                case_id="case-1",
                event_position="2",
                activity="Clear Invoice",
                event_timestamp="2018-01-01T11:00:00.000Z",
                resource_id="user-2",
                user_id="user-2",
                amount="100.00",
            ),
            self.make_event_row(
                case_id="case-2",
                event_position="1",
                activity="Vendor creates invoice",
                event_timestamp="2017-12-31T23:00:00.000Z",
                resource_id="NONE",
                user_id="NONE",
                amount="200.00",
            ),
            self.make_event_row(
                case_id="case-2",
                event_position="2",
                activity="Clear Invoice",
                event_timestamp="2018-01-01T01:00:00.000Z",
                resource_id="batch-1",
                user_id="batch-1",
                amount="200.00",
            ),
            self.make_event_row(
                case_id="case-3",
                event_position="1",
                activity="Create Purchase Order",
                event_timestamp="2018-01-01T00:00:00.000Z",
                resource_id="user-3",
                user_id="user-3",
                amount="300.00",
            ),
            self.make_event_row(
                case_id="case-3",
                event_position="2",
                activity="Clear Invoice",
                event_timestamp="2019-02-02T00:00:00.000Z",
                resource_id="user-4",
                user_id="user-4",
                amount="300.00",
            ),
        ]

        self.write_csv(
            path=self.cases_input,
            headers=CASE_HEADERS,
            rows=self.case_rows,
        )
        self.write_csv(
            path=self.events_input,
            headers=EVENT_HEADERS,
            rows=self.event_rows,
        )

        self.original_cases = self.cases_input.read_bytes()
        self.original_events = self.events_input.read_bytes()

        self.result = transform_data(
            cases_input=self.cases_input,
            events_input=self.events_input,
            cases_output=self.cases_output,
            events_output=self.events_output,
            timing_output=self.timing_output,
            progress_every=0,
        )

        self.case_headers, self.processed_cases = self.read_csv(
            self.cases_output
        )
        self.event_headers, self.processed_events = self.read_csv(
            self.events_output
        )
        self.timing_headers, self.timing_rows = self.read_csv(
            self.timing_output
        )

    @staticmethod
    def make_case_row(
        case_id: str,
        **changes: str,
    ) -> dict[str, str]:
        """Create one complete raw case row."""

        row = {header: "" for header in CASE_HEADERS}
        row.update(
            {
                "case_id": case_id,
                "purchasing_document_id": f"po-{case_id}",
                "item_id": "00001",
                "item_type": "Standard",
                "gr_based_invoice_verification": "false",
                "goods_receipt_required": "true",
                "source_system_id": "system-1",
                "purchasing_document_category": "Purchase order",
                "company_id": "company-1",
                "spend_classification": "NPR",
                "spend_area": "Operations",
                "sub_spend_area": "Services",
                "vendor_id": "vendor-1",
                "vendor_name": "Vendor One",
                "document_type": "Standard PO",
                "item_category": "2-way match",
            }
        )
        row.update(changes)
        return row

    @staticmethod
    def make_event_row(
        case_id: str,
        event_position: str,
        activity: str,
        event_timestamp: str,
        resource_id: str,
        user_id: str,
        amount: str,
    ) -> dict[str, str]:
        """Create one complete raw event row."""

        return {
            "case_id": case_id,
            "event_position": event_position,
            "activity": activity,
            "event_timestamp": event_timestamp,
            "resource_id": resource_id,
            "user_id": user_id,
            "cumulative_net_worth": amount,
        }

    @staticmethod
    def write_csv(
        path: Path,
        headers: list[str],
        rows: list[dict[str, str]],
    ) -> None:
        """Write rows with the requested schema."""

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
            writer.writerows(rows)

    @staticmethod
    def read_csv(
        path: Path,
    ) -> tuple[list[str], list[dict[str, str]]]:
        """Read CSV headers and rows."""

        with path.open(
            mode="r",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)
            headers = list(reader.fieldnames or [])
            rows = list(reader)

        return headers, rows

    def test_output_counts_and_schemas(self) -> None:
        """Transformation should preserve all row counts."""

        self.assertEqual(
            self.result,
            {
                "case_count": 3,
                "event_count": 6,
                "timing_count": 3,
                "duration_eligible_cases": 1,
                "duration_ineligible_cases": 2,
            },
        )

        self.assertEqual(
            self.case_headers,
            PROCESSED_CASE_HEADERS,
        )
        self.assertEqual(
            self.event_headers,
            PROCESSED_EVENT_HEADERS,
        )
        self.assertEqual(
            self.timing_headers,
            CASE_TIMING_HEADERS,
        )

        self.assertEqual(len(self.processed_cases), 3)
        self.assertEqual(len(self.processed_events), 6)
        self.assertEqual(len(self.timing_rows), 3)

    def test_missing_values_are_normalised(self) -> None:
        """Missing markers should become empty output values."""

        case_two = self.processed_cases[1]

        self.assertEqual(
            case_two["spend_classification"],
            "",
        )
        self.assertEqual(case_two["spend_area"], "")
        self.assertEqual(case_two["sub_spend_area"], "")
        self.assertEqual(
            case_two["spend_data_complete"],
            "false",
        )
        self.assertEqual(
            case_two["gr_based_invoice_verification"],
            "true",
        )
        self.assertEqual(
            case_two["goods_receipt_required"],
            "false",
        )

    def test_event_quality_flags_are_created(self) -> None:
        """Events should retain data-quality evidence."""

        outside_event = self.processed_events[2]

        self.assertEqual(
            outside_event["event_timestamp"],
            "2017-12-31T23:00:00+00:00",
        )
        self.assertEqual(
            outside_event["resource_id"],
            "",
        )
        self.assertEqual(outside_event["user_id"], "")
        self.assertEqual(
            outside_event["resource_recorded"],
            "false",
        )
        self.assertEqual(
            outside_event[
                "timestamp_in_analysis_window"
            ],
            "false",
        )

        normal_event = self.processed_events[0]

        self.assertEqual(
            normal_event["resource_recorded"],
            "true",
        )
        self.assertEqual(
            normal_event[
                "timestamp_in_analysis_window"
            ],
            "true",
        )

    def test_eligible_case_timing(self) -> None:
        """A normal case should remain eligible."""

        timing_by_case = {
            row["case_id"]: row
            for row in self.timing_rows
        }
        case_one = timing_by_case["case-1"]

        self.assertEqual(
            case_one["cycle_time_seconds"],
            "3600",
        )
        self.assertEqual(
            case_one["cycle_time_days"],
            "0.041667",
        )
        self.assertEqual(
            case_one["event_count"],
            "2",
        )
        self.assertEqual(
            case_one["duration_eligible"],
            "true",
        )
        self.assertEqual(
            case_one["duration_exclusion_reason"],
            "",
        )

    def test_outside_window_case_is_ineligible(
        self,
    ) -> None:
        """An outside-window event should retain its reason."""

        timing_by_case = {
            row["case_id"]: row
            for row in self.timing_rows
        }
        case_two = timing_by_case["case-2"]

        self.assertEqual(
            case_two[
                "outside_analysis_window_event_count"
            ],
            "1",
        )
        self.assertEqual(
            case_two["duration_eligible"],
            "false",
        )
        self.assertEqual(
            case_two["duration_exclusion_reason"],
            "timestamp_outside_2018_2019",
        )

    def test_long_case_is_ineligible(self) -> None:
        """A case over 365 days should retain its reason."""

        timing_by_case = {
            row["case_id"]: row
            for row in self.timing_rows
        }
        case_three = timing_by_case["case-3"]

        self.assertEqual(
            case_three["cycle_time_days"],
            "397",
        )
        self.assertEqual(
            case_three["exceeds_365_days"],
            "true",
        )
        self.assertEqual(
            case_three["duration_eligible"],
            "false",
        )
        self.assertEqual(
            case_three["duration_exclusion_reason"],
            "cycle_time_over_365_days",
        )

    def test_source_files_are_not_modified(self) -> None:
        """Transformation must leave raw inputs unchanged."""

        self.assertEqual(
            self.cases_input.read_bytes(),
            self.original_cases,
        )
        self.assertEqual(
            self.events_input.read_bytes(),
            self.original_events,
        )

        self.assertEqual(
            list(self.directory.glob("*.tmp")),
            [],
        )

    def test_invalid_arguments_are_rejected(self) -> None:
        """Unsafe paths and progress values should fail."""

        missing_input = self.directory / "missing.csv"

        with self.assertRaises(FileNotFoundError):
            transform_data(
                cases_input=missing_input,
                events_input=self.events_input,
                cases_output=self.cases_output,
                events_output=self.events_output,
                timing_output=self.timing_output,
                progress_every=0,
            )

        with self.assertRaises(ValueError):
            transform_data(
                cases_input=self.cases_input,
                events_input=self.events_input,
                cases_output=self.cases_input,
                events_output=self.events_output,
                timing_output=self.timing_output,
                progress_every=0,
            )

        with self.assertRaises(ValueError):
            transform_data(
                cases_input=self.cases_input,
                events_input=self.events_input,
                cases_output=self.cases_output,
                events_output=self.events_output,
                timing_output=self.timing_output,
                progress_every=-1,
            )


if __name__ == "__main__":
    unittest.main()
