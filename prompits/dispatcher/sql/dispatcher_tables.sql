create table if not exists dispatcher_jobs (
    id text primary key,
    job_type text,
    status text,
    required_capability text,
    capability_tags jsonb,
    targets jsonb,
    payload jsonb,
    target_table text,
    source_url text,
    parse_rules jsonb,
    priority integer,
    premium boolean,
    metadata jsonb,
    scheduled_for timestamptz,
    claimed_by text,
    claimed_at timestamptz,
    completed_at timestamptz,
    result_summary jsonb,
    error text,
    attempts integer,
    max_attempts integer,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists dispatcher_worker_capabilities (
    id text primary key,
    worker_id text,
    name text,
    address text,
    capabilities jsonb,
    metadata jsonb,
    plaza_url text,
    status text,
    last_seen_at timestamptz,
    updated_at timestamptz
);

create table if not exists dispatcher_worker_history (
    id text primary key,
    worker_id text,
    name text,
    address text,
    capabilities jsonb,
    plaza_url text,
    status text,
    event_type text,
    session_started_at timestamptz,
    active_job_id text,
    active_job_status text,
    progress jsonb,
    environment jsonb,
    metadata jsonb,
    captured_at timestamptz
);

create table if not exists dispatcher_job_results (
    id text primary key,
    job_id text,
    worker_id text,
    table_name text,
    source_url text,
    payload jsonb,
    metadata jsonb,
    recorded_at timestamptz
);

create table if not exists dispatcher_raw_payloads (
    id text primary key,
    job_id text,
    worker_id text,
    target_table text,
    source_url text,
    payload jsonb,
    metadata jsonb,
    collected_at timestamptz
);
