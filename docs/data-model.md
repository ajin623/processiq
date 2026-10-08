# ProcessIQ Data Model and Data Dictionary

## 1. Purpose

This document records the data design and its implemented form as of 8 October 2026, aligned with code commit `5e191f1`. The original design defined grains, identifiers, and source mappings before ingestion. The current Python pipeline writes CSVs; the optional PostgreSQL scripts load a subset of those tables into constrained database tables.

### Implemented outputs

Paths below are relative to `data/processed/` and are generated locally.

| File | Grain | Key / use |
|---|---|---|
| `cases.csv` | One purchase-item case | `case_id`; case attributes and spend-completeness flag |
| `events.csv` | One source event | `case_id` + `event_position`; activity, time, resource, and quality flags |
| `case_timing.csv` | One case | `case_id`; observed duration and eligibility reasons |
| `case_conformance.csv` | One selected-category case | `case_id`; rule outcomes, review reasons, and diagnostics |
| `transition_bottlenecks.csv` | One activity pair in the eligible selected cohort | `from_activity` + `to_activity`; counts and wait statistics |
| `marker_duration_comparison.csv` | One diagnostic marker | `marker`; group sizes, durations, p-values, and effects |
| `improvement_priorities.csv` | One configured investigation | `opportunity_id`; ranking, evidence, and cautions |
| `dashboard_cases.csv` | One case across all categories | `case_id`; 48 columns combining case, timing, and available conformance |
| `dashboard_kpis.csv` | One metric record | Section, metric key, category, value, unit, and interpretation; 45 rows in the reference build |

`dashboard_cases` has a one-to-many relationship to `events` on `case_id`, with filtering from cases to events if the event table is imported. The dashboard builder leaves the existing event CSV separate. Aggregate transition, marker, and priority tables are scoped summaries, not event facts; they must not be joined to cases in a way that multiplies counts or implies unsupported slicer recalculation.

Use CSV headers and `data/interim/dashboard_manifest.json` for the current generated schema. [Methodology](methodology.md) defines calculation rules; [reproducibility](reproducibility.md) describes Power Query typing and the optional database workflow.

## 2. Business Grain

The grain describes what one row represents.

### Purchase document

A purchase document represents an overall purchasing record.

One purchase document can contain multiple purchase items.

The purchase document alone is not the ProcessIQ case identifier.

### Purchase item

A purchase item represents one line within a purchase document.

The source dataset combines the purchase-document identifier and item identifier to create a case identifier.

### Case or trace

One case represents one purchase-document item.

The XES trace attribute `concept:name` is the source case identifier.

Expected example:

`2000000000_00001`

### Event

One event represents one recorded activity performed for one case at one timestamp.

The same activity may occur more than once within a case.

### Transition

One transition represents movement from one recorded event to the next recorded event within the same case.

### Case metric

One case-metric row summarises the recorded history of one case; it does not establish process completion.

## 3. Data Layers

ProcessIQ uses source, extracted, and processed data layers, with an optional PostgreSQL layer.

### Layer 1: Immutable source

File:

`data/raw/BPI_Challenge_2019.xes`

Purpose:

- Preserve the original downloaded event log.
- Provide the source for reproducible ingestion.
- Never edit the file manually.
- Never upload the file to GitHub.

### Layer 2: Interim extracted data

Implemented files:

- `data/interim/cases_raw.csv`
- `data/interim/events_raw.csv`

Purpose:

- Convert nested XES data into flat rows.
- Preserve source values.
- Use standardised column names.
- Retain source event order.
- Support inspection before database loading.

These files will remain outside Git.

### Layer 3: Processed CSVs and Optional PostgreSQL Tables

The pipeline writes processed `cases.csv`, `events.csv`, and `case_timing.csv`. [01_schema.sql](../sql/01_schema.sql) and [02_load.sql](../sql/02_load.sql) provide the corresponding PostgreSQL tables:

- `cases`
- `events`
- `case_timing`

Purpose:

- Apply explicit data types.
- Enforce keys and important constraints.
- Support reliable SQL analysis.
- Separate case-level attributes from event-level attributes.

### Layer 4: Derived analytical tables or views

The Python analytical outputs are listed in section 1. [03_analytical_layer.sql](../sql/03_analytical_layer.sql) implements the PostgreSQL `case_overview` and `transitions` views, indexes, and reconciliation queries.

The initial design also proposed database structures named `case_metrics` and separate process-variant, data-quality, and management-KPI views. Those names should not be assumed to exist: the implemented equivalents are the documented CSV/JSON outputs and two SQL views.

## 4. Event-Ordering Rule

Events must remain in their original XES trace order.

Each event will receive an `event_position`:

- The first event in a trace receives position 1.
- The second receives position 2.
- Positions continue sequentially within the same case.

Timestamp alone cannot determine event order because multiple activities can share the same timestamp.

For duration calculations:

