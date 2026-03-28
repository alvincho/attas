-- Immediate RLS hardening for the Plaza Supabase project.
-- Run this once in the Supabase SQL Editor for project shwjdbugjabdgybzdhws.
--
-- These Plaza tables are intended for server-side access. After enabling RLS,
-- make sure the Plaza backend uses the service-role key for pool operations.

alter table if exists public.plaza_credentials enable row level security;
alter table if exists public.plaza_login_history enable row level security;
alter table if exists public.plaza_directory enable row level security;
alter table if exists public.agent_practices enable row level security;
alter table if exists public.pulse_pulser_pairs enable row level security;
alter table if exists public.plaza_ui_users enable row level security;
alter table if exists public.phemas enable row level security;
alter table if exists public.plaza_tokens enable row level security;

select schemaname, tablename, rowsecurity
from pg_tables
where schemaname = 'public'
  and tablename in (
    'agent_practices',
    'phemas',
    'plaza_credentials',
    'plaza_directory',
    'plaza_login_history',
    'plaza_tokens',
    'plaza_ui_users',
    'pulse_pulser_pairs'
  )
order by tablename;
