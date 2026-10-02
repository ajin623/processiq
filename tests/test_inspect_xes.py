"""Tests for the memory-conscious XES profiler."""

from pathlib import Path
import unittest

from processiq.inspect_xes import profile_xes


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "minimal_event_log.xes"
)


class TestProfileXes(unittest.TestCase):
    """Verify the profiler using a small event log with known answers."""

    @classmethod
    def setUpClass(cls) -> None:
        """Create one profile that all tests can inspect."""

        cls.profile = profile_xes(
            FIXTURE_PATH,
            progress_interval=1_000_000,
        )

    def test_case_and_event_counts(self) -> None:
        """The profiler should count traces and events correctly."""

        self.assertEqual(self.profile["trace_count"], 2)
        self.assertEqual(self.profile["event_count"], 3)

    def test_events_per_trace(self) -> None:
        """The profiler should calculate the trace-size summary."""

        events_per_trace = self.profile["events_per_trace"]

        self.assertEqual(events_per_trace["minimum"], 1)
        self.assertEqual(events_per_trace["maximum"], 2)
        self.assertEqual(events_per_trace["mean"], 1.5)

    def test_activity_counts(self) -> None:
        """The profiler should count each activity."""

        activities = self.profile["activities"]

        self.assertEqual(activities["unique_count"], 2)
        self.assertEqual(
            activities["counts"]["Create Purchase Order"],
            2,
        )
        self.assertEqual(
            activities["counts"]["Clear Invoice"],
            1,
        )

    def test_resource_quality(self) -> None:
        """The profiler should distinguish resources from missing markers."""

        self.assertEqual(
            self.profile["resources"]["unique_non_missing_count"],
            2,
        )
        self.assertEqual(
            self.profile["required_field_gaps"][
                "missing_resource_events"
            ],
            1,
        )

    def test_timestamp_range(self) -> None:
        """The profiler should validate and compare timestamps."""

        timestamp_range = self.profile["timestamp_range"]

        self.assertEqual(
            timestamp_range["minimum"],
            "2018-01-01T10:00:00+00:00",
        )
        self.assertEqual(
            timestamp_range["maximum"],
            "2018-01-02T09:30:00+00:00",
        )
        self.assertEqual(
            self.profile["required_field_gaps"][
                "invalid_timestamp_events"
            ],
            0,
        )

    def test_timestamp_year_counts(self) -> None:
        """The profiler should count valid timestamps by year."""

        self.assertEqual(
            self.profile["timestamp_year_counts"],
            {"2018": 3},
        )

    def test_item_categories(self) -> None:
        """The profiler should count item categories."""

        categories = self.profile["item_categories"]

        self.assertEqual(categories["2-way match"], 1)
        self.assertEqual(
            categories["3-way match, invoice before GR"],
            1,
        )

    def test_trace_attribute_name_is_preserved(self) -> None:
        """The profiler must preserve trace-attribute names."""

        attribute_presence = self.profile[
            "trace_attribute_presence"
        ]

        self.assertEqual(
            attribute_presence["Spend classification text"],
            1,
        )


if __name__ == "__main__":
    unittest.main()