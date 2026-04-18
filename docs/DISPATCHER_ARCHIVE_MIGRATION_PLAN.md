# Dispatcher Archive Migration Plan

## Goal

Keep dispatcher hot tables small enough for dashboard and worker-health reads, while preserving recent operational history for diagnostics.

## Scope

Daily Job Archive owns these movements:

- `dispatcher_jobs` -> `dispatcher_jobs_archive` for completed jobs.
- `dispatcher_worker_history` -> `dispatcher_worker_history_archive` for heartbeat/session rows older than the hot-window cutoff.
- `dispatcher_job_results` -> `dispatcher_job_results_archive` for generic result rows older than the hot-window cutoff.
- `dispatcher_raw_payloads` -> `dispatcher_raw_payloads_archive` for raw payload rows older than the hot-window cutoff.

`dispatcher_worker_capabilities` stays active only. It is the latest worker state table, not an append-only history table.

## Default Policy

- Daily archive: move related append-only rows older than 24 hours.
- Monthly cleanup: purge archive rows older than 30 days.
- Batches are bounded so a scheduled run does not monopolize the database.

## Migration Steps

1. Deploy schema support for the three new archive tables and their timestamp indexes.
2. Restart the dispatcher archive-capable worker so it loads the updated `DailyJobArchiveJobCap`.
3. Seed or update the scheduled jobs:
   - Daily archive at 03:00 for completed jobs plus append-only telemetry older than 24 hours.
   - Monthly cleanup on day 1 at 04:00 Asia/Taipei for archive rows older than 30 days.
4. Backfill existing oversized history in controlled batches by issuing the Daily Job Archive capability with a larger `related_table_batch_size`.
5. Verify hot-table sizes fall and dashboard worker reads stay fast.
6. After 30 days, verify monthly cleanup purges old archive rows without affecting current worker state.

## Verification Queries

```sql
select 'dispatcher_worker_history' as table_name, count(*) from dispatcher_worker_history
union all
select 'dispatcher_worker_history_archive', count(*) from dispatcher_worker_history_archive
union all
select 'dispatcher_job_results', count(*) from dispatcher_job_results
union all
select 'dispatcher_job_results_archive', count(*) from dispatcher_job_results_archive
union all
select 'dispatcher_raw_payloads', count(*) from dispatcher_raw_payloads
union all
select 'dispatcher_raw_payloads_archive', count(*) from dispatcher_raw_payloads_archive;
```

```sql
select event_type, count(*)
from dispatcher_worker_history
group by event_type
order by count(*) desc;
```

## Rollback

If a problem appears, stop the Daily Job Archive schedule and move rows back from archive tables using the same primary keys. The archive tables preserve the original row columns plus `archived_at`, so rollback is a straight insert back into the active table followed by deleting the archive copy.
