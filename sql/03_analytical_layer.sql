\set ON_ERROR_STOP on

BEGIN;

CREATE INDEX cases_item_category_idx
    ON processiq.cases (item_category);

CREATE INDEX events_activity_idx
    ON processiq.events (activity);

CREATE INDEX events_timestamp_idx
    ON processiq.events (event_timestamp);

CREATE INDEX case_timing_eligible_duration_idx
    ON processiq.case_timing (cycle_time_days)
    WHERE duration_eligible;

CREATE VIEW processiq.case_overview AS
SELECT
    c.case_id,
    c.purchasing_document_id,
    c.item_id,
    c.item_type,
    c.company_id,
    c.document_type,
    c.item_category,
    c.gr_based_invoice_verification,
    c.goods_receipt_required,
    c.spend_classification,
    c.spend_area,
    c.sub_spend_area,
    c.spend_data_complete,
    t.first_event_timestamp,
    t.last_event_timestamp,
    t.cycle_time_seconds,
    t.cycle_time_days,
    t.event_count,
    t.outside_analysis_window_event_count,
    t.has_negative_timestamp,
    t.exceeds_365_days,
    t.duration_eligible,
    t.duration_exclusion_reason
FROM processiq.cases AS c
JOIN processiq.case_timing AS t
    ON t.case_id = c.case_id;

CREATE VIEW processiq.transitions AS
WITH sequenced_events AS (
    SELECT
        e.case_id,
        e.event_position AS from_event_position,
        e.activity AS from_activity,
        e.event_timestamp AS from_timestamp,
        LEAD(e.event_position) OVER (
            PARTITION BY e.case_id
            ORDER BY e.event_position
        ) AS to_event_position,
        LEAD(e.activity) OVER (
            PARTITION BY e.case_id
            ORDER BY e.event_position
        ) AS to_activity,
        LEAD(e.event_timestamp) OVER (
            PARTITION BY e.case_id
            ORDER BY e.event_position
        ) AS to_timestamp
    FROM processiq.events AS e
)
SELECT
    s.case_id,
    s.from_event_position,
    s.to_event_position,
    s.from_activity,
    s.to_activity,
    s.from_timestamp,
    s.to_timestamp,
    s.to_timestamp - s.from_timestamp
        AS elapsed_interval,
    EXTRACT(
        EPOCH FROM (
            s.to_timestamp - s.from_timestamp
        )
    ) AS elapsed_seconds,
    s.to_timestamp = s.from_timestamp
        AS same_timestamp,
    s.to_timestamp < s.from_timestamp
        AS negative_elapsed_time,
    t.duration_eligible
        AS case_duration_eligible
FROM sequenced_events AS s
JOIN processiq.case_timing AS t
    ON t.case_id = s.case_id
WHERE s.to_event_position IS NOT NULL;

COMMIT;

ANALYZE processiq.cases;
ANALYZE processiq.events;
ANALYZE processiq.case_timing;

SELECT
    (SELECT COUNT(*) FROM processiq.cases)
        AS case_count,
    (SELECT COUNT(*) FROM processiq.events)
        AS event_count,
    (SELECT COUNT(*) FROM processiq.case_timing)
        AS timing_count;

SELECT
    COUNT(*) FILTER (
        WHERE NOT spend_data_complete
    ) AS incomplete_spend_cases
FROM processiq.cases;

SELECT
    COUNT(*) FILTER (
        WHERE NOT resource_recorded
    ) AS events_without_resource,
    COUNT(*) FILTER (
        WHERE NOT timestamp_in_analysis_window
    ) AS events_outside_window
FROM processiq.events;

SELECT
    COUNT(*) FILTER (
        WHERE duration_eligible
    ) AS eligible_duration_cases,
    COUNT(*) FILTER (
        WHERE NOT duration_eligible
    ) AS ineligible_duration_cases
FROM processiq.case_timing;

WITH measured AS (
    SELECT COUNT(*) AS transition_count
    FROM processiq.transitions
),
expected AS (
    SELECT
        (
            (SELECT COUNT(*) FROM processiq.events)
            -
            (SELECT COUNT(*) FROM processiq.cases)
        ) AS expected_transition_count
)
SELECT
    measured.transition_count,
    expected.expected_transition_count,
    measured.transition_count
        = expected.expected_transition_count
        AS counts_match
FROM measured
CROSS JOIN expected;