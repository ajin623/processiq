"""Tests for ProcessIQ process discovery and variant analysis."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from processiq.discover_process import (
    DEFAULT_CATEGORY,
    prepare_pm4py_dataframe,
    profile_variants,
    read_case_categories,
    run_process_discovery,
    select_dfg_for_visualization,
)
from processiq.transform_data import (
    PROCESSED_CASE_HEADERS,
    PROCESSED_EVENT_HEADERS,
)


SECOND_CATEGORY = "2-way match"

CREATE_ACTIVITY = "Create Purchase Order Item"
GOODS_RECEIPT_ACTIVITY = "Record Goods Receipt"
INVOICE_ACTIVITY = "Record Invoice Receipt"
CLEAR_ACTIVITY = "Clear Invoice"


def write_csv(
    path: Path,
    headers: list[str],
    rows: list[dict[str, object]],
) -> None:
    """Write a small test CSV using the real processed schema."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
            complete_row = {
                header: row.get(header, "")
                for header in headers
            }

            writer.writerow(complete_row)


class TestProcessDiscovery(unittest.TestCase):
    """Test variant counting and PM4Py process discovery."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create one temporary dataset for this test class."""

        cls.temporary_directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary_directory.name)

        cls.cases_path = cls.root / "cases.csv"
        cls.events_path = cls.root / "events.csv"

        case_rows = [
            {
                "case_id": "case-1",
                "item_category": DEFAULT_CATEGORY,
                "spend_data_complete": "true",
            },
            {
                "case_id": "case-2",
                "item_category": DEFAULT_CATEGORY,
                "spend_data_complete": "true",
            },
            {
                "case_id": "case-3",
                "item_category": SECOND_CATEGORY,
                "spend_data_complete": "true",
            },
            {
                "case_id": "case-4",
                "item_category": SECOND_CATEGORY,
                "spend_data_complete": "true",
            },
        ]

        event_rows = [
            {
                "case_id": "case-1",
                "event_position": 1,
                "activity": CREATE_ACTIVITY,
                "event_timestamp": "2018-01-01T10:00:00+00:00",
                "resource_id": "user-1",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-1",
                "event_position": 2,
                "activity": GOODS_RECEIPT_ACTIVITY,
                "event_timestamp": "2018-01-01T10:00:00+00:00",
                "resource_id": "user-2",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-1",
                "event_position": 3,
                "activity": INVOICE_ACTIVITY,
                "event_timestamp": "2018-01-01T11:00:00+00:00",
                "resource_id": "user-3",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-2",
                "event_position": 1,
                "activity": CREATE_ACTIVITY,
                "event_timestamp": "2018-01-02T09:00:00+00:00",
                "resource_id": "user-1",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-2",
                "event_position": 2,
                "activity": INVOICE_ACTIVITY,
                "event_timestamp": "2018-01-02T10:00:00+00:00",
                "resource_id": "user-3",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-3",
                "event_position": 1,
                "activity": CREATE_ACTIVITY,
                "event_timestamp": "2018-01-03T09:00:00+00:00",
                "resource_id": "user-1",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-3",
                "event_position": 2,
                "activity": CLEAR_ACTIVITY,
                "event_timestamp": "2018-01-03T10:00:00+00:00",
                "resource_id": "user-4",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-4",
                "event_position": 1,
                "activity": CREATE_ACTIVITY,
                "event_timestamp": "2018-01-04T09:00:00+00:00",
                "resource_id": "user-1",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
            {
                "case_id": "case-4",
                "event_position": 2,
                "activity": CLEAR_ACTIVITY,
                "event_timestamp": "2018-01-04T10:00:00+00:00",
                "resource_id": "user-4",
                "resource_recorded": "true",
                "timestamp_in_analysis_window": "true",
            },
        ]

        write_csv(
            path=cls.cases_path,
            headers=PROCESSED_CASE_HEADERS,
            rows=case_rows,
        )

        write_csv(
            path=cls.events_path,
            headers=PROCESSED_EVENT_HEADERS,
            rows=event_rows,
        )

        (
            cls.case_categories,
            cls.expected_category_counts,
        ) = read_case_categories(cls.cases_path)

        (
            cls.variants_by_category,
            cls.observed_category_counts,
            cls.selected_events,
            cls.total_event_count,
        ) = profile_variants(
            events_path=cls.events_path,
            case_categories=cls.case_categories,
            expected_category_case_counts=(
                cls.expected_category_counts
            ),
            selected_category=DEFAULT_CATEGORY,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        """Remove all temporary test files."""

        cls.temporary_directory.cleanup()

    def test_case_categories_are_read(self) -> None:
        """Each case should retain its business category."""

        self.assertEqual(
            len(self.case_categories),
            4,
        )

        self.assertEqual(
            self.case_categories["case-1"],
            DEFAULT_CATEGORY,
        )

        self.assertEqual(
            self.case_categories["case-3"],
            SECOND_CATEGORY,
        )

        self.assertEqual(
            self.expected_category_counts[DEFAULT_CATEGORY],
            2,
        )

        self.assertEqual(
            self.expected_category_counts[SECOND_CATEGORY],
            2,
        )

    def test_variants_are_counted_by_category(self) -> None:
        """Repeated and alternative paths should be counted correctly."""

        expected_selected_variants = Counter(
            {
                (
                    CREATE_ACTIVITY,
                    GOODS_RECEIPT_ACTIVITY,
                    INVOICE_ACTIVITY,
                ): 1,
                (
                    CREATE_ACTIVITY,
                    INVOICE_ACTIVITY,
                ): 1,
            }
        )

        expected_second_category_variants = Counter(
            {
                (
                    CREATE_ACTIVITY,
                    CLEAR_ACTIVITY,
                ): 2,
            }
        )

        self.assertEqual(
            self.variants_by_category[DEFAULT_CATEGORY],
            expected_selected_variants,
        )

        self.assertEqual(
            self.variants_by_category[SECOND_CATEGORY],
            expected_second_category_variants,
        )

        self.assertEqual(
            self.observed_category_counts,
            self.expected_category_counts,
        )

        self.assertEqual(
            self.total_event_count,
            9,
        )

        self.assertEqual(
            len(self.selected_events),
            5,
        )

    def test_equal_timestamps_preserve_event_position(self) -> None:
        """Original event position should break timestamp ties."""

        dataframe = prepare_pm4py_dataframe(
            self.selected_events
        )

        case_one_events = dataframe.loc[
            dataframe["case_id"] == "case-1"
        ].sort_values(
            by="event_position",
            kind="stable",
        )

        self.assertEqual(
            case_one_events["activity"].tolist(),
            [
                CREATE_ACTIVITY,
                GOODS_RECEIPT_ACTIVITY,
                INVOICE_ACTIVITY,
            ],
        )

    def test_process_discovery_writes_outputs(self) -> None:
        """A valid dataset should produce JSON and SVG outputs."""

        report_path = self.root / "process_discovery.json"
        dfg_path = self.root / "directly_follows_graph.svg"
        process_tree_path = self.root / "process_tree.svg"

        report = run_process_discovery(
            cases_path=self.cases_path,
            events_path=self.events_path,
            selected_category=DEFAULT_CATEGORY,
            top_variants=5,
            top_transitions=10,
            noise_threshold=0.0,
            maximum_dfg_edges=10,
            report_output=report_path,
            dfg_output=dfg_path,
            process_tree_output=process_tree_path,
        )

        self.assertTrue(report_path.is_file())
        self.assertTrue(dfg_path.is_file())
        self.assertTrue(process_tree_path.is_file())

        self.assertGreater(
            report_path.stat().st_size,
            0,
        )

        self.assertGreater(
            dfg_path.stat().st_size,
            0,
        )

        self.assertGreater(
            process_tree_path.stat().st_size,
            0,
        )

        saved_report = json.loads(
            report_path.read_text(encoding="utf-8")
        )

        self.assertEqual(
            saved_report,
            report,
        )

        serialised_report = json.dumps(
            saved_report,
            sort_keys=True,
        )

        self.assertIn(
            DEFAULT_CATEGORY,
            serialised_report,
        )

        self.assertIn(
            CREATE_ACTIVITY,
            serialised_report,
        )

    def test_dfg_visualization_filters_removed_boundaries(
        self,
    ) -> None:
        """Boundary nodes removed with rare edges must not remain."""

        full_dfg = {
            (
                "Common Start",
                "Common End",
            ): 100,
            (
                "Rare Start",
                "Rare End",
            ): 1,
        }

        start_activities = {
            "Common Start": 100,
            "Rare Start": 1,
        }

        end_activities = {
            "Common End": 100,
            "Rare End": 1,
        }

        (
            visual_dfg,
            visual_start_activities,
            visual_end_activities,
        ) = select_dfg_for_visualization(
            dfg=full_dfg,
            start_activities=start_activities,
            end_activities=end_activities,
            maximum_edges=1,
        )

        self.assertEqual(
            visual_dfg,
            {
                (
                    "Common Start",
                    "Common End",
                ): 100,
            },
        )

        self.assertEqual(
            visual_start_activities,
            {
                "Common Start": 100,
            },
        )

        self.assertEqual(
            visual_end_activities,
            {
                "Common End": 100,
            },
        )

    def test_unknown_selected_category_is_rejected(self) -> None:
        """Discovery should stop when the chosen category is absent."""

        with self.assertRaises(ValueError):
            run_process_discovery(
                cases_path=self.cases_path,
                events_path=self.events_path,
                selected_category="Category that does not exist",
                report_output=None,
                dfg_output=None,
                process_tree_output=None,
            )

    def test_invalid_top_variant_limit_is_rejected(self) -> None:
        """The number of requested variants must be positive."""

        with self.assertRaises(ValueError):
            run_process_discovery(
                cases_path=self.cases_path,
                events_path=self.events_path,
                selected_category=DEFAULT_CATEGORY,
                top_variants=0,
                report_output=None,
                dfg_output=None,
                process_tree_output=None,
            )

    def test_missing_case_file_is_rejected(self) -> None:
        """A missing input file should produce a clear error."""

        missing_path = self.root / "missing-cases.csv"

        with self.assertRaises(FileNotFoundError):
            read_case_categories(missing_path)


if __name__ == "__main__":
    unittest.main()
