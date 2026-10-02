# ProcessIQ Data Model and Data Dictionary

## 1. Purpose

This document defines how ProcessIQ will convert the BPI Challenge 2019 XES event log into structured analytical data.

The model is defined before ingestion so that column names, row meanings, keys, data types, and calculation rules are not invented inconsistently during implementation.

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

One case-metric row summarises the complete history of one case.

## 3. Data Layers

ProcessIQ will use four logical data layers.

### Layer 1: Immutable source

File:

`data/raw/BPI_Challenge_2019.xes`

Purpose:

- Preserve the original downloaded event log.
- Provide the source for reproducible ingestion.
- Never edit the file manually.
- Never upload the file to GitHub.

### Layer 2: Interim extracted data

Planned files:

- `data/interim/cases_raw.csv`
- `data/interim/events_raw.csv`

Purpose:

- Convert nested XES data into flat rows.
- Preserve source values.
- Use standardised column names.
- Retain source event order.
- Support inspection before database loading.

These files will remain outside Git.

### Layer 3: Typed PostgreSQL tables

Planned tables:

- `cases`
- `events`

Purpose:

- Apply explicit data types.
- Enforce keys and important constraints.
- Support reliable SQL analysis.
- Separate case-level attributes from event-level attributes.

### Layer 4: Derived analytical tables or views

Planned analytical structures:

- `transitions`
- `case_metrics`
- Process-variant views
- Data-quality views
- Management KPI views

Derived structures will be created only after their rules are documented and tested.

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

`Review` means the attribute is structurally present, but its value quality and missing markers still need validation.

Identifiers will remain text. Converting them to numbers could remove leading zeroes or create false arithmetic meaning.

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
| `cumulative_net_worth` | `Cumulative net worth (EUR)` | `numeric` | Review | Anonymised cumulative monetary value |

The source labels the monetary field as EUR, but the official documentation states that monetary values were anonymised through a linear transformation.

ProcessIQ will therefore use the field for relative and reconciliation analysis. It will not present the value as realised financial savings.

## 7. Transitions Structure

### Grain

One row per consecutive pair of events within a case.

### Planned columns

| Column | Type | Meaning |
|---|---|---|
| `case_id` | `text` | Parent case |
| `transition_position` | `integer` | Position of the transition within the case |
| `from_event_position` | `integer` | Starting event position |
| `to_event_position` | `integer` | Following event position |
| `from_activity` | `text` | Starting activity |
| `to_activity` | `text` | Following activity |
| `from_timestamp` | `timestamp with time zone` | Starting event time |
| `to_timestamp` | `timestamp with time zone` | Following event time |
| `elapsed_seconds` | `numeric` | Recorded time difference between the two events |
| `same_timestamp` | `boolean` | Whether both timestamps are equal |
| `negative_elapsed_time` | `boolean` | Whether source order moves backward in time |

`elapsed_seconds` is a recorded time difference. It will not automatically be called working time or waiting time because the event log may not reveal what happened between two recorded events.

## 8. Case Metrics Structure

### Grain

One row per case.

### Planned columns

| Column | Type | Meaning |
|---|---|---|
| `case_id` | `text` | Case identifier |
| `first_event_timestamp` | `timestamp with time zone` | Earliest event time used for the case |
| `last_event_timestamp` | `timestamp with time zone` | Latest event time used for the case |
| `cycle_time_seconds` | `numeric` | Difference between the selected first and last timestamps |
| `event_count` | `integer` | Number of events in the case |
| `unique_activity_count` | `integer` | Number of different activities |
| `repeat_event_count` | `integer` | Event count minus unique-activity count |
| `missing_resource_event_count` | `integer` | Events with a missing resource marker |
| `variant_signature` | `text` | Ordered activity sequence |
| `has_negative_elapsed_time` | `boolean` | Whether any consecutive timestamps move backward |

A repeated activity is not automatically rework. Some activities legitimately recur, especially for purchase items involving multiple deliveries or invoices.

A separate business rule is required before repetition is classified as rework.

## 9. Relationship Rules

- One purchase document can contain multiple cases.
- One case belongs to one purchase document.
- One case contains one or more events.
- One event belongs to exactly one case.
- One case with `n` events can produce `n - 1` transitions.
- One case produces one case-metrics row.
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
- Record timestamps outside the stated 2018 coverage.
- Do not delete historical or future timestamps automatically.
- Flag negative consecutive durations.
- Investigate events before 2010 separately.
- Investigate the two observed 2020 events separately.
- Determine whether 2019 events complete cases created in 2018.
- Do not calculate trusted cycle times until timestamp-quality rules are approved.

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

ProcessIQ has not yet decided:

- Which timestamp anomalies should be excluded from duration metrics
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
