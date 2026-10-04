"""Tests for ProcessIQ bottleneck and statistical analysis."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from processiq.analyze_bottlenecks import analyze_bottlenecks


SELECTED_CATEGORY = "3-way match, invoice after GR"
OTHER_CATEGORY = "2-way match"


class TestAnalyzeBottlenecks(unittest.TestCase):
    """Exercise timing, transition, marker, and validation behaviour."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)

        self.cases_path = self.directory / "cases.csv"
        self.events_path = self.directory / "events.csv"
        self.timing_path = self.directory / "case_timing.csv"
        self.transition_output = self.directory / "transitions.csv"
        self.marker_output = self.directory / "markers.csv"
        self.report_output = self.directory / "report.json"

        self.case_definitions = {
            "base-a": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 1.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "base-b": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 2.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "multiple-gr": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 3.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "multiple-ir": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 10.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "multiple-service": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 4.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Service Entry Sheet",
                    "Record Service Entry Sheet",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "payment": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 8.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Set Payment Block",
                    "Remove Payment Block",
                    "Clear Invoice",
                ],
            },
            "cancellation": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 7.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Goods Receipt",
                    "Cancel Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "deletion": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 0.5,
                "activities": [
                    "Create Purchase Order Item",
                    "Delete Purchase Order Item",
                ],
            },
            "change": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 9.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Change Quantity",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "overlap": {
                "category": SELECTED_CATEGORY,
                "eligible": True,
                "duration": 12.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Change Quantity",
                    "Record Goods Receipt",
                    "Record Invoice Receipt",
                    "Record Invoice Receipt",
                    "Set Payment Block",
                    "Cancel Invoice Receipt",
                    "Clear Invoice",
                ],
            },
            "excluded": {
                "category": SELECTED_CATEGORY,
                "eligible": False,
                "duration": 400.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Clear Invoice",
                ],
            },
            "other": {
                "category": OTHER_CATEGORY,
                "eligible": True,
                "duration": 5.0,
                "activities": [
                    "Create Purchase Order Item",
                    "Record Invoice Receipt",
                    "Clear Invoice",
                ],
            },
        }

        self._write_inputs()

    def _write_inputs(self) -> None:
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
            for case_id, definition in self.case_definitions.items():
                writer.writerow(
                    {
                        "case_id": case_id,
                        "item_category": definition["category"],
                    }
                )

        with self.timing_path.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as timing_file:
            writer = csv.DictWriter(
                timing_file,
                fieldnames=[
                    "case_id",
                    "cycle_time_days",
                    "event_count",
                    "duration_eligible",
                ],
            )
            writer.writeheader()
            for case_id, definition in self.case_definitions.items():
                writer.writerow(
                    {
                        "case_id": case_id,
                        "cycle_time_days": definition["duration"],
                        "event_count": len(definition["activities"]),
                        "duration_eligible": str(
                            definition["eligible"]
                        ).lower(),
                    }
                )

        start = datetime(2018, 1, 1, tzinfo=timezone.utc)
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
                    "event_timestamp",
                ],
            )
            writer.writeheader()

            for case_id, definition in self.case_definitions.items():
                activities = definition["activities"]
                duration = float(definition["duration"])
                interval = (
                    duration / (len(activities) - 1)
                    if len(activities) > 1
                    else 0.0
                )

                for position, activity in enumerate(activities, start=1):
                    timestamp = start + timedelta(
                        days=interval * (position - 1)
                    )
                    writer.writerow(
                        {
                            "case_id": case_id,
                            "event_position": position,
                            "activity": activity,
                            "event_timestamp": timestamp.isoformat(),
                        }
                    )

    def _run_analysis(self) -> dict[str, object]:
        return analyze_bottlenecks(
            cases_path=self.cases_path,
            events_path=self.events_path,
            timing_path=self.timing_path,
            transition_output=self.transition_output,
            marker_output=self.marker_output,
            report_output=self.report_output,
            category=SELECTED_CATEGORY,
            minimum_transition_cases=1,
            top_transitions=10,
            progress_every=0,
        )

    def test_category_baseline_excludes_ineligible_duration(self) -> None:
        """The 400-day excluded case must not distort cycle-time statistics."""

        report = self._run_analysis()
        selected = next(
            row
            for row in report["category_cycle_time_baseline"]
            if row["item_category"] == SELECTED_CATEGORY
        )

        self.assertEqual(selected["total_cases"], 11)
        self.assertEqual(selected["eligible_cases"], 10)
        self.assertEqual(selected["excluded_cases"], 1)
        self.assertLess(selected["p95_days"], 20)

    def test_transition_waits_reconcile_to_eligible_cases(self) -> None:
        """Only selected, eligible case events should form transitions."""

        report = self._run_analysis()
        with self.transition_output.open(
            encoding="utf-8",
            newline="",
        ) as transition_file:
            rows = list(csv.DictReader(transition_file))

        expected_transitions = sum(
            len(definition["activities"]) - 1
            for definition in self.case_definitions.values()
            if definition["category"] == SELECTED_CATEGORY
            and definition["eligible"]
        )
        actual_transitions = sum(
            int(row["transition_count"]) for row in rows
        )

        self.assertEqual(actual_transitions, expected_transitions)
        self.assertGreater(report["transition_analysis"]["unique_transitions"], 0)
        self.assertAlmostEqual(
            sum(float(row["share_of_observed_wait"]) for row in rows),
            100.0,
            places=1,
        )

    def test_all_diagnostic_markers_are_compared(self) -> None:
        """Every defined marker should receive a two-group comparison."""

        self._run_analysis()
        with self.marker_output.open(
            encoding="utf-8",
            newline="",
        ) as marker_file:
            rows = {
                row["marker"]: row
                for row in csv.DictReader(marker_file)
            }

        self.assertEqual(len(rows), 7)
        self.assertEqual(
            int(rows["Multiple invoice receipts"]["cases_with_marker"]),
            2,
        )
        self.assertEqual(
            int(rows["Payment-block intervention"]["cases_with_marker"]),
            2,
        )
        self.assertEqual(
            int(rows["Multiple goods receipts"]["cases_with_marker"]),
            1,
        )

    def test_marker_statistics_include_effect_and_adjusted_p_value(self) -> None:
        """Significance should be accompanied by multiplicity and effect evidence."""

        report = self._run_analysis()

        for comparison in report["marker_comparisons"]:
            self.assertIn("adjusted_p_value", comparison)
            self.assertIn("rank_biserial_effect", comparison)
            self.assertIn(
                comparison["effect_magnitude"],
                {"negligible", "small", "medium", "large"},
            )
            self.assertGreaterEqual(comparison["adjusted_p_value"], 0.0)
            self.assertLessEqual(comparison["adjusted_p_value"], 1.0)

    def test_overlap_summary_keeps_marker_combinations_visible(self) -> None:
        """The four-marker case should remain identifiable in overlap results."""

        report = self._run_analysis()
        score_rows = {
            row["marker_count"]: row
            for row in report["overlap_score_summary"]
        }

        self.assertEqual(score_rows[4]["case_count"], 1)
        self.assertEqual(score_rows[4]["median_days"], 12.0)
        self.assertEqual(
            sum(row["case_count"] for row in score_rows.values()),
            10,
        )

    def test_written_report_matches_returned_report(self) -> None:
        """The JSON artifact should contain the same analysed scope."""

        returned_report = self._run_analysis()
        written_report = json.loads(
            self.report_output.read_text(encoding="utf-8")
        )

        self.assertEqual(
            written_report["scope"],
            returned_report["scope"],
        )
        self.assertEqual(
            written_report["scope"]["duration_eligible_selected_cases"],
            10,
        )

    def test_invalid_analysis_limits_are_rejected(self) -> None:
        """Limits and progress values must remain safe and meaningful."""

        with self.assertRaisesRegex(ValueError, "must be positive"):
            analyze_bottlenecks(
                cases_path=self.cases_path,
                events_path=self.events_path,
                timing_path=self.timing_path,
                transition_output=self.transition_output,
                marker_output=self.marker_output,
                report_output=self.report_output,
                minimum_transition_cases=0,
            )

    def test_duplicate_paths_are_rejected(self) -> None:
        """Generated analysis must never overwrite a source table."""

        with self.assertRaisesRegex(ValueError, "must all be different"):
            analyze_bottlenecks(
                cases_path=self.cases_path,
                events_path=self.events_path,
                timing_path=self.timing_path,
                transition_output=self.events_path,
                marker_output=self.marker_output,
                report_output=self.report_output,
                category=SELECTED_CATEGORY,
                minimum_transition_cases=1,
                top_transitions=10,
                progress_every=0,
            )


if __name__ == "__main__":
    unittest.main()
