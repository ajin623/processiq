BEGIN;

CREATE SCHEMA processiq;

SET search_path TO processiq, public;

CREATE TABLE cases (
    case_id text PRIMARY KEY,
    purchasing_document_id text NOT NULL,
    item_id text NOT NULL,
    item_type text,
    gr_based_invoice_verification boolean NOT NULL,
    goods_receipt_required boolean NOT NULL,
    source_system_id text,
    purchasing_document_category text,
    company_id text,
    spend_classification text,
    spend_area text,
    sub_spend_area text,
    vendor_id text,
    vendor_name text,
    document_type text,
    item_category text NOT NULL,
    spend_data_complete boolean NOT NULL,

    CONSTRAINT cases_item_category_allowed
        CHECK (
            item_category IN (
                '2-way match',
                '3-way match, invoice after GR',
                '3-way match, invoice before GR',
                'Consignment'
            )
        ),

    CONSTRAINT cases_spend_completeness_matches_values
        CHECK (
            spend_data_complete = (
                spend_classification IS NOT NULL
                AND spend_area IS NOT NULL
                AND sub_spend_area IS NOT NULL
            )
        )
);

CREATE TABLE events (
    case_id text NOT NULL,
    event_position integer NOT NULL,
    activity text NOT NULL,
    event_timestamp timestamp with time zone NOT NULL,
    resource_id text,
    user_id text,
    cumulative_net_worth numeric NOT NULL,
    resource_recorded boolean NOT NULL,
    timestamp_in_analysis_window boolean NOT NULL,

    CONSTRAINT events_primary_key
        PRIMARY KEY (
            case_id,
            event_position
        ),

    CONSTRAINT events_case_foreign_key
        FOREIGN KEY (case_id)
        REFERENCES cases (case_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT events_position_positive
        CHECK (event_position > 0),

    CONSTRAINT events_resource_flag_matches_value
        CHECK (
            resource_recorded = (
                resource_id IS NOT NULL
            )
        ),

    CONSTRAINT events_timestamp_flag_matches_year
        CHECK (
            timestamp_in_analysis_window = (
                EXTRACT(
                    YEAR FROM
                    event_timestamp AT TIME ZONE 'UTC'
                ) BETWEEN 2018 AND 2019
            )
        )
);

CREATE TABLE case_timing (
    case_id text PRIMARY KEY,
    first_event_timestamp timestamp with time zone NOT NULL,
    last_event_timestamp timestamp with time zone NOT NULL,
    cycle_time_seconds numeric(20, 6) NOT NULL,
    cycle_time_days numeric(20, 6) NOT NULL,
    event_count integer NOT NULL,
    outside_analysis_window_event_count integer NOT NULL,
    has_negative_timestamp boolean NOT NULL,
    exceeds_365_days boolean NOT NULL,
    duration_eligible boolean NOT NULL,
    duration_exclusion_reason text,

    CONSTRAINT case_timing_case_foreign_key
        FOREIGN KEY (case_id)
        REFERENCES cases (case_id)
        ON UPDATE RESTRICT
        ON DELETE RESTRICT,

    CONSTRAINT case_timing_event_count_positive
        CHECK (event_count > 0),

    CONSTRAINT case_timing_outside_count_nonnegative
        CHECK (
            outside_analysis_window_event_count >= 0
        ),

    CONSTRAINT case_timing_seconds_match_timestamps
        CHECK (
            ABS(
                EXTRACT(
                    EPOCH FROM (
                        last_event_timestamp
                        - first_event_timestamp
                    )
                )
                - cycle_time_seconds
            ) <= 0.001
        ),

    CONSTRAINT case_timing_days_match_seconds
        CHECK (
            ABS(
                cycle_time_seconds
                - cycle_time_days * 86400
            ) <= 0.1
        ),

    CONSTRAINT case_timing_long_case_flag_matches
        CHECK (
            exceeds_365_days = (
                cycle_time_days > 365
            )
        ),

    CONSTRAINT case_timing_eligibility_matches_flags
        CHECK (
            duration_eligible = (
                outside_analysis_window_event_count = 0
                AND NOT has_negative_timestamp
                AND NOT exceeds_365_days
            )
        ),

    CONSTRAINT case_timing_reason_matches_eligibility
        CHECK (
            (
                duration_eligible
                AND duration_exclusion_reason IS NULL
            )
            OR
            (
                NOT duration_eligible
                AND duration_exclusion_reason IS NOT NULL
            )
        )
);

COMMIT;
