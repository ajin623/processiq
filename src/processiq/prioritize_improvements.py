"""Prioritise evidence-based ProcessIQ improvement opportunities.

This module combines the bottleneck and conformance reports created in earlier
analysis phases. It produces a transparent decision-support ranking rather
than claiming that statistical associations prove root causes or savings.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BOTTLENECK_REPORT = Path("data/interim/bottleneck_report.json")
DEFAULT_CONFORMANCE_REPORT = Path("data/interim/conformance_report.json")
DEFAULT_PRIORITY_OUTPUT = Path("data/processed/improvement_priorities.csv")
DEFAULT_REPORT_OUTPUT = Path("data/interim/improvement_priorities.json")

SCORE_WEIGHTS = {
    "reach": 0.25,
    "time_impact": 0.25,
    "evidence_strength": 0.25,
    "actionability": 0.15,
    "confidence": 0.10,
}

CSV_HEADERS = [
    "rank",
    "priority_band",
    "overall_score",
    "opportunity_id",
    "title",
    "evidence_type",
    "affected_cases",
    "denominator_cases",
    "reach_percentage",
    "representative_delay_metric",
    "representative_delay_days",
    "p90_days",
    "observed_wait_share_percentage",
    "rank_biserial_effect",
    "effect_magnitude",
    "statistically_significant",
    "reach_score",
    "time_impact_score",
    "evidence_strength_score",
    "actionability_score",
    "confidence_score",
    "recommended_next_analysis",
    "decision_caution",
]

TRANSITION_OPPORTUNITIES = [
    {
        "opportunity_id": "invoice_receipt_to_clearing",
        "title": "Investigate invoice-receipt-to-clearing delay",
        "from_activity": "Record Invoice Receipt",
        "to_activity": "Clear Invoice",
        "actionability_score": 2,
        "confidence_score": 3,
        "recommended_next_analysis": (
            "Enrich cases with contractual due dates and payment terms, then "
            "separate expected payment waiting from avoidable clearing delay."
        ),
        "decision_caution": (
            "Long calendar time may reflect agreed payment terms. Do not treat "
            "the complete observed wait as operational waste."
        ),
    },
    {
        "opportunity_id": "goods_receipt_to_invoice_receipt",
        "title": "Investigate goods-receipt-to-invoice-receipt delay",
        "from_activity": "Record Goods Receipt",
        "to_activity": "Record Invoice Receipt",
        "actionability_score": 3,
        "confidence_score": 3,
        "recommended_next_analysis": (
            "Segment the transition by supplier, purchasing organisation, and "
            "item category to locate slow invoice-receipt posting patterns."
        ),
        "decision_caution": (
            "This is a directly-follows transition. Cases containing an "
            "intermediate recorded event are not represented by this measure."
        ),
    },
    {
        "opportunity_id": "vendor_invoice_to_invoice_receipt",
        "title": "Investigate vendor-invoice-to-formal-receipt delay",
        "from_activity": "Vendor creates invoice",
        "to_activity": "Record Invoice Receipt",
        "actionability_score": 4,
        "confidence_score": 4,
        "recommended_next_analysis": (
            "Compare posting delays by supplier and processing group, and verify "
            "whether the two timestamps represent a controllable handoff."
        ),
        "decision_caution": (
            "The vendor-creation timestamp and formal receipt timestamp may come "
            "from different systems with different recording semantics."
        ),
    },
]

MARKER_OPPORTUNITIES = [
    {
        "opportunity_id": "payment_block_intervention",
        "title": "Investigate payment-block prevention and resolution",
        "marker": "Payment-block intervention",
        "actionability_score": 4,
        "confidence_score": 3,
        "recommended_next_analysis": (
            "Segment blocked cases by supplier and purchasing attributes, then "
            "measure block-to-release and release-to-clearing time separately."
        ),
        "decision_caution": (
            "The marker is associated with longer duration but does not prove "
            "that the payment block caused the entire difference."
        ),
    },
    {
        "opportunity_id": "multiple_invoice_receipts",
        "title": "Investigate repeated formal invoice receipts",
        "marker": "Multiple invoice receipts",
        "actionability_score": 3,
        "confidence_score": 3,
        "recommended_next_analysis": (
            "Classify repeated receipts as partial invoices, corrections, "
            "reversals, or potential duplicates before proposing controls."
        ),
        "decision_caution": (
            "Repeated invoice receipts are not automatically duplicates or "
            "errors; legitimate partial and corrective postings may exist."
        ),
    },
]


def validate_input_file(path: Path) -> None:
    """Reject a missing or non-file report path."""

    if not path.exists():
        raise FileNotFoundError(f"Input report does not exist: {path}")

    if not path.is_file():
        raise ValueError(f"Input report is not a file: {path}")


def resolved_path(path: Path) -> Path:
    """Return a comparable absolute path without requiring it to exist."""

    return path.expanduser().resolve(strict=False)


def validate_distinct_paths(
    input_paths: list[Path],
    output_paths: list[Path],
) -> None:
    """Ensure generated outputs cannot overwrite inputs or each other."""

    resolved_inputs = [resolved_path(path) for path in input_paths]
    resolved_outputs = [resolved_path(path) for path in output_paths]

    if len(set(resolved_outputs)) != len(resolved_outputs):
        raise ValueError("Output paths must be different from each other.")

    for output_path in resolved_outputs:
        if output_path in resolved_inputs:
            raise ValueError(
                "An output path must not overwrite an input report: "
                f"{output_path}"
            )


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON report and require an object at its root."""

    validate_input_file(path)

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error

    if not isinstance(content, dict):
        raise ValueError(f"JSON report must contain an object: {path}")

    return content