1. Source event order defines sequence.
2. Timestamps define elapsed time.
3. Equal timestamps produce zero elapsed time.
4. A later source event with an earlier timestamp produces a chronology flag.
5. Tied timestamps must not be reordered alphabetically.

## 5. Cases Table

### Grain

One row per purchase-item case.

### Primary key

`case_id`

### Data dictionary

| Column | Source XES key | PostgreSQL type | Required | Meaning |
|---|---|---|---|---|
| `case_id` | `concept:name` | `text` | Yes | Purchase-document and item case identifier |
| `purchasing_document_id` | `Purchasing Document` | `text` | Yes | Anonymised purchase-document identifier |
| `item_id` | `Item` | `text` | Yes | Item identifier within the purchase document |
| `item_type` | `Item Type` | `text` | Review | Source item type |
| `gr_based_invoice_verification` | `GR-Based Inv. Verif.` | `boolean` | Yes | Whether goods-receipt-based invoice verification applies |
| `goods_receipt_required` | `Goods Receipt` | `boolean` | Yes | Whether a goods receipt is required |
| `source_system_id` | `Source` | `text` | Review | Anonymised source-system identifier |
| `purchasing_document_category` | `Purch. Doc. Category name` | `text` | Review | Purchase-document category |
| `company_id` | `Company` | `text` | Review | Anonymised company or subsidiary identifier |
| `spend_classification` | `Spend classification text` | `text` | Review | High-level spend classification |
| `spend_area` | `Spend area text` | `text` | Review | Spend area |
| `sub_spend_area` | `Sub spend area text` | `text` | Review | Detailed spend area |
| `vendor_id` | `Vendor` | `text` | Review | Anonymised vendor identifier |
| `vendor_name` | `Name` | `text` | Review | Anonymised vendor name |
| `document_type` | `Document Type` | `text` | Review | Source document type |
| `item_category` | `Item Category` | `text` | Yes | Matching category used to interpret expected process behaviour |
| `spend_data_complete` | Derived | `boolean` | Yes | All three spend classification fields are recorded |

`Review` marks source fields whose business meaning or missing-value coverage requires interpretation. They are nullable in the implemented PostgreSQL schema; see `01_schema.sql` for enforced constraints.

Identifiers remain text. Converting them to numbers could remove leading zeroes or create false arithmetic meaning.

## 6. Events Table

### Grain

One row per recorded event occurrence.

### Primary key

The combined key:

- `case_id`
- `event_position`

### Data dictionary

| Column | Source XES key | PostgreSQL type | Required | Meaning |
|---|---|---|---|---|
| `case_id` | Parent trace `concept:name` | `text` | Yes | Case to which the event belongs |
| `event_position` | Derived from source order | `integer` | Yes | Event's original position inside its trace |
| `activity` | `concept:name` | `text` | Yes | Recorded business activity |
| `event_timestamp` | `time:timestamp` | `timestamp with time zone` | Yes | Event timestamp converted to a timezone-aware value |
| `resource_id` | `org:resource` | `text` | No | Recorded human, batch, or missing resource |
| `user_id` | `User` | `text` | No | Source user value |
| `cumulative_net_worth` | `Cumulative net worth (EUR)` | `numeric` | Yes | Anonymised cumulative monetary value; business interpretation requires care |
| `resource_recorded` | Derived | `boolean` | Yes | Resource value remains after missing-marker normalisation |
| `timestamp_in_analysis_window` | Derived | `boolean` | Yes | Timestamp falls in the implemented 2018–2019 window |

The source labels the monetary field as EUR, but the official documentation states that monetary values were anonymised through a linear transformation.

ProcessIQ preserves and validates this field. The current improvement ranking does not use it to estimate financial savings.

## 7. Implemented PostgreSQL Transitions View

### Grain

One row per consecutive pair of events within a case.

### Columns

| Column | Type | Meaning |
|---|---|---|
| `case_id` | `text` | Parent case |
| `from_event_position` | `integer` | Starting event position |
| `to_event_position` | `integer` | Following event position |
| `from_activity` | `text` | Starting activity |
| `to_activity` | `text` | Following activity |
| `from_timestamp` | `timestamp with time zone` | Starting event time |
| `to_timestamp` | `timestamp with time zone` | Following event time |
| `elapsed_interval` | `interval` | Recorded timestamp difference |
| `elapsed_seconds` | `numeric` | Recorded time difference between the two events |
| `same_timestamp` | `boolean` | Whether both timestamps are equal |
| `negative_elapsed_time` | `boolean` | Whether source order moves backward in time |
| `case_duration_eligible` | `boolean` | Eligibility of the parent case for duration analysis |

`elapsed_seconds` is a recorded time difference, not measured working time. The bottleneck report describes eligible elapsed intervals as observed waiting time and documents that activity between events may be unrecorded. The SQL view retains ineligible cases with a flag; duration queries must filter it explicitly. This row-level view differs from the aggregated activity-pair CSV.

