# Roadmap

This document tracks the short-term public priorities for FinMAS.

## Current Priorities

- keep the fresh-clone path reliable and easy to test
- improve local-first setup and onboarding
- reduce mutable fixture state in `tests/storage/`
- clarify which components are experimental versus recommended starting points
- keep the public repo minimal and free of local-only runtime artifacts

## Near-Term Focus

- stronger public quickstart documentation
- more public-friendly smoke coverage
- cleaner separation between local examples and private or cloud-backed configs
- clearer maturity notes across `prompits`, `attas`, `phemacast`, and `ads`

## Planned Prompits Platform Features

- Plaza-backed authentication and permissions for `UsePractice(...)` calls across
  agents in `prompits`
- a pre-execution `prompits` workflow where agents can negotiate cost, confirm
  payment terms, and complete payment before executing `UsePractice(...)`
- clearer trust, access, and economic boundaries for cross-agent collaboration in
  `prompits`

## Planned Phemacast Features

- more `Phemar` agents for representing human intelligence, judgment, and structured
  interpretation
- more `Castr` agents for producing output from a `Phema` in formats such as PDS,
  PPTX, web pages, and multimedia
- AI-generated `Pulse` creation and refinement based on human feedback, runtime
  efficiency, and cost
- broader diagram support in `MapPhemar`

## Planned Attas Features

- more investment and treasury-operation workflows for collaboration inside an
  organization and across organizations
- fine-tuned agent models designed to represent financial professionals more
  accurately
- automatic mapping from API endpoints to `Pulse` definitions for data vendors and
  service providers

## Not A Promise

This roadmap is directional, not a guarantee. The repository is still experimental,
and priorities may move as the codebase is split, stabilized, or packaged more
formally.
