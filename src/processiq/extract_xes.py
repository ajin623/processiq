"""Extract case and event tables from an XES event log."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from xml.etree.ElementTree import Element, iterparse


CASE_FIELD_MAP = {
    "case_id": "concept:name",
    "purchasing_document_id": "Purchasing Document",
    "item_id": "Item",
    "item_type": "Item Type",
    "gr_based_invoice_verification": "GR-Based Inv. Verif.",
    "goods_receipt_required": "Goods Receipt",
    "source_system_id": "Source",
    "purchasing_document_category": "Purch. Doc. Category name",
    "company_id": "Company",
    "spend_classification": "Spend classification text",
    "spend_area": "Spend area text",
    "sub_spend_area": "Sub spend area text",
    "vendor_id": "Vendor",
    "vendor_name": "Name",
    "document_type": "Document Type",
    "item_category": "Item Category",
}

EVENT_FIELD_MAP = {
    "activity": "concept:name",
    "event_timestamp": "time:timestamp",
    "resource_id": "org:resource",
    "user_id": "User",
    "cumulative_net_worth": "Cumulative net worth (EUR)",
}

CASE_HEADERS = list(CASE_FIELD_MAP)
EVENT_HEADERS = [
    "case_id",
    "event_position",
    *EVENT_FIELD_MAP,
]


def local_name(tag: str) -> str:
    """Return an XML tag without its optional namespace."""

    return tag.rsplit("}", maxsplit=1)[-1]


def read_attributes(element: Element) -> dict[str, str]:
    """Read direct XES attributes from an XML element."""

    attributes: dict[str, str] = {}

    for child in element:
        key = child.attrib.get("key")

        if key is None:
            continue

        attributes[key] = child.attrib.get("value", "")

    return attributes


def validate_paths(
    input_path: Path,
    cases_output: Path,
    events_output: Path,
) -> None:
    """Check that the input and output paths are safe to use."""

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input XES file does not exist: {input_path}"
        )

    if not input_path.is_file():
        raise ValueError(
            f"Input XES path is not a file: {input_path}"
        )

    resolved_paths = {
        input_path.resolve(),
        cases_output.resolve(),
        events_output.resolve(),
    }

    if len(resolved_paths) != 3:
        raise ValueError(
            "Input, cases output, and events output must use "
            "three different paths."
        )


def extract_xes(
    input_path: Path,
    cases_output: Path,
    events_output: Path,
    progress_every: int = 25_000,
) -> dict[str, int]:
    """Extract flat case and event CSV files from an XES event log."""

    if progress_every < 0:
        raise ValueError("progress_every cannot be negative.")

    validate_paths(
        input_path=input_path,
        cases_output=cases_output,
        events_output=events_output,
    )

    cases_output.parent.mkdir(parents=True, exist_ok=True)
    events_output.parent.mkdir(parents=True, exist_ok=True)

    cases_temporary = cases_output.with_name(
        f"{cases_output.name}.tmp"
    )
    events_temporary = events_output.with_name(
        f"{events_output.name}.tmp"
    )

    case_count = 0
    event_count = 0

    try:
        with (
            cases_temporary.open(
                mode="w",
                encoding="utf-8",
                newline="",
            ) as cases_file,
            events_temporary.open(
                mode="w",
                encoding="utf-8",
                newline="",
            ) as events_file,
        ):
            cases_writer = csv.DictWriter(
                cases_file,
                fieldnames=CASE_HEADERS,
            )
            events_writer = csv.DictWriter(
                events_file,
                fieldnames=EVENT_HEADERS,
            )

            cases_writer.writeheader()
            events_writer.writeheader()

            parser = iterparse(
                input_path,
                events=("start", "end"),
            )
            _, root = next(parser)

            for parser_event, element in parser:
                if parser_event != "end":
                    continue

                if local_name(element.tag) != "trace":
                    continue

                trace_attributes = read_attributes(element)

                case_row = {
                    output_column: trace_attributes.get(
                        source_key,
                        "",
                    )
                    for output_column, source_key
                    in CASE_FIELD_MAP.items()
                }

                cases_writer.writerow(case_row)
                case_count += 1

                case_id = case_row["case_id"]
                event_position = 0

                for child in element:
                    if local_name(child.tag) != "event":
                        continue

                    event_position += 1
                    event_attributes = read_attributes(child)

                    event_row = {
                        "case_id": case_id,
                        "event_position": event_position,
                    }

                    event_row.update(
                        {
                            output_column: event_attributes.get(
                                source_key,
                                "",
                            )
                            for output_column, source_key
                            in EVENT_FIELD_MAP.items()
                        }
                    )

                    events_writer.writerow(event_row)
                    event_count += 1

                if (
                    progress_every > 0
                    and case_count % progress_every == 0
                ):
                    print(
                        f"Processed {case_count:,} cases "
                        f"and {event_count:,} events..."
                    )

                root.remove(element)
                element.clear()

        cases_temporary.replace(cases_output)
        events_temporary.replace(events_output)

    except BaseException:
        cases_temporary.unlink(missing_ok=True)
        events_temporary.unlink(missing_ok=True)
        raise

    return {
        "case_count": case_count,
        "event_count": event_count,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract flat case and event tables from an XES event log."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to the source XES file.",
    )
    parser.add_argument(
        "--cases-output",
        type=Path,
        default=Path("data/interim/cases_raw.csv"),
        help="Path for the extracted case CSV file.",
    )
    parser.add_argument(
        "--events-output",
        type=Path,
        default=Path("data/interim/events_raw.csv"),
        help="Path for the extracted event CSV file.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25_000,
        help=(
            "Print progress after this many cases. "
            "Use 0 to disable progress messages."
        ),
    )

    return parser


def main() -> None:
    """Run the extractor from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    result = extract_xes(
        input_path=arguments.input,
        cases_output=arguments.cases_output,
        events_output=arguments.events_output,
        progress_every=arguments.progress_every,
    )

    print("Extraction completed.")
    print(f"Cases written: {result['case_count']:,}")
    print(f"Events written: {result['event_count']:,}")
    print(f"Cases file: {arguments.cases_output}")
    print(f"Events file: {arguments.events_output}")


if __name__ == "__main__":
    main()
