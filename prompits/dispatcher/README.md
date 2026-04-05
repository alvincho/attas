# Prompits Dispatcher

## Translations

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

`prompits.dispatcher` is the generalized queue-and-worker layer extracted from an older domain-specific service.
It keeps the reusable orchestration pieces and removes the old domain loaders,
schemas, and naming.

## Included pieces

- `DispatcherAgent`: queue-backed job dispatcher
- `DispatcherWorkerAgent`: worker that polls for matching jobs and reports results
- `DispatcherBossAgent`: browser UI for issuing jobs and inspecting runtime state
- `JobCap`: capability abstraction for pluggable job handlers
- shared practices, schemas, runtime helpers, and example configs

## Internal tables

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

If a worker returns rows for a concrete `target_table` and supplies a schema, the
dispatcher can create and persist that table too. If no schema is supplied, rows are
stored generically in `dispatcher_job_results`.

## Practices

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## Example usage

Start the dispatcher:

```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

Start a worker:

```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

Start the boss UI:

```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

The sample worker config uses a minimal example capability from
`prompits.dispatcher.examples.job_caps`.

## Notes

- The package defaults to a shared local direct token so `UsePractice(...)` calls work locally before Plaza auth is configured.
- The example configs use `PostgresPool`, but the tests also cover SQLite.
- The worker can advertise callable or class-based capabilities through the `dispatcher.job_capabilities` config section.
