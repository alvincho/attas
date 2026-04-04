# Attas Data Services

Attas Data Services (`ads`) is a lightweight data-services backend for the existing `prompits` and `phemacast` runtimes. It now includes three concrete building blocks:

- `ADSDispatcherAgent`: queue-backed dispatcher for collection jobs
- `ADSWorkerAgent`: collector worker that polls for matching jobs and reports results
- `ADSPulser`: pulser that serves normalized ADS tables as Plaza pulses
- `ADSBossAgent`: operator UI that issues jobs to the dispatcher

## Coverage

The current normalized dataset tables are:

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

The dispatcher also manages:

- `ads_jobs`
- `ads_worker_capabilities`

The implementation uses `ads_` table prefixes rather than literal `ads-*` names so the same identifiers work cleanly across SQLite, Postgres, and Supabase-backed SQL.

## Runtime shape

Dispatcher:

- is a `prompits` agent
- owns the shared queue and normalized storage tables
- exposes `ads-submit-job`, `ads-get-job`, `ads-register-worker`, and `ads-post-job-result`
- hands workers a typed `JobDetail` payload when they claim work
- accepts a typed `JobResult` payload to finalize jobs and persist collected rows plus raw payloads

Worker:

- is a `prompits` agent
- advertises its capabilities through agent metadata and the dispatcher capability table
- loads `job_capabilities` from config and registers those capability names on Plaza metadata
- uses `JobCap` objects as the default execution path for claimed jobs
- can run once or in a polling loop, defaulting to a 10 second interval
- accepts either an overridden `process_job()` or an external handler callback

Pulser:

- is a `phemacast` pulser
- reads normalized ADS tables from the shared pool
- exposes pulses for security master, daily prices, fundamentals, statements, news, and raw payload lookup

## Files

- `ads/agents.py`: dispatcher and worker agents
- `ads/jobcap.py`: `JobCap` abstraction and callable-backed capability loader
- `ads/models.py`: `JobDetail` and `JobResult`
- `ads/pulser.py`: ADS pulser implementation
- `ads/boss.py`: boss operator UI agent
- `ads/practices.py`: dispatcher practices
- `ads/schema.py`: shared table schemas
- `ads/iex.py`: IEX end-of-day job capability
- `ads/twse.py`: Taiwan Stock Exchange end-of-day job capability
- `ads/rss_news.py`: multi-feed RSS news collection capability
- `ads/sec.py`: SEC EDGAR bulk raw import and per-company mapping capabilities
- `ads/us_listed.py`: Nasdaq Trader U.S. listed security master capability
- `ads/yfinance.py`: Yahoo Finance end-of-day job capability
- `ads/runtime.py`: normalization helpers
- `ads/configs/*.agent`: example ADS configs
- `ads/sql/ads_tables.sql`: Postgres/Supabase DDL

## Local examples

The shipped ADS configs now assume a shared PostgreSQL database. Set
`POSTGRES_DSN` or `DATABASE_URL` before starting the agents. You can optionally
set `ADS_POSTGRES_SCHEMA` to use a schema other than `public`, and
`ADS_POSTGRES_SSLMODE` to override the default local-friendly `disable`
behavior when you need SSL for managed PostgreSQL.

Start the dispatcher:

```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

Start a worker:

```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

