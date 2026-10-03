"""Tests for the streaming XES extraction pipeline."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from processiq.extract_xes import (
    CASE_HEADERS,
    EVENT_HEADERS,
    extract_xes,
)


class TestExtractXes(unittest.TestCase):
    """Verify that XES traces and events are extracted correctly."""

    def setUp(self) -> None:
        """Create isolated output files for each test."""

        self.fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "minimal_event_log.xes"
        )

        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.output_directory = Path(
            self.temporary_directory.name
        )
        self.cases_output = (
            self.output_directory / "cases_raw.csv"
        )
        self.events_output = (
            self.output_directory / "events_raw.csv"
        )

        self.result = extract_xes(
            input_path=self.fixture_path,
            cases_output=self.cases_output,
            events_output=self.events_output,
            progress_every=0,
        )

    @staticmethod
    def read_csv_rows(path: Path) -> list[dict[str, str]]:
        """Read a CSV file as a list of dictionaries."""

        with path.open(
            mode="r",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            return list(csv.DictReader(csv_file))

    @staticmethod
    def read_csv_headers(path: Path) -> list[str]:
        """Read the header row from a CSV file."""

        with path.open(
            mode="r",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)
            return list(reader.fieldnames or [])

    def test_extraction_counts(self) -> None:
        """The extractor should return correct row counts."""

        self.assertEqual(
            self.result,
            {
                "case_count": 2,
                "event_count": 3,
            },
        )

    def test_output_files_are_created(self) -> None:
        """Completed case and event files should exist."""

        self.assertTrue(self.cases_output.is_file())
        self.assertTrue(self.events_output.is_file())

        self.assertFalse(
            self.cases_output.with_name(
                f"{self.cases_output.name}.tmp"
            ).exists()
        )
        self.assertFalse(
            self.events_output.with_name(
                f"{self.events_output.name}.tmp"
            ).exists()
        )

    def test_case_headers(self) -> None:
        """The case CSV should use the defined column order."""

        headers = self.read_csv_headers(self.cases_output)

        self.assertEqual(headers, CASE_HEADERS)

    def test_event_headers(self) -> None:
        """The event CSV should use the defined column order."""

        headers = self.read_csv_headers(self.events_output)

        self.assertEqual(headers, EVENT_HEADERS)

    def test_case_values_are_mapped(self) -> None:
        """Source trace attributes should map to case columns."""

        rows = self.read_csv_rows(self.cases_output)

        self.assertEqual(rows[0]["case_id"], "case-1")
        self.assertEqual(
            rows[0]["spend_classification"],
            "NPR",
        )
        self.assertEqual(
            rows[0]["item_category"],
            "2-way match",
        )
        self.assertEqual(
            rows[1]["item_category"],
            "3-way match, invoice before GR",
        )

    def test_missing_case_values_remain_empty(self) -> None:
        """Absent source attributes should remain empty."""

        rows = self.read_csv_rows(self.cases_output)

        self.assertEqual(
            rows[0]["purchasing_document_id"],
            "",
        )
        self.assertEqual(rows[0]["vendor_id"], "")

    def test_event_order_is_preserved(self) -> None:
        """Event positions should follow original trace order."""

        rows = self.read_csv_rows(self.events_output)

        self.assertEqual(
            [
                (
                    row["case_id"],
                    row["event_position"],
                    row["activity"],
                )
                for row in rows
            ],
            [
                (
                    "case-1",
                    "1",
                    "Create Purchase Order",
                ),
                (
                    "case-1",
                    "2",
                    "Clear Invoice",
                ),
                (
                    "case-2",
                    "1",
                    "Create Purchase Order",
                ),
            ],
        )

    def test_missing_marker_is_preserved(self) -> None:
        """Extraction should not silently clean missing markers."""

        rows = self.read_csv_rows(self.events_output)

        self.assertEqual(rows[1]["resource_id"], "NONE")

    def test_missing_input_is_rejected(self) -> None:
        """A missing source file should produce a clear error."""

        missing_input = (
            self.output_directory / "missing.xes"
        )

        with self.assertRaises(FileNotFoundError):
            extract_xes(
                input_path=missing_input,
                cases_output=self.cases_output,
                events_output=self.events_output,
                progress_every=0,
            )

    def test_duplicate_paths_are_rejected(self) -> None:
        """Input and output files must use different paths."""

        with self.assertRaises(ValueError):
            extract_xes(
                input_path=self.fixture_path,
                cases_output=self.fixture_path,
                events_output=self.events_output,
                progress_every=0,
            )

    def test_negative_progress_interval_is_rejected(
        self,
    ) -> None:
        """A negative progress interval is invalid."""

        with self.assertRaises(ValueError):
            extract_xes(
                input_path=self.fixture_path,
                cases_output=self.cases_output,
                events_output=self.events_output,
                progress_every=-1,
            )


if __name__ == "__main__":
    unittest.main()
