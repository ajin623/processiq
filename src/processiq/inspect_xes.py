"""Create a memory-conscious structural profile of an XES event log."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


MISSING_MARKERS = {"", "NONE", "UNKNOWN"}


def local_name(tag: str) -> str:
    """Return an XML tag without an optional namespace."""

    return tag.rsplit("}", maxsplit=1)[-1]


def read_attributes(element: ET.Element) -> dict[str, str]:
    """Read direct XES attribute children into a key-value dictionary."""

    attributes: dict[str, str] = {}

    for child in element:
        if local_name(child.tag) == "event":
            continue

        key = child.attrib.get("key")

        if key is not None:
            attributes[key] = child.attrib.get("value", "")

    return attributes


def is_missing(value: str | None) -> bool:
    """Return True when an XES value is absent or uses a missing marker."""

    if value is None:
        return True

    return value.strip().upper() in MISSING_MARKERS


def profile_xes(
    input_path: Path,
    progress_interval: int = 250_000,
) -> dict[str, object]:
    """Stream an XES file and return a structural profile."""

    trace_count = 0
    event_count = 0
    current_trace_event_count = 0
    minimum_events_per_trace: int | None = None
    maximum_events_per_trace = 0

    trace_attribute_presence: Counter[str] = Counter()
    event_attribute_presence: Counter[str] = Counter()
    activity_counts: Counter[str] = Counter()
    item_category_counts: Counter[str] = Counter()
    timestamp_year_counts: Counter[int] = Counter()

    resource_values: set[str] = set()

    missing_activity_count = 0
    missing_timestamp_count = 0
    invalid_timestamp_count = 0
    missing_resource_count = 0

    minimum_timestamp: datetime | None = None
    maximum_timestamp: datetime | None = None

    extensions: list[dict[str, str]] = []
    classifiers: list[dict[str, str]] = []
    global_defaults: dict[str, dict[str, str]] = {}

    parser = ET.iterparse(input_path, events=("start", "end"))
    first_event, root = next(parser)

    if first_event != "start" or local_name(root.tag) != "log":
        raise ValueError("The input file does not start with an XES log element.")

    root_attributes = dict(root.attrib)

    for parser_event, element in parser:
        element_name = local_name(element.tag)

        if parser_event == "start":
            if element_name == "trace":
                current_trace_event_count = 0

            continue

        if element_name == "extension":
            extensions.append(dict(element.attrib))
            element.clear()

        elif element_name == "classifier":
            classifiers.append(dict(element.attrib))
            element.clear()

        elif element_name == "global":
            scope = element.attrib.get("scope", "unknown")
            global_defaults[scope] = read_attributes(element)
            element.clear()

        elif element_name == "event":
            event_count += 1
            current_trace_event_count += 1

            attributes = read_attributes(element)
            event_attribute_presence.update(attributes.keys())

            activity = attributes.get("concept:name")

            if is_missing(activity):
                missing_activity_count += 1
            else:
                activity_counts[activity] += 1

            resource = attributes.get("org:resource")

            if is_missing(resource):
                missing_resource_count += 1
            else:
                resource_values.add(resource)

            timestamp = attributes.get("time:timestamp")

            if is_missing(timestamp):
                missing_timestamp_count += 1
            else:
                try:
                    parsed_timestamp = datetime.fromisoformat(
                        timestamp.replace("Z", "+00:00")
                    )
                except ValueError:
                    invalid_timestamp_count += 1
                else:
                    timestamp_year_counts[parsed_timestamp.year] += 1

                    if (
                        minimum_timestamp is None
                        or parsed_timestamp < minimum_timestamp
                    ):
                        minimum_timestamp = parsed_timestamp

                    if (
                        maximum_timestamp is None
                        or parsed_timestamp > maximum_timestamp
                    ):
                        maximum_timestamp = parsed_timestamp

            if event_count % progress_interval == 0:
                print(f"Processed {event_count:,} events...")

            element.clear()

        elif element_name == "trace":
            trace_count += 1

            attributes = read_attributes(element)
            trace_attribute_presence.update(attributes.keys())

            item_category = attributes.get("Item Category")

            if not is_missing(item_category):
                item_category_counts[item_category] += 1

            if (
                minimum_events_per_trace is None
                or current_trace_event_count < minimum_events_per_trace
            ):
                minimum_events_per_trace = current_trace_event_count

            if current_trace_event_count > maximum_events_per_trace:
                maximum_events_per_trace = current_trace_event_count

            element.clear()
            root.remove(element)

    mean_events_per_trace = (
        event_count / trace_count if trace_count else 0.0
    )

    return {
        "input_file": str(input_path),
        "root_attributes": root_attributes,
        "extensions": extensions,
        "classifiers": classifiers,
        "global_defaults": global_defaults,
        "trace_count": trace_count,
        "event_count": event_count,
        "events_per_trace": {
            "minimum": minimum_events_per_trace or 0,
            "maximum": maximum_events_per_trace,
            "mean": mean_events_per_trace,
        },
        "timestamp_range": {
            "minimum": (
                minimum_timestamp.isoformat()
                if minimum_timestamp is not None
                else None
            ),
            "maximum": (
                maximum_timestamp.isoformat()
                if maximum_timestamp is not None
                else None
            ),
        },
        "timestamp_year_counts": {
            str(year): count
            for year, count in sorted(timestamp_year_counts.items())
        },
        "required_field_gaps": {
            "missing_activity_events": missing_activity_count,
            "missing_timestamp_events": missing_timestamp_count,
            "invalid_timestamp_events": invalid_timestamp_count,
            "missing_resource_events": missing_resource_count,
        },
        "activities": {
            "unique_count": len(activity_counts),
            "counts": dict(sorted(activity_counts.items())),
        },
        "resources": {
            "unique_non_missing_count": len(resource_values),
        },
        "item_categories": dict(sorted(item_category_counts.items())),
        "trace_attribute_presence": dict(
            sorted(trace_attribute_presence.items())
        ),
        "event_attribute_presence": dict(
            sorted(event_attribute_presence.items())
        ),
    }


def main() -> None:
    """Run the XES profiler from the command line."""

    argument_parser = argparse.ArgumentParser(
        description="Create a structural profile of an XES event log."
    )
    argument_parser.add_argument(
        "input",
        type=Path,
        help="Path to the source XES file.",
    )
    argument_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/interim/xes_profile.json"),
        help="Path for the generated JSON profile.",
    )

    arguments = argument_parser.parse_args()

    if not arguments.input.is_file():
        argument_parser.error(
            f"Input file does not exist: {arguments.input}"
        )

    profile = profile_xes(arguments.input)

    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Profile written to: {arguments.output}")
    print(f"Traces: {profile['trace_count']:,}")
    print(f"Events: {profile['event_count']:,}")
    print(
        "Unique activities: "
        f"{profile['activities']['unique_count']:,}"
    )


if __name__ == "__main__":
    main()