def require_mapping(
    value: Any,
    context: str,
) -> dict[str, Any]:
    """Require a dictionary-like report section."""

    if not isinstance(value, dict):
        raise ValueError(f"Expected an object for {context}.")

    return value


def require_list(
    value: Any,
    context: str,
) -> list[Any]:
    """Require a list-like report section."""

    if not isinstance(value, list):
        raise ValueError(f"Expected a list for {context}.")

    return value


def require_string(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> str:
    """Read a required non-empty string from a report section."""

    value = mapping.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected a non-empty string at {context}.{key}.")

    return value


def require_number(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> float:
    """Read a required finite numeric value from a report section."""

    value = mapping.get(key)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Expected a number at {context}.{key}.")

    numeric_value = float(value)

    if not math.isfinite(numeric_value):
        raise ValueError(f"Expected a finite number at {context}.{key}.")

    return numeric_value


def require_non_negative_integer(
    mapping: dict[str, Any],
    key: str,
    context: str,
) -> int:
    """Read a required non-negative integer from a report section."""

    value = mapping.get(key)

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            f"Expected a non-negative integer at {context}.{key}."
        )

    return value


def find_transition(
    transitions: list[Any],
    from_activity: str,
    to_activity: str,
) -> dict[str, Any]:
    """Find one exact transition in the focused transition results."""

    for index, candidate in enumerate(transitions):
        transition = require_mapping(
            candidate,
            f"transition_analysis.focused_transitions[{index}]",
        )

        if (
            transition.get("from_activity") == from_activity
            and transition.get("to_activity") == to_activity
        ):
            return transition

    raise ValueError(
        "Required focused transition was not found: "
        f"{from_activity} -> {to_activity}"
    )


def find_marker(
    markers: list[Any],
    marker_name: str,
) -> dict[str, Any]:
    """Find one exact marker comparison in the bottleneck report."""

    for index, candidate in enumerate(markers):
        marker = require_mapping(
            candidate,
            f"marker_comparisons[{index}]",
        )

        if marker.get("marker") == marker_name:
            return marker

    raise ValueError(f"Required marker comparison was not found: {marker_name}")


def reach_score(reach_percentage: float) -> int:
    """Convert case reach into a transparent one-to-five score."""

    if reach_percentage >= 40.0:
        return 5
    if reach_percentage >= 25.0:
        return 4
    if reach_percentage >= 10.0:
        return 3
    if reach_percentage >= 5.0:
        return 2
    return 1


def time_impact_score(delay_days: float) -> int:
    """Convert a representative delay into a one-to-five score."""

    if delay_days >= 60.0:
        return 5
    if delay_days >= 30.0:
        return 4
    if delay_days >= 15.0:
        return 3
    if delay_days >= 5.0:
        return 2
    return 1


def transition_evidence_score(wait_share: float) -> int:
    """Score transition evidence using its share of observed waiting time."""

    if wait_share >= 20.0:
        return 5
    if wait_share >= 15.0:
        return 4
    if wait_share >= 10.0:
        return 3
    if wait_share >= 5.0:
        return 2
    return 1


def marker_evidence_score(
    effect_magnitude: str,
    statistically_significant: bool,
) -> int:
    """Score marker evidence without confusing association with causation."""

    magnitude_scores = {
        "large": 5,
        "medium": 4,
        "small": 3,
        "negligible": 2,
    }

    score = magnitude_scores.get(effect_magnitude.lower())

    if score is None:
        raise ValueError(
            "Unsupported marker effect magnitude: "
            f"{effect_magnitude}"
        )

    if not statistically_significant:
        return max(1, score - 1)

    return score


def calculate_overall_score(component_scores: dict[str, int]) -> float:
    """Calculate the weighted score on a zero-to-100 scale."""

    if set(component_scores) != set(SCORE_WEIGHTS):
        raise ValueError("Component scores do not match the scoring framework.")

    weighted_score = 0.0

    for component, weight in SCORE_WEIGHTS.items():
        score = component_scores[component]

        if score < 1 or score > 5:
            raise ValueError(
                f"{component} score must be between 1 and 5."
            )

        weighted_score += score * weight

    return round((weighted_score / 5.0) * 100.0, 2)


def priority_band(overall_score: float) -> str:
    """Assign a relative priority band within this analysis."""

    if overall_score >= 75.0:
        return "P1"
    if overall_score >= 65.0:
        return "P2"
    return "P3"


def build_transition_opportunity(
    definition: dict[str, Any],
    transition: dict[str, Any],
    denominator_cases: int,
) -> dict[str, Any]:
    """Build one scored opportunity from directly-follows waiting time."""

    context = (
        "transition "
        f"{definition['from_activity']} -> {definition['to_activity']}"
    )
    affected_cases = require_non_negative_integer(
        transition,
        "affected_cases",
        context,
    )
    median_wait_hours = require_number(
        transition,
        "median_wait_hours",
        context,
    )
    p90_wait_hours = require_number(
        transition,
        "p90_wait_hours",
        context,
    )
    wait_share = require_number(
        transition,
        "share_of_observed_wait",
        context,
    )

    reach_percentage = round(
        affected_cases / denominator_cases * 100.0,
        2,
    )
    median_wait_days = round(median_wait_hours / 24.0, 2)
    p90_wait_days = round(p90_wait_hours / 24.0, 2)

    component_scores = {
        "reach": reach_score(reach_percentage),
        "time_impact": time_impact_score(median_wait_days),
        "evidence_strength": transition_evidence_score(wait_share),
        "actionability": int(definition["actionability_score"]),
        "confidence": int(definition["confidence_score"]),
    }
    overall_score = calculate_overall_score(component_scores)

    return {
        "opportunity_id": definition["opportunity_id"],
        "title": definition["title"],
        "evidence_type": "directly_follows_waiting_time",
        "affected_cases": affected_cases,
        "denominator_cases": denominator_cases,
        "reach_percentage": reach_percentage,
        "representative_delay_metric": "median_wait_days",
        "representative_delay_days": median_wait_days,
        "p90_days": p90_wait_days,
        "observed_wait_share_percentage": round(wait_share, 2),
        "rank_biserial_effect": None,
        "effect_magnitude": None,
        "statistically_significant": None,
        "source_evidence": {
            "from_activity": require_string(
                transition,
                "from_activity",
                context,
            ),
            "to_activity": require_string(
                transition,
                "to_activity",
                context,
            ),
            "transition_count": require_non_negative_integer(
                transition,
                "transition_count",
                context,
            ),
            "total_wait_days": round(
                require_number(
                    transition,
                    "total_wait_days",
                    context,
                ),
                2,
            ),
            "zero_time_percentage": round(
                require_number(
                    transition,
                    "zero_time_percentage",
                    context,
                ),
                2,
            ),
        },
        "component_scores": component_scores,
        "overall_score": overall_score,
        "priority_band": priority_band(overall_score),
        "recommended_next_analysis": definition["recommended_next_analysis"],
        "decision_caution": definition["decision_caution"],
    }


def build_marker_opportunity(
    definition: dict[str, Any],
    marker: dict[str, Any],
    denominator_cases: int,
) -> dict[str, Any]:
    """Build one scored opportunity from a case-level marker association."""

    context = f"marker comparison {definition['marker']}"
    affected_cases = require_non_negative_integer(
        marker,
        "cases_with_marker",
        context,
    )
    median_difference_days = require_number(
        marker,
        "median_difference_days",
        context,
    )
    rank_biserial_effect = require_number(
        marker,
        "rank_biserial_effect",
        context,
    )
    effect_magnitude = require_string(
        marker,
        "effect_magnitude",
        context,
    )
    statistically_significant = marker.get("statistically_significant")

    if not isinstance(statistically_significant, bool):
        raise ValueError(
            "Expected a boolean at "
            f"{context}.statistically_significant."
        )

    if median_difference_days <= 0:
        raise ValueError(
            f"Expected a positive duration association for {definition['marker']}."
        )

    reach_percentage = round(
        affected_cases / denominator_cases * 100.0,
        2,
    )
    component_scores = {
        "reach": reach_score(reach_percentage),
        "time_impact": time_impact_score(median_difference_days),
        "evidence_strength": marker_evidence_score(
            effect_magnitude,
            statistically_significant,
        ),
        "actionability": int(definition["actionability_score"]),
        "confidence": int(definition["confidence_score"]),
    }
    overall_score = calculate_overall_score(component_scores)

    return {
        "opportunity_id": definition["opportunity_id"],
        "title": definition["title"],
        "evidence_type": "case_level_marker_association",
        "affected_cases": affected_cases,
        "denominator_cases": denominator_cases,
        "reach_percentage": reach_percentage,
        "representative_delay_metric": "median_difference_days",
        "representative_delay_days": round(median_difference_days, 2),
        "p90_days": round(
            require_number(marker, "p90_days_with", context),
            2,
        ),
        "observed_wait_share_percentage": None,
        "rank_biserial_effect": round(rank_biserial_effect, 4),
        "effect_magnitude": effect_magnitude,
        "statistically_significant": statistically_significant,
        "source_evidence": {
            "marker": require_string(marker, "marker", context),
            "median_days_with": round(
                require_number(marker, "median_days_with", context),
                2,
            ),
            "median_days_without": round(
                require_number(marker, "median_days_without", context),
                2,
            ),
            "adjusted_p_value": require_number(
                marker,
                "adjusted_p_value",
                context,
            ),
        },
        "component_scores": component_scores,
        "overall_score": overall_score,
        "priority_band": priority_band(overall_score),
        "recommended_next_analysis": definition["recommended_next_analysis"],
        "decision_caution": definition["decision_caution"],
    }


def build_control_actions(
    conformance_report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep mandatory reviews and evidence gaps outside the impact ranking."""

    scope = require_mapping(
        conformance_report.get("scope"),
        "conformance_report.scope",
    )
    conformance = require_mapping(
        conformance_report.get("conformance"),
        "conformance_report.conformance",
    )
    status_counts = require_mapping(
        conformance.get("status_counts"),
        "conformance_report.conformance.status_counts",
    )
    status_percentages = require_mapping(
        conformance.get("status_percentages"),
        "conformance_report.conformance.status_percentages",
    )
    review_reasons = require_mapping(
        conformance.get("review_reason_counts"),
        "conformance_report.conformance.review_reason_counts",
    )
    selected_cases = require_non_negative_integer(
        scope,
        "selected_case_count",
        "conformance_report.scope",
    )

    review_required = require_non_negative_integer(
        status_counts,
        "review_required",
        "conformance_report.conformance.status_counts",
    )
    incomplete_evidence = require_non_negative_integer(
        status_counts,
        "incomplete_evidence",
        "conformance_report.conformance.status_counts",
    )

    return [
        {
            "action_id": "manual_ordering_exception_review",
            "action_type": "mandatory_control_review",
            "affected_cases": review_required,
            "denominator_cases": selected_cases,
            "affected_percentage": round(
                require_number(
                    status_percentages,
                    "review_required",
                    "conformance_report.conformance.status_percentages",
                ),
                2,
            ),
            "reason_counts": {
                "clearing_before_invoice_receipt": (
                    require_non_negative_integer(
                        review_reasons,
                        "clearing_before_invoice_receipt",
                        (
                            "conformance_report.conformance."
                            "review_reason_counts"
                        ),
                    )
                ),
                "clearing_without_invoice_receipt": (
                    require_non_negative_integer(
                        review_reasons,
                        "clearing_without_invoice_receipt",
                        (
                            "conformance_report.conformance."
                            "review_reason_counts"
                        ),
                    )
                ),
            },
            "recommended_action": (
                "Review the recorded event histories and source-system evidence "
                "for all flagged cases before drawing a compliance conclusion."
            ),
            "why_not_ranked": (
                "Control exceptions require review even when case volume is too "
                "small to score highly in an operational impact ranking."
            ),
            "decision_caution": (
                "A review flag is not proof of fraud, control failure, or policy "
                "breach."
            ),
        },
        {
            "action_id": "separate_incomplete_case_evidence",
            "action_type": "data_and_scope_control",
            "affected_cases": incomplete_evidence,
            "denominator_cases": selected_cases,
            "affected_percentage": round(
                require_number(
                    status_percentages,
                    "incomplete_evidence",
                    "conformance_report.conformance.status_percentages",
                ),
                2,
            ),
            "recommended_action": (
                "Separate open, observation-truncated, and genuinely missing-event "
                "cases before reporting final conformance or completion KPIs."
            ),
            "why_not_ranked": (
                "Incomplete evidence is a scope and data-quality issue, not a "
                "measured operational delay or confirmed process violation."
            ),
            "decision_caution": (
                "Do not label incomplete cases as non-conforming solely because a "
                "clearing event is absent."
            ),
        },
    ]


def write_json(
    output_path: Path,
    content: dict[str, Any],
) -> None:
    """Write a readable UTF-8 JSON artifact."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(content, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def csv_value(value: Any) -> Any:
    """Represent missing values as empty CSV fields."""

    if value is None:
        return ""

    return value


def write_priorities_csv(
    output_path: Path,
    opportunities: list[dict[str, Any]],
) -> None:
    """Write the ranked opportunities in a spreadsheet-friendly format."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=CSV_HEADERS)
        writer.writeheader()

        for opportunity in opportunities:
            component_scores = require_mapping(
                opportunity.get("component_scores"),
                f"opportunity {opportunity.get('opportunity_id')}.component_scores",
            )
            row = {
                "rank": opportunity["rank"],
                "priority_band": opportunity["priority_band"],
                "overall_score": opportunity["overall_score"],
                "opportunity_id": opportunity["opportunity_id"],
                "title": opportunity["title"],
                "evidence_type": opportunity["evidence_type"],
                "affected_cases": opportunity["affected_cases"],
                "denominator_cases": opportunity["denominator_cases"],
                "reach_percentage": opportunity["reach_percentage"],
                "representative_delay_metric": opportunity[
                    "representative_delay_metric"
                ],
                "representative_delay_days": opportunity[
                    "representative_delay_days"
                ],
                "p90_days": csv_value(opportunity["p90_days"]),
                "observed_wait_share_percentage": csv_value(
                    opportunity["observed_wait_share_percentage"]
                ),
                "rank_biserial_effect": csv_value(
                    opportunity["rank_biserial_effect"]
                ),
                "effect_magnitude": csv_value(
                    opportunity["effect_magnitude"]
                ),
                "statistically_significant": csv_value(
                    opportunity["statistically_significant"]
                ),
                "reach_score": component_scores["reach"],
                "time_impact_score": component_scores["time_impact"],
                "evidence_strength_score": component_scores[
                    "evidence_strength"
                ],
                "actionability_score": component_scores["actionability"],
                "confidence_score": component_scores["confidence"],
                "recommended_next_analysis": opportunity[
                    "recommended_next_analysis"
                ],
                "decision_caution": opportunity["decision_caution"],
            }
            writer.writerow(row)


def run_improvement_prioritization(
    bottleneck_report_path: Path,
    conformance_report_path: Path,
    priority_output_path: Path,
    report_output_path: Path,
) -> dict[str, Any]:
    """Combine existing evidence and write ranked decision-support outputs."""

    validate_distinct_paths(
        [bottleneck_report_path, conformance_report_path],
        [priority_output_path, report_output_path],
    )

    bottleneck_report = read_json_object(bottleneck_report_path)
    conformance_report = read_json_object(conformance_report_path)

    bottleneck_scope = require_mapping(
        bottleneck_report.get("scope"),
        "bottleneck_report.scope",
    )
    conformance_scope = require_mapping(
        conformance_report.get("scope"),
        "conformance_report.scope",
    )
    bottleneck_category = require_string(
        bottleneck_scope,
        "selected_category",
        "bottleneck_report.scope",
    )
    conformance_category = require_string(
        conformance_scope,
        "item_category",
        "conformance_report.scope",
    )

    if bottleneck_category != conformance_category:
        raise ValueError(
            "Report categories do not match: "
            f"{bottleneck_category!r} != {conformance_category!r}"
        )

    eligible_cases = require_non_negative_integer(
        bottleneck_scope,
        "duration_eligible_selected_cases",
        "bottleneck_report.scope",
    )
    total_selected_cases = require_non_negative_integer(
        bottleneck_scope,
        "total_selected_cases",
        "bottleneck_report.scope",
    )

    if eligible_cases <= 0:
        raise ValueError("The bottleneck report contains no eligible cases.")

    transition_analysis = require_mapping(
        bottleneck_report.get("transition_analysis"),
        "bottleneck_report.transition_analysis",
    )
    focused_transitions = require_list(
        transition_analysis.get("focused_transitions"),
        "bottleneck_report.transition_analysis.focused_transitions",
    )
    marker_comparisons = require_list(
        bottleneck_report.get("marker_comparisons"),
        "bottleneck_report.marker_comparisons",
    )

    opportunities: list[dict[str, Any]] = []

    for definition in TRANSITION_OPPORTUNITIES:
        transition = find_transition(
            focused_transitions,
            definition["from_activity"],
            definition["to_activity"],
        )
        opportunities.append(
            build_transition_opportunity(
                definition,
                transition,
                eligible_cases,
            )
        )

    for definition in MARKER_OPPORTUNITIES:
        marker = find_marker(
            marker_comparisons,
            definition["marker"],
        )
        opportunities.append(
            build_marker_opportunity(
                definition,
                marker,
                eligible_cases,
            )
        )

    opportunities.sort(
        key=lambda opportunity: (
            -float(opportunity["overall_score"]),
            str(opportunity["opportunity_id"]),
        )
    )

    for rank, opportunity in enumerate(opportunities, start=1):
        opportunity["rank"] = rank

    limitations = require_list(
        bottleneck_report.get("limitations"),
        "bottleneck_report.limitations",
    )

    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "item_category": bottleneck_category,
            "total_selected_cases": total_selected_cases,
            "duration_eligible_cases": eligible_cases,
            "duration_excluded_cases": (
                require_non_negative_integer(
                    bottleneck_scope,
                    "duration_excluded_selected_cases",
                    "bottleneck_report.scope",
                )
            ),
            "ranked_operational_opportunities": len(opportunities),
        },
        "methodology": {
            "purpose": (
                "Transparent relative prioritisation for further analysis; not a "
                "causal model, financial forecast, or automated decision."
            ),
            "score_range": "0 to 100",
            "component_range": "1 to 5",
            "weights": SCORE_WEIGHTS,
            "priority_bands": {
                "P1": "overall score greater than or equal to 75",
                "P2": "overall score from 65 to less than 75",
                "P3": "overall score below 65",
            },
            "reach_thresholds_percentage": {
                "5": "40 or more",
                "4": "25 to less than 40",
                "3": "10 to less than 25",
                "2": "5 to less than 10",
                "1": "less than 5",
            },
            "time_impact_thresholds_days": {
                "5": "60 or more",
                "4": "30 to less than 60",
                "3": "15 to less than 30",
                "2": "5 to less than 15",
                "1": "less than 5",
            },
            "analyst_judgment": (
                "Actionability and confidence scores are explicit analyst "
                "judgments. They must be revisited with process owners."
            ),
        },
        "ranked_operational_opportunities": opportunities,
        "control_and_data_actions": build_control_actions(
            conformance_report
        ),
        "limitations": [
            *limitations,
            (
                "The ranking compares selected opportunities within one item "
                "category; it is not a company-wide investment ranking."
            ),
            (
                "No monetary benefit is estimated because cost, capacity, due-date, "
                "and intervention-cost data are unavailable."
            ),
            (
                "Statistical association and directly-follows waiting time do not "
                "establish root cause."
            ),
        ],
        "source_reports": {
            "bottleneck_report": str(bottleneck_report_path),
            "conformance_report": str(conformance_report_path),
            "bottleneck_generated_at_utc": bottleneck_report.get(
                "generated_at_utc"
            ),
            "conformance_generated_at_utc": conformance_report.get(
                "generated_at_utc"
            ),
        },
    }

    write_priorities_csv(priority_output_path, opportunities)
    write_json(report_output_path, report)

    return report


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        description=(
            "Prioritise ProcessIQ improvement opportunities using existing "
            "bottleneck and conformance evidence."
        )
    )
    parser.add_argument(
        "--bottleneck-report",
        type=Path,
        default=DEFAULT_BOTTLENECK_REPORT,
        help="Path to the bottleneck analysis JSON report.",
    )
    parser.add_argument(
        "--conformance-report",
        type=Path,
        default=DEFAULT_CONFORMANCE_REPORT,
        help="Path to the conformance analysis JSON report.",
    )
    parser.add_argument(
        "--priority-output",
        type=Path,
        default=DEFAULT_PRIORITY_OUTPUT,
        help="Path for the ranked improvement-priority CSV.",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_REPORT_OUTPUT,
        help="Path for the complete improvement-priority JSON report.",
    )
    return parser


def main() -> None:
    """Run the command-line workflow."""

    parser = build_argument_parser()
    arguments = parser.parse_args()

    report = run_improvement_prioritization(
        bottleneck_report_path=arguments.bottleneck_report,
        conformance_report_path=arguments.conformance_report,
        priority_output_path=arguments.priority_output,
        report_output_path=arguments.report_output,
    )

    scope = require_mapping(report.get("scope"), "report.scope")
    opportunities = require_list(
        report.get("ranked_operational_opportunities"),
        "report.ranked_operational_opportunities",
    )

    print("Improvement prioritisation completed.")
    print(f"Category: {scope['item_category']}")
    print(f"Eligible cases: {scope['duration_eligible_cases']:,}")
    print(f"Ranked opportunities: {len(opportunities)}")

    for opportunity in opportunities:
        print(
            f"  {opportunity['rank']}. {opportunity['title']} "
            f"| Score: {opportunity['overall_score']:.2f} "
            f"| Band: {opportunity['priority_band']}"
        )

    print(f"Priority CSV: {arguments.priority_output}")
    print(f"Priority report: {arguments.report_output}")


if __name__ == "__main__":
    main()
