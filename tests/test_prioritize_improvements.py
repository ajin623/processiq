"""Tests for transparent improvement-opportunity prioritisation."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from processiq.prioritize_improvements import (
    calculate_overall_score,
    reach_score,
    run_improvement_prioritization,
    time_impact_score,
)


class TestPrioritizeImprovements(unittest.TestCase):
    """Verify ranking logic, safeguards, and generated artifacts."""

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)

        self.base_path = Path(self.temporary_directory.name)
        self.bottleneck_path = self.base_path / "bottleneck_report.json"
        self.conformance_path = self.base_path / "conformance_report.json"
        self.priority_output = self.base_path / "improvement_priorities.csv"
        self.report_output = self.base_path / "improvement_priorities.json"

        self.bottleneck_report = {
            "generated_at_utc": "2026-10-04T22:39:40+00:00",
            "scope": {
                "all_events_scanned": 1_595_923,
                "duration_eligible_selected_cases": 15_045,
                "duration_excluded_selected_cases": 137,
                "selected_category": "3-way match, invoice after GR",
                "selected_events_in_eligible_cases": 302_275,
                "single_event_or_missing_selected_cases": 163,
                "total_selected_cases": 15_182,
            },
            "transition_analysis": {
                "focused_transitions": [
                    {
                        "affected_cases": 7_718,
                        "from_activity": "Record Invoice Receipt",
                        "median_wait_hours": 527.10,
                        "p75_wait_hours": 1_026.08,
                        "p90_wait_hours": 1_560.80,
                        "share_of_observed_wait": 24.32,
                        "to_activity": "Clear Invoice",
                        "total_wait_days": 248_151.48,
                        "transition_count": 8_702,
                        "zero_time_percentage": 0.15,
                    },
                    {
                        "affected_cases": 5_360,
                        "from_activity": "Record Goods Receipt",
                        "median_wait_hours": 458.02,
                        "p75_wait_hours": 993.40,
                        "p90_wait_hours": 1_612.25,
                        "share_of_observed_wait": 18.52,
                        "to_activity": "Record Invoice Receipt",
                        "total_wait_days": 188_995.50,
                        "transition_count": 5_595,
                        "zero_time_percentage": 0.00,
                    },
                    {
                        "affected_cases": 4_886,
                        "from_activity": "Vendor creates invoice",
                        "median_wait_hours": 489.38,
                        "p75_wait_hours": 1_018.63,
                        "p90_wait_hours": 1_632.75,
                        "share_of_observed_wait": 14.42,
                        "to_activity": "Record Invoice Receipt",
                        "total_wait_days": 147_100.44,
                        "transition_count": 5_186,
                        "zero_time_percentage": 0.00,
                    },
                ],
                "minimum_affected_cases_for_focus": 100,
                "top_transition_limit": 20,
                "unique_transitions": 297,
            },
            "marker_comparisons": [
                {
                    "adjusted_p_value": 5.486e-298,
                    "average_events_with": 9.67,
                    "average_events_without": 21.93,
                    "cases_with_marker": 2_252,
                    "cases_without_marker": 12_793,
                    "effect_magnitude": "large",
                    "mann_whitney_u": 0.0,
                    "marker": "Payment-block intervention",
                    "median_days_with": 91.93,
                    "median_days_without": 55.97,
                    "median_difference_days": 35.96,
                    "p90_days_with": 173.93,
                    "p90_days_without": 120.67,
                    "rank_biserial_effect": 0.4870,
                    "raw_p_value": 0.0,
                    "statistically_significant": True,
                },
                {
                    "adjusted_p_value": 0.0,
                    "average_events_with": 30.39,
                    "average_events_without": 19.18,
                    "cases_with_marker": 1_221,
                    "cases_without_marker": 13_824,
                    "effect_magnitude": "large",
                    "mann_whitney_u": 13_947_407.5,
                    "marker": "Multiple invoice receipts",
                    "median_days_with": 125.56,
                    "median_days_without": 58.10,
                    "median_difference_days": 67.46,
                    "p90_days_with": 336.03,
                    "p90_days_without": 118.74,
                    "rank_biserial_effect": 0.6526,
                    "raw_p_value": 0.0,
                    "statistically_significant": True,
                },
            ],
            "limitations": [
                "Waiting times are calendar time, not working time.",
                "Associations do not prove causation.",
            ],
        }

        self.conformance_report = {
            "generated_at_utc": "2026-10-04T21:39:11+00:00",
            "scope": {
                "all_events_scanned": 1_595_923,
                "item_category": "3-way match, invoice after GR",
                "selected_case_count": 15_182,
                "selected_event_count": 319_233,
            },
            "conformance": {
                "review_reason_counts": {
                    "clearing_before_invoice_receipt": 7,
                    "clearing_without_invoice_receipt": 2,
                },
                "status_counts": {
                    "conforming": 9_667,
                    "incomplete_evidence": 5_506,
                    "review_required": 9,
                },
                "status_percentages": {
                    "conforming": 63.67,
                    "incomplete_evidence": 36.27,
                    "review_required": 0.06,
                },
            },
        }

        self.write_json(self.bottleneck_path, self.bottleneck_report)
        self.write_json(self.conformance_path, self.conformance_report)

    @staticmethod
    def write_json(path: Path, content: dict[str, object]) -> None:
        path.write_text(
            json.dumps(content, indent=2) + "\n",
            encoding="utf-8",
        )

    def run_analysis(self) -> dict[str, object]:
        return run_improvement_prioritization(
            bottleneck_report_path=self.bottleneck_path,
            conformance_report_path=self.conformance_path,
            priority_output_path=self.priority_output,
            report_output_path=self.report_output,
        )

    def test_ranked_opportunities_follow_transparent_scores(self) -> None:
        """Evidence should produce a deterministic, explainable ranking."""

        report = self.run_analysis()
        opportunities = report["ranked_operational_opportunities"]

        self.assertEqual(
            [item["opportunity_id"] for item in opportunities],
            [
                "payment_block_intervention",
                "invoice_receipt_to_clearing",
                "multiple_invoice_receipts",
                "goods_receipt_to_invoice_receipt",
                "vendor_invoice_to_invoice_receipt",
            ],
        )
        self.assertEqual(
            [item["overall_score"] for item in opportunities],
            [78.0, 77.0, 75.0, 70.0, 70.0],
        )
        self.assertEqual(
            [item["rank"] for item in opportunities],
            [1, 2, 3, 4, 5],
        )

    def test_priority_bands_are_relative_not_financial_claims(self) -> None:
        """Priority bands should be labelled without inventing savings."""

        report = self.run_analysis()
        opportunities = report["ranked_operational_opportunities"]

        self.assertEqual(
            [item["priority_band"] for item in opportunities],
            ["P1", "P1", "P1", "P2", "P2"],
        )
        self.assertIn(
            "No monetary benefit is estimated",
            " ".join(report["limitations"]),
        )

    def test_control_actions_remain_outside_operational_ranking(self) -> None:
        """Small control exceptions must not disappear inside impact scores."""

        report = self.run_analysis()
        actions = report["control_and_data_actions"]

        self.assertEqual(len(report["ranked_operational_opportunities"]), 5)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["action_type"], "mandatory_control_review")
        self.assertEqual(actions[0]["affected_cases"], 9)
        self.assertEqual(
            actions[0]["reason_counts"],
            {
                "clearing_before_invoice_receipt": 7,
                "clearing_without_invoice_receipt": 2,
            },
        )
        self.assertEqual(actions[1]["action_type"], "data_and_scope_control")
        self.assertEqual(actions[1]["affected_cases"], 5_506)

    def test_csv_and_json_outputs_reconcile(self) -> None:
        """Written artifacts should match the returned analysis."""

        report = self.run_analysis()

        self.assertTrue(self.priority_output.is_file())
        self.assertTrue(self.report_output.is_file())

        written_report = json.loads(
            self.report_output.read_text(encoding="utf-8")
        )
        self.assertEqual(written_report, report)

        with self.priority_output.open(encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(
            rows[0]["opportunity_id"],
            "payment_block_intervention",
        )
        self.assertEqual(rows[0]["overall_score"], "78.0")

    def test_report_categories_must_match(self) -> None:
        """Evidence from different categories must never be combined."""

        changed_report = deepcopy(self.conformance_report)
        changed_report["scope"]["item_category"] = "2-way match"
        self.write_json(self.conformance_path, changed_report)

        with self.assertRaisesRegex(ValueError, "categories do not match"):
            self.run_analysis()

    def test_required_transition_must_exist(self) -> None:
        """A missing evidence row should stop rather than silently score zero."""

        changed_report = deepcopy(self.bottleneck_report)
        changed_report["transition_analysis"]["focused_transitions"] = (
            changed_report["transition_analysis"]["focused_transitions"][1:]
        )
        self.write_json(self.bottleneck_path, changed_report)

        with self.assertRaisesRegex(ValueError, "was not found"):
            self.run_analysis()

    def test_negative_marker_association_is_rejected(self) -> None:
        """The configured delay opportunity must show a positive association."""

        changed_report = deepcopy(self.bottleneck_report)

        for marker in changed_report["marker_comparisons"]:
            if marker["marker"] == "Payment-block intervention":
                marker["median_difference_days"] = -10.0

        self.write_json(self.bottleneck_path, changed_report)

        with self.assertRaisesRegex(ValueError, "positive duration association"):
            self.run_analysis()

    def test_input_reports_cannot_be_overwritten(self) -> None:
        """Generated artifacts must never replace analytical evidence."""

        with self.assertRaisesRegex(
            ValueError,
            "must not overwrite an input report",
        ):
            run_improvement_prioritization(
                bottleneck_report_path=self.bottleneck_path,
                conformance_report_path=self.conformance_path,
                priority_output_path=self.bottleneck_path,
                report_output_path=self.report_output,
            )

    def test_scoring_boundaries_are_explicit(self) -> None:
        """Threshold behavior should remain visible and stable."""

        self.assertEqual(reach_score(40.0), 5)
        self.assertEqual(reach_score(25.0), 4)
        self.assertEqual(reach_score(10.0), 3)
        self.assertEqual(reach_score(5.0), 2)
        self.assertEqual(reach_score(4.99), 1)

        self.assertEqual(time_impact_score(60.0), 5)
        self.assertEqual(time_impact_score(30.0), 4)
        self.assertEqual(time_impact_score(15.0), 3)
        self.assertEqual(time_impact_score(5.0), 2)
        self.assertEqual(time_impact_score(4.99), 1)

        self.assertEqual(
            calculate_overall_score(
                {
                    "reach": 5,
                    "time_impact": 4,
                    "evidence_strength": 5,
                    "actionability": 4,
                    "confidence": 3,
                }
            ),
            88.0,
        )


if __name__ == "__main__":
    unittest.main()
