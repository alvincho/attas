-- Supabase migration for Plaza storage tables
-- Run in Supabase SQL Editor (or via supabase migration tooling).

drop function if exists public.batch_upsert_agent_configs(jsonb);
drop table if exists public.agent_configs;

create table if not exists public.plaza_credentials (
    id uuid primary key default gen_random_uuid(),
    plaza_url text not null,
    agent_id text not null,
    agent_name text not null,
    api_key text not null,
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_plaza_credentials_agent_name
    on public.plaza_credentials (agent_name);

create unique index if not exists idx_plaza_credentials_agent_name_plaza_url
    on public.plaza_credentials (agent_name, plaza_url);

create table if not exists public.plaza_login_history (
    id uuid primary key default gen_random_uuid(),
    agent_id text not null,
    agent_name text not null,
    address text,
    event text not null,
    timestamp timestamptz not null default timezone('utc', now())
);

create index if not exists idx_plaza_login_history_agent_id_ts
    on public.plaza_login_history (agent_id, timestamp desc);

create table if not exists public.plaza_directory (
    id text primary key,
    agent_id text not null,
    name text not null,
    type text not null,
    description text,
    owner text,
    address text,
    meta jsonb not null default '{}'::jsonb,
    card jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_plaza_directory_type
    on public.plaza_directory (type);

create index if not exists idx_plaza_directory_name
    on public.plaza_directory (name);

create index if not exists idx_plaza_directory_owner
    on public.plaza_directory (owner);

create index if not exists idx_plaza_directory_updated_at
    on public.plaza_directory (updated_at desc);

create table if not exists public.agent_practices (
    id text primary key,
    agent_name text not null,
    practice_id text not null,
    practice_name text not null,
    practice_description text,
    practice_data jsonb not null default '{}'::jsonb,
    is_deleted boolean not null default false,
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_agent_practices_agent_name
    on public.agent_practices (agent_name);

create index if not exists idx_agent_practices_practice_id
    on public.agent_practices (practice_id);

create table if not exists public.pulse_pulser_pairs (
    id text primary key,
    pulse_id text,
    pulse_directory_id text,
    pulse_name text not null,
    pulse_address text not null,
    pulse_definition jsonb not null default '{}'::jsonb,
    status text not null default 'stable',
    is_complete boolean,
    completion_status text,
    completion_errors jsonb not null default '[]'::jsonb,
    pulser_id text not null,
    pulser_directory_id text,
    pulser_name text not null,
    pulser_address text,
    input_schema jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default timezone('utc', now())
);

alter table if exists public.pulse_pulser_pairs
    add column if not exists pulse_id text;

alter table if exists public.pulse_pulser_pairs
    add column if not exists pulse_directory_id text;

alter table if exists public.pulse_pulser_pairs
    add column if not exists pulse_definition jsonb not null default '{}'::jsonb;

alter table if exists public.pulse_pulser_pairs
    add column if not exists status text not null default 'stable';

alter table if exists public.pulse_pulser_pairs
    add column if not exists is_complete boolean;

alter table if exists public.pulse_pulser_pairs
    add column if not exists completion_status text;

alter table if exists public.pulse_pulser_pairs
    add column if not exists completion_errors jsonb not null default '[]'::jsonb;

alter table if exists public.pulse_pulser_pairs
    add column if not exists pulser_directory_id text;

create index if not exists idx_pulse_pulser_pairs_pulse_id
    on public.pulse_pulser_pairs (pulse_id);

create index if not exists idx_pulse_pulser_pairs_pulse_directory_id
    on public.pulse_pulser_pairs (pulse_directory_id);

create index if not exists idx_pulse_pulser_pairs_pulse_name
    on public.pulse_pulser_pairs (pulse_name);

create index if not exists idx_pulse_pulser_pairs_pulse_address
    on public.pulse_pulser_pairs (pulse_address);

create index if not exists idx_pulse_pulser_pairs_pulser_id
    on public.pulse_pulser_pairs (pulser_id);

create index if not exists idx_pulse_pulser_pairs_pulser_directory_id
    on public.pulse_pulser_pairs (pulser_directory_id);

create index if not exists idx_pulse_pulser_pairs_updated_at
    on public.pulse_pulser_pairs (updated_at desc);

update public.pulse_pulser_pairs as pairs
set pulser_directory_id = directory.id
from public.plaza_directory as directory
where pairs.pulser_directory_id is null
  and directory.type = 'Pulser'
  and directory.id = pairs.pulser_id;

update public.pulse_pulser_pairs as pairs
set pulse_directory_id = directory.id
from public.plaza_directory as directory
where pairs.pulse_directory_id is null
  and directory.type = 'Pulse'
  and (
    lower(directory.name) = lower(pairs.pulse_name)
    or coalesce(directory.meta->>'pulse_id', '') = coalesce(pairs.pulse_id, '')
    or coalesce(directory.meta->>'pulse_address', '') = coalesce(pairs.pulse_address, '')
  );

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'fk_pulse_pulser_pairs_pulse_directory'
    ) then
        alter table public.pulse_pulser_pairs
            add constraint fk_pulse_pulser_pairs_pulse_directory
            foreign key (pulse_directory_id) references public.plaza_directory(id) not valid;
    end if;

    if not exists (
        select 1 from pg_constraint
        where conname = 'fk_pulse_pulser_pairs_pulser_directory'
    ) then
        alter table public.pulse_pulser_pairs
            add constraint fk_pulse_pulser_pairs_pulser_directory
            foreign key (pulser_directory_id) references public.plaza_directory(id) not valid;
    end if;
end $$;

create table if not exists public.plaza_ui_users (
    id text primary key,
    username text,
    email text not null,
    display_name text,
    role text not null default 'user',
    status text not null default 'active',
    auth_provider text not null default 'password',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    last_sign_in_at timestamptz
);

alter table if exists public.plaza_ui_users
    add column if not exists username text;

alter table if exists public.plaza_ui_users
    add column if not exists auth_provider text not null default 'password';

create index if not exists idx_plaza_ui_users_email
    on public.plaza_ui_users (email);

create unique index if not exists idx_plaza_ui_users_username
    on public.plaza_ui_users (username);

create index if not exists idx_plaza_ui_users_role
    on public.plaza_ui_users (role);

create index if not exists idx_plaza_ui_users_status
    on public.plaza_ui_users (status);

create index if not exists idx_plaza_ui_users_auth_provider
    on public.plaza_ui_users (auth_provider);

create table if not exists public.phemas (
    id text primary key,
    name text not null,
    description text,
    owner text,
    address text,
    tags jsonb not null default '[]'::jsonb,
    input_schema jsonb not null default '{}'::jsonb,
    sections jsonb not null default '[]'::jsonb,
    resolution_mode text,
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_phemas_name
    on public.phemas (name);

create index if not exists idx_phemas_owner
    on public.phemas (owner);

create index if not exists idx_phemas_updated_at
    on public.phemas (updated_at desc);

create table if not exists public.plaza_tokens (
    token text primary key,
    agent_id text not null,
    agent_name text not null,
    expires_at real not null,
    created_at text not null
);

create index if not exists idx_plaza_tokens_agent_id
    on public.plaza_tokens (agent_id);

create or replace function public.batch_upsert_agent_practices(entries jsonb)
returns integer
language sql
as $$
    with payload as (
        select
            nullif(trim(entry->>'id'), '') as id,
            coalesce(entry->>'agent_name', '') as agent_name,
            coalesce(entry->>'practice_id', '') as practice_id,
            coalesce(entry->>'practice_name', '') as practice_name,
            coalesce(entry->>'practice_description', '') as practice_description,
            coalesce(entry->'practice_data', '{}'::jsonb) as practice_data,
            coalesce((entry->>'is_deleted')::boolean, false) as is_deleted,
            coalesce(nullif(entry->>'updated_at', '')::timestamptz, timezone('utc', now())) as updated_at
        from jsonb_array_elements(coalesce(entries, '[]'::jsonb)) as entry
    ),
    upserted as (
        insert into public.agent_practices (
            id,
            agent_name,
            practice_id,
            practice_name,
            practice_description,
            practice_data,
            is_deleted,
            updated_at
        )
        select
            id,
            agent_name,
            practice_id,
            practice_name,
            practice_description,
            practice_data,
            is_deleted,
            updated_at
        from payload
        where id is not null
        on conflict (id) do update
        set agent_name = excluded.agent_name,
            practice_id = excluded.practice_id,
            practice_name = excluded.practice_name,
            practice_description = excluded.practice_description,
            practice_data = excluded.practice_data,
            is_deleted = excluded.is_deleted,
            updated_at = excluded.updated_at
        returning 1
    )
    select count(*)::integer from upserted;
$$;

create or replace function public.batch_upsert_plaza_directory(entries jsonb)
returns integer
language sql
as $$
    with payload as (
        select
            nullif(trim(entry->>'id'), '') as id,
            coalesce(nullif(entry->>'agent_id', ''), nullif(trim(entry->>'id'), '')) as agent_id,
            coalesce(entry->>'name', '') as name,
            coalesce(nullif(entry->>'type', ''), 'Agent') as type,
            coalesce(entry->>'description', '') as description,
            coalesce(entry->>'owner', '') as owner,
            coalesce(entry->>'address', '') as address,
            coalesce(entry->'meta', '{}'::jsonb) as meta,
            coalesce(entry->'card', '{}'::jsonb) as card,
            coalesce(nullif(entry->>'updated_at', '')::timestamptz, timezone('utc', now())) as updated_at
        from jsonb_array_elements(coalesce(entries, '[]'::jsonb)) as entry
    ),
    upserted as (
        insert into public.plaza_directory (
            id,
            agent_id,
            name,
            type,
            description,
            owner,
            address,
            meta,
            card,
            updated_at
        )
        select
            id,
            agent_id,
            name,
            type,
            description,
            owner,
            address,
            meta,
            card,
            updated_at
        from payload
        where id is not null
        on conflict (id) do update
        set agent_id = excluded.agent_id,
            name = excluded.name,
            type = excluded.type,
            description = excluded.description,
            owner = excluded.owner,
            address = excluded.address,
            meta = excluded.meta,
            card = excluded.card,
            updated_at = excluded.updated_at
        returning 1
    )
    select count(*)::integer from upserted;
$$;

create or replace function public.batch_upsert_pulse_pulser_pairs(entries jsonb)
returns integer
language sql
as $$
    with payload as (
        select
            nullif(trim(entry->>'id'), '') as id,
            nullif(entry->>'pulse_id', '') as pulse_id,
            nullif(entry->>'pulse_directory_id', '') as pulse_directory_id,
            coalesce(entry->>'pulse_name', '') as pulse_name,
            coalesce(entry->>'pulse_address', '') as pulse_address,
            coalesce(entry->'pulse_definition', '{}'::jsonb) as pulse_definition,
            coalesce(nullif(entry->>'status', ''), 'stable') as status,
            (entry->>'is_complete')::boolean as is_complete,
            nullif(entry->>'completion_status', '') as completion_status,
            coalesce(entry->'completion_errors', '[]'::jsonb) as completion_errors,
            coalesce(entry->>'pulser_id', '') as pulser_id,
            nullif(entry->>'pulser_directory_id', '') as pulser_directory_id,
            coalesce(entry->>'pulser_name', '') as pulser_name,
            nullif(entry->>'pulser_address', '') as pulser_address,
            coalesce(entry->'input_schema', '{}'::jsonb) as input_schema,
            coalesce(nullif(entry->>'updated_at', '')::timestamptz, timezone('utc', now())) as updated_at
        from jsonb_array_elements(coalesce(entries, '[]'::jsonb)) as entry
    ),
    upserted as (
        insert into public.pulse_pulser_pairs (
            id,
            pulse_id,
            pulse_directory_id,
            pulse_name,
            pulse_address,
            pulse_definition,
            status,
            is_complete,
            completion_status,
            completion_errors,
            pulser_id,
            pulser_directory_id,
            pulser_name,
            pulser_address,
            input_schema,
            updated_at
        )
        select
            id,
            pulse_id,
            pulse_directory_id,
            pulse_name,
            pulse_address,
            pulse_definition,
            status,
            is_complete,
            completion_status,
            completion_errors,
            pulser_id,
            pulser_directory_id,
            pulser_name,
            pulser_address,
            input_schema,
            updated_at
        from payload
        where id is not null
        on conflict (id) do update
        set pulse_id = excluded.pulse_id,
            pulse_directory_id = excluded.pulse_directory_id,
            pulse_name = excluded.pulse_name,
            pulse_address = excluded.pulse_address,
            pulse_definition = excluded.pulse_definition,
            status = excluded.status,
            is_complete = excluded.is_complete,
            completion_status = excluded.completion_status,
            completion_errors = excluded.completion_errors,
            pulser_id = excluded.pulser_id,
            pulser_directory_id = excluded.pulser_directory_id,
            pulser_name = excluded.pulser_name,
            pulser_address = excluded.pulser_address,
            input_schema = excluded.input_schema,
            updated_at = excluded.updated_at
        returning 1
    )
    select count(*)::integer from upserted;
$$;

-- Security hardening: every API-exposed Plaza table should require RLS.
-- These tables are intended for server-side access through the Plaza backend.
alter table if exists public.plaza_credentials enable row level security;
alter table if exists public.plaza_login_history enable row level security;
alter table if exists public.plaza_directory enable row level security;
alter table if exists public.agent_practices enable row level security;
alter table if exists public.pulse_pulser_pairs enable row level security;
alter table if exists public.plaza_ui_users enable row level security;
alter table if exists public.phemas enable row level security;
alter table if exists public.plaza_tokens enable row level security;
