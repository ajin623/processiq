"""Discover process variants and PM4Py models."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
import pm4py

from processiq.transform_data import (
    PROCESSED_CASE_HEADERS,
    PROCESSED_EVENT_HEADERS,
)


DEFAULT_CATEGORY = "3-way match, invoice after GR"


def validate_input_file(path: Path) -> None:
    """Require an existing regular input file."""

    if not path.exists():
        raise FileNotFoundError(
            f"Input file does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"Input path is not a file: {path}"
        )


def validate_csv_headers(
    reader: csv.DictReader,
    expected_headers: list[str],
    path: Path,
) -> None:
    """Require the expected CSV column order."""

    actual_headers = list(reader.fieldnames or [])

    if actual_headers != expected_headers:
        raise ValueError(
            f"Unexpected columns in {path}.\n"
            f"Expected: {expected_headers}\n"
            f"Actual:   {actual_headers}"
        )


def read_case_categories(
    cases_path: Path,
) -> tuple[dict[str, str], Counter[str]]:
    """Read the item category belonging to every case."""

    case_categories: dict[str, str] = {}
    category_case_counts: Counter[str] = Counter()

    with cases_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as cases_file:
        reader = csv.DictReader(cases_file)

        validate_csv_headers(
            reader=reader,
            expected_headers=PROCESSED_CASE_HEADERS,
            path=cases_path,
        )

        for row in reader:
            case_id = row["case_id"]
            category = row["item_category"]

            if case_id in case_categories:
                raise ValueError(
                    f"Duplicate case identifier: {case_id}"
                )

            case_categories[case_id] = category
            category_case_counts[category] += 1

    return case_categories, category_case_counts


def profile_variants(
    events_path: Path,
    case_categories: dict[str, str],
    expected_category_case_counts: Counter[str],
    selected_category: str,
) -> tuple[
    dict[str, Counter[tuple[str, ...]]],
    Counter[str],
    list[dict[str, object]],
    int,
]:
    """Count all variants and collect one selected cohort."""

    variant_counts: dict[
        str,
        Counter[tuple[str, ...]],
    ] = defaultdict(Counter)

    observed_category_case_counts: Counter[str] = Counter()
    selected_events: list[dict[str, object]] = []

    current_case_id: str | None = None
    current_activities: list[str] = []
    total_event_count = 0

    def finish_current_case() -> None:
        """Store the completed case variant."""

        if current_case_id is None:
            return

        category = case_categories[current_case_id]
        variant = tuple(current_activities)

        variant_counts[category][variant] += 1
        observed_category_case_counts[category] += 1

    with events_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as events_file:
        reader = csv.DictReader(events_file)

        validate_csv_headers(
            reader=reader,
            expected_headers=PROCESSED_EVENT_HEADERS,
            path=events_path,
        )

        for row in reader:
            total_event_count += 1
            case_id = row["case_id"]

            if case_id not in case_categories:
                raise ValueError(
                    f"Event references unknown case: {case_id}"
                )

            if case_id != current_case_id:
                finish_current_case()
                current_case_id = case_id
                current_activities = []

            current_activities.append(row["activity"])

            if (
                case_categories[case_id]
                == selected_category
            ):
                selected_events.append(
                    {
                        "case_id": case_id,
                        "event_position": int(
                            row["event_position"]
                        ),
                        "activity": row["activity"],
                        "event_timestamp": (
                            row["event_timestamp"]
                        ),
                    }
                )

    finish_current_case()

    if (
        observed_category_case_counts
        != expected_category_case_counts
    ):
        raise ValueError(
            "Case counts reconstructed from events do not "
            "match the processed cases table."
        )

    return (
        variant_counts,
        observed_category_case_counts,
        selected_events,
        total_event_count,
    )


def summarise_variants(
    variants: Counter[tuple[str, ...]],
    top_n: int,
) -> dict[str, object]:
    """Create a concise variant summary."""

    case_count = sum(variants.values())
    ordered_variants = variants.most_common()

    top_variants: list[dict[str, object]] = []
    cumulative_cases = 0

    for rank, (variant, count) in enumerate(
        ordered_variants[:top_n],
        start=1,
    ):
        cumulative_cases += count

        top_variants.append(
            {
                "rank": rank,
                "activities": list(variant),
                "activity_count": len(variant),
                "case_count": count,
                "case_share": round(
                    count / case_count,
                    6,
                ),
                "cumulative_case_share": round(
                    cumulative_cases / case_count,
                    6,
                ),
            }
        )

    top_n_case_count = sum(
        count
        for _, count in ordered_variants[:top_n]
    )

    return {
        "case_count": case_count,
        "unique_variant_count": len(variants),
        "top_n": top_n,
        "top_n_case_count": top_n_case_count,
        "top_n_case_coverage": round(
            top_n_case_count / case_count,
            6,
        ),
        "top_variants": top_variants,
    }


def prepare_pm4py_dataframe(
    selected_events: list[dict[str, object]],
) -> pd.DataFrame:
    """Create a correctly ordered PM4Py dataframe."""

    if not selected_events:
        raise ValueError(
            "The selected category contains no events."
        )

    dataframe = pd.DataFrame(selected_events)

    dataframe["event_timestamp"] = pd.to_datetime(
        dataframe["event_timestamp"],
        utc=True,
    )

    dataframe = dataframe.sort_values(
        ["case_id", "event_position"],
        kind="stable",
    ).reset_index(drop=True)

    return pm4py.format_dataframe(
        dataframe,
        case_id="case_id",
        activity_key="activity",
        timestamp_key="event_timestamp",
    )


def summarise_dfg(
    dfg: dict[tuple[str, str], int],
    start_activities: dict[str, int],
    end_activities: dict[str, int],
    top_n: int,
) -> dict[str, object]:
    """Create a serialisable DFG summary."""

    total_transition_occurrences = sum(dfg.values())

    top_transitions = []

    for rank, (transition, count) in enumerate(
        sorted(
            dfg.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )[:top_n],
        start=1,
    ):
        from_activity, to_activity = transition

        top_transitions.append(
            {
                "rank": rank,
                "from_activity": from_activity,
                "to_activity": to_activity,
                "occurrence_count": count,
                "occurrence_share": round(
                    count
                    / total_transition_occurrences,
                    6,
                ),
            }
        )

    return {
        "unique_transition_count": len(dfg),
        "total_transition_occurrences": (
            total_transition_occurrences
        ),
        "start_activities": dict(
            sorted(start_activities.items())
        ),
        "end_activities": dict(
            sorted(end_activities.items())
        ),
        "top_transitions": top_transitions,
    }


def select_dfg_for_visualization(
    dfg: dict[tuple[str, str], int],
    start_activities: dict[str, int],
    end_activities: dict[str, int],
    maximum_edges: int,
) -> tuple[
    dict[tuple[str, str], int],
    dict[str, int],
    dict[str, int],
]:
    """Create a consistent, limited DFG for display.

    PM4Py can limit a DFG internally, but its visualizer may
    retain start or end activities whose edges were removed.
    This function limits the edges first and then keeps only
    boundary activities that still exist in the displayed graph.
    The complete DFG remains unchanged for analytical results.
    """

    if maximum_edges <= 0:
        raise ValueError("maximum_edges must be positive.")

    if not dfg:
        return (
            {},
            dict(start_activities),
            dict(end_activities),
        )

    ordered_transitions = sorted(
        dfg.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    visual_dfg = dict(
        ordered_transitions[:maximum_edges]
    )

    visual_activities = {
        activity
        for transition in visual_dfg
        for activity in transition
    }

    visual_start_activities = {
        activity: count
        for activity, count in start_activities.items()
        if activity in visual_activities
    }

    visual_end_activities = {
        activity: count
        for activity, count in end_activities.items()
        if activity in visual_activities
    }

    return (
        visual_dfg,
        visual_start_activities,
        visual_end_activities,
    )


def write_json(
    output_path: Path,
    content: dict[str, object],
) -> None:
    """Write JSON atomically."""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f"{output_path.name}.tmp"
    )

    try:
        temporary_path.write_text(
            json.dumps(
                content,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def run_process_discovery(
    cases_path: Path,
    events_path: Path,
    selected_category: str = DEFAULT_CATEGORY,
    top_variants: int = 10,
    top_transitions: int = 20,
    noise_threshold: float = 0.2,
    maximum_dfg_edges: int = 30,
    report_output: Path | None = None,
    dfg_output: Path | None = None,
    process_tree_output: Path | None = None,
    show_progress: bool = False,
) -> dict[str, object]:
    """Run variant analysis and focused PM4Py discovery."""

    if top_variants <= 0:
        raise ValueError("top_variants must be positive.")

    if top_transitions <= 0:
        raise ValueError("top_transitions must be positive.")

    if maximum_dfg_edges <= 0:
        raise ValueError(
            "maximum_dfg_edges must be positive."
        )

    if not 0.0 <= noise_threshold <= 1.0:
        raise ValueError(
            "noise_threshold must be between 0 and 1."
        )

    validate_input_file(cases_path)
    validate_input_file(events_path)

    if show_progress:
        print(
            "Stage 1/6: Reading case categories...",
            flush=True,
        )

    (
        case_categories,
        expected_category_case_counts,
    ) = read_case_categories(cases_path)

    if (
        selected_category
        not in expected_category_case_counts
    ):
        raise ValueError(
            "Unknown selected category: "
            f"{selected_category}"
        )

    if show_progress:
        print(
            "Stage 2/6: Profiling variants across all "
            "categories...",
            flush=True,
        )

    (
        variant_counts,
        observed_category_case_counts,
        selected_events,
        total_event_count,
    ) = profile_variants(
        events_path=events_path,
        case_categories=case_categories,
        expected_category_case_counts=(
            expected_category_case_counts
        ),
        selected_category=selected_category,
    )

    category_summaries = {
        category: summarise_variants(
            variants=variant_counts[category],
            top_n=top_variants,
        )
        for category in sorted(variant_counts)
    }

    if show_progress:
        print(
            "Stage 3/6: Preparing the selected PM4Py "
            "cohort...",
            flush=True,
        )

    dataframe = prepare_pm4py_dataframe(
        selected_events
    )

    if show_progress:
        print(
            "Stage 4/6: Discovering the directly-follows "
            "graph...",
            flush=True,
        )

    dfg, start_activities, end_activities = (
        pm4py.discover_dfg(dataframe)
    )

    if show_progress:
        print(
            "Stage 5/6: Discovering the process tree. "
            "This is the slowest stage...",
            flush=True,
        )

    process_tree = (
        pm4py.discover_process_tree_inductive(
            dataframe,
            noise_threshold=noise_threshold,
        )
    )

    (
        visual_dfg,
        visual_start_activities,
        visual_end_activities,
    ) = select_dfg_for_visualization(
        dfg=dfg,
        start_activities=start_activities,
        end_activities=end_activities,
        maximum_edges=maximum_dfg_edges,
    )

    visual_activity_count = len(
        {
            activity
            for transition in visual_dfg
            for activity in transition
        }
    )

    selected_case_count = (
        observed_category_case_counts[
            selected_category
        ]
    )
    selected_activity_count = int(
        dataframe["activity"].nunique()
    )

    report: dict[str, object] = {
        "inputs": {
            "cases": str(cases_path),
            "events": str(events_path),
        },
        "parameters": {
            "selected_category": selected_category,
            "top_variants": top_variants,
            "top_transitions": top_transitions,
            "noise_threshold": noise_threshold,
            "maximum_dfg_edges": maximum_dfg_edges,
        },
        "software": {
            "pm4py_version": pm4py.__version__,
            "pandas_version": pd.__version__,
        },
        "totals": {
            "case_count": len(case_categories),
            "event_count": total_event_count,
            "category_count": len(
                observed_category_case_counts
            ),
        },
        "categories": category_summaries,
        "selected_model": {
            "category": selected_category,
            "case_count": selected_case_count,
            "event_count": len(selected_events),
            "activity_count": selected_activity_count,
            "dfg": summarise_dfg(
                dfg=dfg,
                start_activities=start_activities,
                end_activities=end_activities,
                top_n=top_transitions,
            ),
            "dfg_visualization": {
                "displayed_transition_count": len(
                    visual_dfg
                ),
                "displayed_activity_count": (
                    visual_activity_count
                ),
                "displayed_start_activity_count": len(
                    visual_start_activities
                ),
                "displayed_end_activity_count": len(
                    visual_end_activities
                ),
            },
            "process_tree": str(process_tree),
        },
    }

    if show_progress:
        print(
            "Stage 6/6: Saving the report and "
            "visualizations...",
            flush=True,
        )

    if dfg_output is not None:
        dfg_output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        pm4py.save_vis_dfg(
            visual_dfg,
            visual_start_activities,
            visual_end_activities,
            str(dfg_output),
            max_num_edges=max(
                len(visual_dfg),
                1,
            ),
            rankdir="LR",
            graph_title=(
                f"ProcessIQ — {selected_category}"
            ),
        )

    if process_tree_output is not None:
        process_tree_output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        pm4py.save_vis_process_tree(
            process_tree,
            str(process_tree_output),
            rankdir="LR",
            graph_title=(
                "ProcessIQ — Inductive Process Model: "
                f"{selected_category}"
            ),
        )

    if report_output is not None:
        write_json(
            output_path=report_output,
            content=report,
        )

    return report


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Analyse process variants and discover "
            "a focused PM4Py model."
        )
    )

    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("data/processed/cases.csv"),
        help="Path to processed cases.",
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=Path("data/processed/events.csv"),
        help="Path to processed events.",
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_CATEGORY,
        help="Item category used for PM4Py discovery.",
    )
    parser.add_argument(
        "--top-variants",
        type=int,
        default=10,
        help="Number of variants reported per category.",
    )
    parser.add_argument(
        "--top-transitions",
        type=int,
        default=20,
        help="Number of DFG transitions reported.",
    )
    parser.add_argument(
        "--noise-threshold",
        type=float,
        default=0.2,
        help="Inductive Miner noise threshold.",
    )
    parser.add_argument(
        "--maximum-dfg-edges",
        type=int,
        default=30,
        help="Maximum number of edges in the DFG SVG.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path(
            "data/interim/process_discovery.json"
        ),
        help="Path for the generated JSON report.",
    )
    parser.add_argument(
        "--dfg-output",
        type=Path,
        default=Path(
            "reports/figures/"
            "dfg_invoice_after_gr.svg"
        ),
        help="Path for the DFG SVG.",
    )
    parser.add_argument(
        "--process-tree-output",
        type=Path,
        default=Path(
            "reports/figures/"
            "process_tree_invoice_after_gr.svg"
        ),
        help="Path for the process-tree SVG.",
    )

    return parser


def main() -> None:
    """Run process discovery from the command line."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    report = run_process_discovery(
        cases_path=arguments.cases,
        events_path=arguments.events,
        selected_category=arguments.category,
        top_variants=arguments.top_variants,
        top_transitions=arguments.top_transitions,
        noise_threshold=arguments.noise_threshold,
        maximum_dfg_edges=(
            arguments.maximum_dfg_edges
        ),
        report_output=arguments.report_output,
        dfg_output=arguments.dfg_output,
        process_tree_output=(
            arguments.process_tree_output
        ),
        show_progress=True,
    )

    totals = report["totals"]
    model = report["selected_model"]

    print("Process discovery completed.")
    print(
        f"Cases profiled: {totals['case_count']:,}"
    )
    print(
        f"Events profiled: {totals['event_count']:,}"
    )
    print(
        f"Categories profiled: "
        f"{totals['category_count']}"
    )
    print(f"Selected category: {model['category']}")
    print(
        f"Selected cases: {model['case_count']:,}"
    )
    print(
        f"Selected events: {model['event_count']:,}"
    )
    print(
        f"Selected activities: "
        f"{model['activity_count']}"
    )
    print(
        "Unique DFG transitions: "
        f"{model['dfg']['unique_transition_count']}"
    )
    print(
        f"Report written to: "
        f"{arguments.report_output}"
    )
    print(f"DFG written to: {arguments.dfg_output}")
    print(
        "Process tree written to: "
        f"{arguments.process_tree_output}"
    )


if __name__ == "__main__":
    main()
