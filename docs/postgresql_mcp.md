# PostgreSQL MCP

This workspace now includes a local PostgreSQL MCP server at `mcp_servers/postgresql_server.py`.

## What it exposes

- `postgres_server_status`
- `postgres_list_tables`
- `postgres_describe_table`
- `postgres_query`
- `postgres_execute`

## Connection discovery

The server looks for connection settings in this order:

1. Tool call `dsn` override
2. `POSTGRES_DSN`
3. `DATABASE_URL`
4. `SUPABASE_DB_URL`
5. Standard libpq `PG*` variables such as `PGHOST`, `PGDATABASE`, and `PGUSER`

It also loads the workspace `.env` file automatically.

## Safety defaults

- `postgres_query` only accepts read-only SQL.
- `postgres_execute` only accepts a single statement at a time.
- `DROP`, `TRUNCATE`, and `DELETE` require `acknowledge_destructive=true`.
- `UPDATE` and `DELETE` require a `WHERE` clause unless `allow_full_table_write=true`.

## Codex config snippet

Add this block to `~/.codex/config.toml`:

```toml
[mcp_servers.postgresql]
command = "python3"
args = ["/Users/alvincho/Library/Mobile Documents/com~apple~CloudDocs/Documents/Projects/DevOps/Retis/FinMAS/mcp_servers/postgresql_server.py"]
```

If your database URL is not already available in the environment that launches Codex, add an env block too:

```toml
[mcp_servers.postgresql.env]
POSTGRES_DSN = "postgresql://USER:PASSWORD@HOST:5432/DBNAME"
```