The sample worker config ships a live `US Listed Sec to security master` capability backed by
`ads.us_listed:USListedSecJobCap`, mock handlers for `fundamentals`,
`financial_statements`, and `news`, and uses
`ads.sec:USFilingBulkJobCap` named `US Filing Bulk`,
`ads.sec:USFilingMappingJobCap` named `US Filing Mapping`,
`ads.yfinance:YFinanceEODJobCap` named `YFinance EOD`,
`ads.yfinance:YFinanceUSMarketEODJobCap` named `YFinance US Market EOD`, plus
`ads.twse:TWSEMarketEODJobCap` named `TWSE Market EOD` for live end-of-day collection,
and `ads.rss_news:RSSNewsJobCap` named `RSS News` for multi-feed news collection.
`YFinance EOD` uses the installed `yfinance` module and does not require a
separate API key. `YFinance US Market EOD` scans `ads_security_master` for
active `USD` symbols, sorts them by `metadata.yfinance.eod_at`, updates that
timestamp symbol-by-symbol, and queues one-symbol `YFinance EOD` jobs so the
stalest names get refreshed first. `TWSE Market EOD` reads the official TWSE `MI_INDEX` daily
quotes report and stores the full market-wide quote table into normalized
`ads_daily_price` rows. When `ads_daily_price` is empty it bootstraps a short
recent window by default instead of attempting a multi-year full-market backfill;
use an explicit `start_date` if you want TWSE historical coverage. `USListedSecJobCap` reads Nasdaq Trader
symbol directory files `nasdaqlisted.txt` and `otherlisted.txt`, prefers the web-hosted
`https://www.nasdaqtrader.com/dynamic/SymDir/` copies with FTP fallback, filters out test symbols, and upserts
the current U.S. listed universe into `ads_security_master`. `RSS News` pulls
the configured SEC, CFTC, and BLS feeds in one job and stores normalized feed
entries in `ads_news`. `US Filing Bulk` downloads the nightly SEC EDGAR
`companyfacts.zip` and `submissions.zip` archives, writes raw per-company JSON
rows into `ads_sec_companyfacts` and `ads_sec_submissions`, and sends a
declared SEC `User-Agent` header. `US Filing Mapping` reads one company from
those raw SEC tables and maps it into `ads_fundamentals` plus
`ads_financial_statements` when a symbol is available in submissions metadata.

Start the pulser:

```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

Start the boss UI:

```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

The boss UI now includes a live Plaza connection strip at the top of the page,
an `Issue Job` page, a `/monitor` view for browsing queued, claimed,
completed, and failed ADS jobs plus their raw payload records, and a
`Settings` page for boss-side dispatcher defaults and monitor refresh
preferences.

## Notes

- The shipped example configs use `PostgresPool` so dispatcher, workers, pulser, and boss all point at the same ADS database instead of per-agent SQLite files.
- `PostgresPool` resolves connection settings from `POSTGRES_DSN`, `DATABASE_URL`, `SUPABASE_DB_URL`, or standard libpq `PG*` environment variables.
- `ads/configs/boss.agent`, `ads/configs/dispatcher.agent`, and `ads/configs/worker.agent` should stay aligned when new JobCaps are introduced; the shipped configs expose `US Listed Sec to security master`, `US Filing Bulk`, `US Filing Mapping`, `YFinance EOD`, `YFinance US Market EOD`, `TWSE Market EOD`, and `RSS News`.
- Worker configs can declare `ads.job_capabilities` entries with a capability name and callable path such as `ads.examples.job_caps:mock_daily_price_cap`.
- Worker configs can also declare class-based capabilities with `type`, for example `ads.iex:IEXEODJobCap`, `ads.rss_news:RSSNewsJobCap`, `ads.sec:USFilingBulkJobCap`, `ads.sec:USFilingMappingJobCap`, `ads.twse:TWSEMarketEODJobCap`, `ads.us_listed:USListedSecJobCap`, or `ads.yfinance:YFinanceEODJobCap`, which return normalized rows plus raw payloads for dispatcher persistence.
- Worker `ads.job_capabilities` entries support `disabled: true` to temporarily disable a configured job cap without deleting its configuration entry.
- Worker configs can set `ads.yfinance_request_cooldown_sec` (default `120`) so a worker temporarily stops advertising YFinance-related capabilities after a Yahoo rate-limit response.
- `ads/sql/ads_tables.sql` is included for Postgres or Supabase deployments.
- Dispatcher and worker default to a shared local direct token so remote `UsePractice(...)` calls work on one machine even before Plaza auth is configured.
- All three components fit the existing repo conventions, so they can still participate in Plaza registration and remote `UsePractice(...)` calls when configured to do so.
