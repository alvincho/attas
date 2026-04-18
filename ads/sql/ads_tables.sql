create table if not exists ads_jobs (
    id text primary key,
    job_type text,
    status text,
    required_capability text,
    capability_tags jsonb,
    symbols jsonb,
    payload jsonb,
    target_table text,
    source_url text,
    parse_rules jsonb,
    priority integer default 100,
    premium boolean default false,
    metadata jsonb,
    scheduled_for timestamptz,
    claimed_by text,
    claimed_at timestamptz,
    completed_at timestamptz,
    result_summary jsonb,
    error text,
    attempts integer default 0,
    max_attempts integer default 3,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists ads_jobs_archive (
    id text primary key,
    job_type text,
    status text,
    required_capability text,
    capability_tags jsonb,
    symbols jsonb,
    payload jsonb,
    target_table text,
    source_url text,
    parse_rules jsonb,
    priority integer default 100,
    premium boolean default false,
    metadata jsonb,
    scheduled_for timestamptz,
    claimed_by text,
    claimed_at timestamptz,
    completed_at timestamptz,
    result_summary jsonb,
    error text,
    attempts integer default 0,
    max_attempts integer default 3,
    created_at timestamptz,
    updated_at timestamptz,
    archived_at timestamptz
);

create index if not exists ads_jobs_status_idx
    on ads_jobs ((lower(coalesce(status, ''))));

create index if not exists ads_jobs_ready_order_idx
    on ads_jobs (priority, created_at, id)
    where lower(coalesce(status, '')) in ('queued', 'retry', 'unfinished');

create index if not exists ads_jobs_ready_schedule_idx
    on ads_jobs (scheduled_for, priority, created_at, id)
    where lower(coalesce(status, '')) in ('queued', 'retry', 'unfinished');

create index if not exists ads_jobs_ready_capability_idx
    on ads_jobs ((lower(coalesce(required_capability, ''))), priority, created_at, id)
    where lower(coalesce(status, '')) in ('queued', 'retry', 'unfinished');

create index if not exists ads_jobs_claimed_worker_idx
    on ads_jobs (claimed_by, (lower(coalesce(status, ''))))
    where coalesce(claimed_by, '') <> '';

create index if not exists ads_jobs_archive_completed_idx
    on ads_jobs_archive (completed_at desc, archived_at desc);

create table if not exists ads_worker_capabilities (
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

create table if not exists ads_worker_history (
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

create table if not exists ads_security_master (
    id text primary key,
    symbol text,
    name text,
    instrument_type text,
    exchange text,
    currency text,
    is_active boolean,
    provider text,
    metadata jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists ads_daily_price (
    id text primary key,
    symbol text not null,
    trade_date text not null,
    open double precision,
    high double precision,
    low double precision,
    close double precision,
    adj_close double precision,
    volume double precision,
    provider text not null,
    source_url text,
    metadata jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

create unique index if not exists ads_daily_price_symbol_trade_date_provider_uq
    on ads_daily_price (symbol, trade_date, provider);

create table if not exists ads_fundamentals (
    id text primary key,
    symbol text,
    as_of_date text,
    market_cap double precision,
    pe_ratio double precision,
    dividend_yield double precision,
    sector text,
    industry text,
    provider text,
    data jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists ads_financial_statements (
    id text primary key,
    symbol text,
    statement_type text,
    period_end text,
    fiscal_period text,
    currency text,
    provider text,
    data jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists ads_news (
    id text primary key,
    symbol text,
    headline text,
    summary text,
    url text,
    source text,
    source_url text,
    published_at timestamptz,
    sentiment double precision,
    data jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists ads_sec_companyfacts (
    id text,
    cik text primary key,
    entity_name text,
    file_name text,
    fact_count bigint,
    source_url text,
    provider text,
    payload jsonb,
    created_at timestamptz,
    updated_at timestamptz
);

create table if not exists ads_sec_submissions (
    id text,
    cik text,
    entity_name text,
    symbol text,
    symbols jsonb,
    exchanges jsonb,
    file_name text,
    is_primary boolean,
    filing_count bigint,
    source_url text,
    provider text,
    payload jsonb,
    created_at timestamptz,
    updated_at timestamptz,
    primary key (cik, file_name)
);

create table if not exists ads_raw_data_collected (
    id text primary key,
    job_id text,
    worker_id text,
    target_table text,
    source_url text,
    payload jsonb,
    metadata jsonb,
    collected_at timestamptz
);