## 8. Implemented Case Timing Structure

### Grain

One row per case.

### Columns

| Column | Type | Meaning |
|---|---|---|
| `case_id` | `text` | Case identifier |
| `first_event_timestamp` | `timestamp with time zone` | Timestamp of the first source-ordered event |
| `last_event_timestamp` | `timestamp with time zone` | Timestamp of the last source-ordered event |
| `cycle_time_seconds` | `numeric` | Difference between the selected first and last timestamps |
| `cycle_time_days` | `numeric` | Recorded span in seconds divided by 86,400 |
| `event_count` | `integer` | Number of events in the case |
| `outside_analysis_window_event_count` | `integer` | Events outside 2018–2019 |
| `has_negative_timestamp` | `boolean` | Whether consecutive timestamps move backward |
| `exceeds_365_days` | `boolean` | Recorded span is strictly greater than 365 days |
| `duration_eligible` | `boolean` | Case passes all duration-scope checks |
| `duration_exclusion_reason` | `text` | Reasons for exclusion; empty/NULL when eligible |

The original design proposed additional case-level variant and repetition fields. These are not columns of the implemented timing table. Variant summaries and diagnostic markers are produced in the discovery and conformance/bottleneck outputs.

A repeated activity is not automatically rework. Some activities legitimately recur, especially for purchase items involving multiple deliveries or invoices.

A separate business rule is required before repetition is classified as rework.

## 9. Relationship Rules

- One purchase document can contain multiple cases.
- One case belongs to one purchase document.
- One case contains one or more events.
- One event belongs to exactly one case.
- One case with `n` events can produce `n - 1` transitions.
- One case produces one timing row.
- Cases with one event produce zero transitions.

## 10. Naming Rules

ProcessIQ will use:

- Lowercase `snake_case` column names
- Singular values inside rows
- `_id` for identifiers
- `_timestamp` for complete dates and times
- `_count` for counts
- `_seconds` for durations
- `is_` or `has_` prefixes for boolean flags where appropriate

Source column names will be documented but not used directly as Python or SQL identifiers.

## 11. Missing-Value Rules

The initial missing markers are:

- Empty string
- `NONE`
- `UNKNOWN`

Rules:

1. The original source value must remain recoverable.
2. Missing markers may be converted to database `NULL` only through a documented transformation.
3. Boolean `false` is a valid value and must never be treated as missing.
4. Numeric zero is a valid value and must never be treated as missing automatically.
5. Missing resources must not automatically be classified as automated events.
6. A present XML attribute can still contain a missing marker.

## 12. Timestamp Rules

- Parse timestamps as timezone-aware values.
- Preserve the original event order.
- Preserve source timestamps and record whether they fall outside the implemented 2018–2019 analysis window.
- Do not delete historical or future timestamps automatically.
- Flag negative consecutive durations.
- Investigate events before 2010 separately.
- Investigate the two observed 2020 events separately.
- Determine whether 2019 events complete cases created in 2018.
- Use only duration-eligible cases for duration summaries: no out-of-window event, no backwards timestamp step, and observed span at most 365 days.
- Keep excluded cases and their reasons in the analytical tables. Eligibility does not imply completion or conformance.

## 13. Initial Integrity Rules

The ingestion and validation pipeline must test:

1. Every case has a non-missing `case_id`.
2. `case_id` values are unique in the cases table.
3. Every event refers to an existing case.
4. Event positions start at 1 within every case.
5. Event positions are consecutive within every case.
6. The combination of `case_id` and `event_position` is unique.
7. Activity names are present.
8. Timestamps are present and parseable.
9. Boolean values can be converted without guessing.
10. Item categories belong to the observed controlled set.
11. Extracted trace count equals 251,734.
12. Extracted event count equals 1,595,923.
13. Item-category counts reconcile to the case count.
14. Activity counts reconcile to the event count.
15. The original XES source remains unchanged.

## 14. Explicit Non-Decisions

The implemented duration-exclusion policy is documented in [methodology](methodology.md). The following business interpretations remain unresolved or outside the implemented scope:

- Which repeated activities represent rework
- Which final activities represent process completion
- Which process path is compliant for every category
- Whether `User` and `org:resource` are semantically interchangeable
- Whether missing resources are expected for particular activities
- Which amount-reconciliation tolerance is appropriate
- Whether a case is late or SLA-compliant

These decisions require evidence and documented business rules.

## 15. Design Principles

- Preserve source evidence before transforming it.
- Give every row one clear meaning.
- Prefer transparent rules over unexplained automation.
- Separate recorded facts from derived metrics.
- Keep identifiers as identifiers rather than treating them as numbers.
- Retain original event order when timestamps tie.
- Flag questionable records instead of silently deleting them.
- Do not describe elapsed time as business waiting time without evidence.
- Do not describe statistical association as causation.
