\set ON_ERROR_STOP on

BEGIN;

TRUNCATE TABLE
    processiq.events,
    processiq.case_timing,
    processiq.cases;

\copy processiq.cases FROM 'data/processed/cases.csv' WITH (FORMAT csv, HEADER true, NULL '');

\copy processiq.events FROM 'data/processed/events.csv' WITH (FORMAT csv, HEADER true, NULL '');

\copy processiq.case_timing FROM 'data/processed/case_timing.csv' WITH (FORMAT csv, HEADER true, NULL '');

COMMIT;

ANALYZE processiq.cases;
ANALYZE processiq.events;
ANALYZE processiq.case_timing;