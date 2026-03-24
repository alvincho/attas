-- Supabase migration for Plaza storage tables
-- Run in Supabase SQL Editor (or via supabase migration tooling).

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
    pulse_name text not null,
    pulse_address text not null,
    pulser_id text not null,
    pulser_name text not null,
    pulser_address text,
    input_schema jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_pulse_pulser_pairs_pulse_name
    on public.pulse_pulser_pairs (pulse_name);

create index if not exists idx_pulse_pulser_pairs_pulse_address
    on public.pulse_pulser_pairs (pulse_address);

create index if not exists idx_pulse_pulser_pairs_pulser_id
    on public.pulse_pulser_pairs (pulser_id);

create index if not exists idx_pulse_pulser_pairs_updated_at
    on public.pulse_pulser_pairs (updated_at desc);

create table if not exists public.plaza_ui_users (
    id text primary key,
    email text not null,
    display_name text,
    role text not null default 'user',
    status text not null default 'active',
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    last_sign_in_at timestamptz
);

create index if not exists idx_plaza_ui_users_email
    on public.plaza_ui_users (email);

create index if not exists idx_plaza_ui_users_role
    on public.plaza_ui_users (role);

create index if not exists idx_plaza_ui_users_status
    on public.plaza_ui_users (status);

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
