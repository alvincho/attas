# FinMAS

FinMAS is an experimental multi-agent workspace for financial intelligence systems.

The repository currently combines several related codebases:

- `prompits`: Python infrastructure for HTTP-native agents, Plaza discovery, pools, and remote practice execution
- `phemacast`: a collaborative content pipeline built on Prompits
- `attas`: higher-level finance-oriented agent patterns and pulse definitions
- `ads`: data-service and collection components that feed normalized finance datasets into the wider system

## Status

This repository is actively developed and still evolving. APIs, config formats, and
example flows may change as the projects are split, stabilized, or packaged more
formally.

The public repo is meant for:

- local development
- experimentation
- prototype workflows
- architecture exploration

It is not yet a polished turnkey product or a one-command production deployment.

## Fresh Clone Quickstart

From a brand-new checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

The smoke script clones the committed repo state into a temporary directory, creates
its own virtualenv, installs dependencies, and runs a focused public-facing test
suite. This is the closest approximation of what a GitHub user will actually pull.

If you want to test your latest uncommitted local changes instead, use:

```bash
attas_smoke --worktree
```

That mode copies the current working tree, including uncommitted changes and
untracked non-ignored files, into the temporary test directory.

From the repo root, you can also run:

```bash
bash attas_smoke
```

From any subdirectory inside the repo tree, you can run:

```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

That launcher finds the repo root and starts the same smoke flow. If you symlink
`attas_smoke` into a directory on your `PATH`, you can also call it as
a reusable command from anywhere and optionally set `FINMAS_REPO_ROOT` when working
outside the repo tree.

## Local-First Quickstart

The safest local path today is the Prompits example stack. It does not require
Supabase or other private infrastructure.

Terminal 1:

```bash
bash run_plaza_local.sh
```

Terminal 2:

```bash
python3 prompits/create_agent.py --config prompits/examples/worker.agent
```

Terminal 3:

```bash
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Then open `http://127.0.0.1:8214/`.

If you want the older Supabase-backed Plaza setup, point `PROMPITS_AGENT_CONFIG` at
`attas/configs/plaza.agent` and provide the required environment variables.

## Repository Layout

```text
attas/       Finance-oriented agent, pulse, and personal-agent work
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## Getting Oriented

- Start with `prompits/README.md` for the core runtime model.
- Read `phemacast/README.md` for the content pipeline layer.
- Read `attas/README.md` for the finance-network framing and higher-level concepts.
- Read `ads/README.md` for the data-service components.

## Component Status

| Area | Current Public Status | Notes |
| --- | --- | --- |
| `prompits` | Best starting point | Local-first examples and core runtime are the easiest public entry point. |
| `attas` | Experimental | Core concepts and user-agent work are public, but some unfinished components are intentionally hidden from the default flow. |
| `phemacast` | Experimental | Core pipeline code is public; some reporting/rendering components are still being trimmed and stabilized. |
| `ads` | Advanced | Useful for development and research, but some data workflows require extra setup and are not a first-run path. |
| `deploy/` | Example-only | Deployment helpers are environment-specific and should not be treated as a polished public deployment story. |
| `mcp_servers/` | Public source | Local MCP server implementations are part of the public source tree. |

## Known Limitations

- Some workflows still assume optional environment variables or third-party services.
- `tests/storage/` contains useful fixtures, but it still mixes deterministic test data
  with more mutable local-style state than an ideal public fixture set.
- Deployment scripts are examples, not a supported production platform.
- The repository is evolving quickly, so some configs and module boundaries may change.

## Roadmap

The short-term public roadmap is tracked in `docs/ROADMAP.md`.

Planned `prompits` capabilities include authenticated and permissioned
`UsePractice(...)` calls between agents, with cost negotiation and payment handling
before execution.

Planned `phemacast` capabilities include richer `Phemar` representations of human
intelligence, broader `Castr` output formats, and AI-generated `Pulse` refinement
based on feedback, efficiency, and cost, plus broader diagram support in
`MapPhemar`.

Planned `attas` capabilities include more collaborative investment and treasury
workflows, agent models tuned for financial professionals, and automatic API
endpoint-to-`Pulse` mapping for vendors and service providers.

## Public Repo Notes

- Secrets are expected to come from environment variables and local config, not committed files.
- Local databases, browser artifacts, and scratch snapshots are intentionally excluded from version control.
- The codebase currently targets experimentation, local development, and prototype workflows more than polished end-user packaging.

## Contributing

This is currently a public repo with a single primary maintainer. Issues and pull
requests are welcome, but roadmap and merge decisions remain maintainer-driven for
now. See `CONTRIBUTING.md` for the current workflow.

## License

This repository is licensed under the Apache License 2.0. See `LICENSE` for the full text.
