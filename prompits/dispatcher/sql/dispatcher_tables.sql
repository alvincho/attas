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

create table if not exists dispatcher_jobs_archive (
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
    updated_at timestamptz,
    archived_at timestamptz
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

create table if not exists dispatcher_worker_history_archive (
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
    captured_at timestamptz,
    archived_at timestamptz
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

create table if not exists dispatcher_job_results_archive (
    id text primary key,
    job_id text,
    worker_id text,
    table_name text,
    source_url text,
    payload jsonb,
    metadata jsonb,
    recorded_at timestamptz,
    archived_at timestamptz
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

create table if not exists dispatcher_raw_payloads_archive (
    id text primary key,
    job_id text,
    worker_id text,
    target_table text,
    source_url text,
    payload jsonb,
    metadata jsonb,
    collected_at timestamptz,
    archived_at timestamptz
);

create index if not exists dispatcher_jobs_status_idx
    on dispatcher_jobs ((lower(coalesce(status, ''))));

create index if not exists dispatcher_jobs_ready_order_idx
    on dispatcher_jobs (priority, created_at, id)
    where lower(coalesce(status, '')) in ('queued', 'retry', 'unfinished');

create index if not exists dispatcher_jobs_ready_schedule_idx
    on dispatcher_jobs (scheduled_for, priority, created_at, id)
    where lower(coalesce(status, '')) in ('queued', 'retry', 'unfinished');

create index if not exists dispatcher_jobs_ready_capability_idx
    on dispatcher_jobs ((lower(coalesce(required_capability, ''))), priority, created_at, id)
    where lower(coalesce(status, '')) in ('queued', 'retry', 'unfinished');

create index if not exists dispatcher_jobs_claimed_worker_idx
    on dispatcher_jobs (claimed_by, (lower(coalesce(status, ''))))
    where coalesce(claimed_by, '') <> '';

create index if not exists dispatcher_jobs_status_pipeline_logical_key_idx
    on dispatcher_jobs (
        (lower(coalesce(status, ''))),
        (
            coalesce(
                metadata -> 'stamp_auction_network' ->> 'logical_job_key',
                metadata -> 'ebay_active_stamp' ->> 'logical_job_key',
                metadata ->> 'logical_job_key',
                ''
            )
        )
    );

create index if not exists dispatcher_jobs_archive_completed_idx
    on dispatcher_jobs_archive (completed_at desc, archived_at desc);

create index if not exists dispatcher_worker_history_worker_captured_idx
    on dispatcher_worker_history (worker_id, captured_at desc);

create index if not exists dispatcher_worker_history_captured_idx
    on dispatcher_worker_history (captured_at desc);

create index if not exists dispatcher_worker_history_archive_captured_idx
    on dispatcher_worker_history_archive (captured_at desc, worker_id);

create index if not exists dispatcher_job_results_recorded_idx
    on dispatcher_job_results (recorded_at desc, job_id);

create index if not exists dispatcher_job_results_archive_recorded_idx
    on dispatcher_job_results_archive (recorded_at desc, job_id);

create index if not exists dispatcher_raw_payloads_collected_idx
    on dispatcher_raw_payloads (collected_at desc, job_id);

create index if not exists dispatcher_raw_payloads_archive_collected_idx
    on dispatcher_raw_payloads_archive (collected_at desc, job_id);
