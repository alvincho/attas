# Prompits Concepts And Class Reference

This document is the detailed companion to [`prompits/README.md`](../prompits/README.md). It explains how the current Prompits runtime is structured, how the main objects interact, and where `phemacast` fits as a higher-level system built on the same primitives.

## Reading Guide

If you are new to the codebase, read this document in the following order:

1. Runtime lifecycle
2. Core concepts
3. Agent types
4. Plaza flows
5. Pool backends
6. Class-by-class reference

## Runtime Lifecycle

At a high level, a Prompits deployment works like this:

1. A config file is loaded by `prompits/create_agent.py`.
2. The configured agent class is instantiated with its primary pool.
3. `BaseAgent` creates the FastAPI app, registers the default `mailbox` endpoint, and exposes core routes.
4. Additional practices from config are imported and mounted.
5. If the agent has a `plaza_url` and is not Plaza itself, it registers on startup.
6. Plaza returns a stable `agent_id`, a persistent `api_key`, and a short-lived bearer token.
7. The agent saves credentials to its primary pool and starts a heartbeat loop.
8. Other agents discover it through Plaza search and can send messages or invoke practices remotely.

## Core Concepts

### Pit

The smallest conceptual building block. A `Pit` carries identity metadata such as `name`, `description`, and address information. In practice, `BaseAgent` inherits from `Pit` so every runtime agent participates in the same identity model.

### Practice

A practice is a capability mounted onto an agent. It has:

- metadata for discovery and UI rendering
- a `mount(app)` hook for HTTP routes
- an `execute(...)` method for direct local calls
- optional agent binding through `bind(agent)`

Practices are the main unit of extension in Prompits.

### Message

`Message` is the common envelope for inter-agent communication. Message-style communication is lightweight and flexible. It is different from remote practice invocation, which is more structured and verified.

### Pool

A pool is the persistence boundary. Agents use pools to:

- persist Plaza credentials
- persist discovered practice metadata
- store domain data or memory
- back Plaza directory and related state

### Plaza

Plaza is the coordination plane. It is implemented as a concrete agent host plus a mounted practice bundle, and it manages identity, search, liveness, and relay behaviors.

## Agent Types

### `BaseAgent`

`BaseAgent` is the runtime hub for the framework. Its responsibilities include:

- creating and configuring the FastAPI app
- mounting practices
- storing and reloading practice metadata
- registering with Plaza
- renewing tokens and sending heartbeats
- discovering peers through Plaza search
- invoking local or remote practices

Important identity fields:

- `agent_id`: stable identity issued by Plaza
- `api_key`: long-lived credential used for relogin
- `plaza_token`: short-lived bearer token for Plaza-authenticated operations
- `pit_address`: normalized agent address object used in remote practice verification

### `StandbyAgent`

`StandbyAgent` is the default worker runtime. It adds:

- message handling through `receive(...)`
- basic command-oriented demo logic
- generic routing of incoming messages to practices by `msg_type`

Use `StandbyAgent` when you want a simple networked worker that can host practices.

### `UserAgent`

`UserAgent` is a browser-facing shell over Plaza discovery and messaging. It adds:

- HTML routes for the Plaza UI
- `/api/plazas_status` for frontend polling
- `/api/send_message` for browser-triggered message dispatch

Use it when you want a lightweight dashboard or operator UI.

### `PlazaAgent`

`PlazaAgent` is the concrete host for Plaza service runtime. It adds:

- Plaza-specific templates and static assets
- status APIs for registry and UI workflows
- phema-related UI routes

Its actual registration, auth, heartbeat, search, and relay APIs are supplied by `PlazaPractice`.

## Plaza Flows

### Registration

An agent sends `POST /register` with its name, address, card metadata, and optional prior credentials. Plaza either:

- issues a new identity and token, or
- accepts an existing `agent_id` and `api_key` pair for relogin

### Renewal

Agents use `POST /renew` to rotate a Plaza bearer token before expiry.

### Authentication

`POST /authenticate` validates a bearer token.

Agent relogin continues to go through `POST /register` with an existing `agent_id` and `api_key` pair. Remote practice verification uses bearer-token validation through `/authenticate`.

### Heartbeat

Agents periodically send `POST /heartbeat` so Plaza can maintain activity state.

### Search

`GET /search` exposes Plaza's searchable directory of registered agent cards. Filters include:

- `name`
- `agent_id`
- `pit_type`
- `practice`
- `role`
- other metadata fields

### Relay

`POST /relay` forwards messages through Plaza. The routing behavior is:

- a practice-specific path when the receiver advertises that practice
- `/mailbox` as the default for generic message flows

## Remote Practice Invocation

Prompits supports direct practice execution across agents through:

- `BaseAgent.UsePractice(...)`
- `BaseAgent.UsePracticeAsync(...)`
- `POST /use_practice/{practice_id}`

Verification path:

1. Caller resolves the target through `PitAddress` and Plaza search.
2. Caller includes its own `PitAddress` plus a Plaza token or direct shared token.
3. Receiver verifies the caller with Plaza `POST /authenticate`.
4. If verification succeeds, the receiver executes the requested practice and returns the result.

This flow is demonstrated throughout the pool and pulser tests, especially the remote `get_pulse_data` coverage in `phemacast/tests/`.

## Pool Backends

### `FileSystemPool`

Best for local development and transparent debugging.

- table = directory
- row = JSON file
- easy to inspect by hand
- weaker for large scans and complex queries

### `SQLitePool`

Best for single-node persistence with stronger query behavior than the filesystem backend.

- SQLite database with WAL mode
- busy timeout support
- JSON value serialization helpers

### `SupabasePool`

Best when Plaza or agents need hosted relational storage.

- uses Supabase/PostgREST
- table creation is handled outside the runtime
- supports upsert and RPC-style query patterns

## Prompits vs. Phemacast

Prompits is the infrastructure layer.

Phemacast is a higher-level multi-role content pipeline built on top of Prompits ideas and message semantics. It introduces domain-specific agents such as:

- `CreatorAgent`
- `PulserAgent`
- `PhemarAgent`
- `CastrAgent`

If you are releasing Prompits as open source, it helps to present `phemacast` as an example system or reference application rather than part of the minimum mental model.

## Class-By-Class Reference

### `prompits/core/pit.py`

- `Pit`
  - Purpose: base metadata abstraction for framework building blocks.
  - Key fields: `name`, `description`, `meta`.
  - Notes: behavior-light by design; used as a shared conceptual base.

### `prompits/core/practice.py`

- `Practice`
  - Purpose: base class for agent capabilities.
  - Lifecycle:
    - create metadata such as `id`, tags, input/output modes, and parameters
    - `bind(agent)` to gain runtime context
    - `mount(app)` to expose HTTP routes
    - `execute(...)` for direct callable logic
  - Important conventions:
    - `path` is usually derived from `id`
    - metadata is surfaced in Plaza search results and agent cards

### `prompits/core/message.py`

- `Message`
  - Purpose: typed communication envelope.
  - Key fields: `sender`, `receiver`, `content`, `msg_type`, `timestamp`, `metadata`.
  - Routing: `msg_type` is the main dispatch key.

### `prompits/core/pool.py`

- `DataItem`
  - Purpose: abstract typed persistence item with `to_dict()` contract.
- `Pool`
  - Purpose: abstract persistence interface.
  - Required methods: `_CreateTable`, `_TableExists`, `_Insert`, `_Query`, `_GetTableData`.
  - Optional lifecycle: `connect`, `disconnect`.
  - Used by: agents, Plaza state, credentials, practice metadata, and tests.

### `prompits/core/schema.py`

- `DataType`
  - Purpose: standard type enum and value validator.
- `Schema`
  - Purpose: common schema base with validation contract.
- `TableSchema`
  - Purpose: table-level schema.
- `RowSchema`
  - Purpose: row and column validation.
- `TupleSchema`
  - Purpose: ordered tuple validation.
- `JsonSchema`
  - Purpose: JSON Schema-based validation via `jsonschema`.

### `prompits/pools/filesystem.py`

- `FileSystemPool`
  - Purpose: JSON-on-filesystem pool implementation.
  - Storage model:
    - table = directory
    - row = JSON file named from the encoded record id
  - Tradeoff: transparent and portable, but not optimized for heavy query workloads.

### `prompits/pools/sqlite.py`

- `SQLitePool`
  - Purpose: SQLite-backed pool implementation.
  - Runtime behavior:
    - enables WAL mode
    - supports table creation, insert/upsert, filtered reads, and SQL queries
    - serializes JSON-like values automatically when needed

### `prompits/pools/supabase.py`

- `SupabasePool`
  - Purpose: Supabase/PostgREST-backed pool implementation.
  - Notes:
    - schema creation is expected outside the runtime
    - `_Query` maps to RPC calls
    - `_Insert` uses upsert semantics

### `prompits/agents/base.py`

- `BaseAgent`
  - Purpose: shared runtime engine.
  - Responsibilities:
    - FastAPI host and route setup
    - practice mounting and metadata persistence
    - Plaza registration, auth, token renewal, and heartbeat lifecycle
    - peer lookup, message sending, and local/remote practice invocation
  - Core routes:
    - `GET /health`
    - `POST /use_practice/{practice_id}`

### `prompits/agents/standby.py`

- `StandbyAgent`
  - Purpose: general-purpose worker agent.
  - Behavior:
    - handles inbound `Message`
    - routes by `msg_type` to mounted practices
    - includes simple command parsing for demos

### `prompits/agents/user.py`

- `UserAgent`
  - Purpose: UI-facing agent with templates, static assets, and helper APIs.
  - Routes:
    - `/`
    - `/plazas`
    - `/api/plazas_status`
    - `/api/send_message`
  - Special handling:
    - retries or re-registers if Plaza search fails due to missing auth or missing directory presence

### `prompits/core/plaza.py`

- `PlazaAgent`
  - Purpose: agent host for Plaza service runtime.
  - Notes:
    - Plaza endpoints are supplied via `PlazaPractice`
    - exposes `/.well-known/agent-card`
    - serves Plaza UI and related editor pages

### `prompits/practices/embeddings.py`

- `EmbeddingsPractice`
  - Purpose: vector embedding generation through Ollama or OpenAI-style APIs.
  - Typical use:
    - semantic retrieval
    - indexing
    - hybrid RAG experiments

### `prompits/practices/plaza.py`

#### Request Models

- `RegisterRequest`: registration or relogin payload.
- `RenewRequest`: token renewal payload.
- `RelayMessage`: relay envelope.
- `HeartbeatRequest`: heartbeat payload.

#### Persistence and State

- `PlazaCredentialStore`
  - Purpose: persistence adapter for credentials and login history.
  - Tables:
    - `plaza_credentials`
    - `plaza_login_history`

- `PlazaState`
  - Purpose: shared mutable runtime state across Plaza endpoints.
  - Tracks:
    - registry and address mappings
    - token map and expiration
    - agent cards and pit types
    - credential and login history
    - heartbeat activity
    - durable directory and pulse-pulser tables when backed by a pool

#### Endpoint Practice Hierarchy

- `PlazaEndpointPractice`
  - Purpose: base endpoint-practice class bound to shared `PlazaState`.

- `PlazaRegisterPractice`
  - Purpose: issue new identities or accept credential relogin.

- `PlazaRenewPractice`
  - Purpose: rotate bearer tokens while preserving identity.

- `PlazaAuthenticatePractice`
  - Purpose: authenticate by bearer token or credential pair.

- `PlazaHeartbeatPractice`
  - Purpose: authenticated heartbeat updates.

- `PlazaSearchPractice`
  - Purpose: directory search with filters such as `name`, `agent_id`, `pit_type`, and `practice`.

- `PlazaRelayPractice`
  - Purpose: relay payloads between agents through Plaza.

- `PlazaPractice`
  - Purpose: composite practice that mounts the full Plaza endpoint set.

### `phemacast/models.py`

- `Persona`
  - Purpose: output voice profile.
- `PhemaBlock`
  - Purpose: one templated render block with explicit bindings.
- `Phema`
  - Purpose: blueprint for a castable narrative or data composition.
- `Pulse`
  - Purpose: timestamped payload from one source.

### `phemacast/system.py`

- `CreatorAgent`
  - Purpose: create `Phema` structures from prompts.
- `PulserAgent`
  - Purpose: fetch pulse data through pulse providers.
- `PhemarAgent`
  - Purpose: bind pulse data into template blocks.
- `CastrAgent`
  - Purpose: render bound data into final output formats.
- `PhemacastSystem`
  - Purpose: orchestrate the full pipeline and emit trace messages.

## Relationship Summary

- `BaseAgent` is the runtime center of Prompits.
- `Practice` is the extension point attached to an agent.
- `Pool` is the persistence boundary.
- `PlazaPractice` is a composite practice that implements the coordination plane.
- `StandbyAgent`, `UserAgent`, and `PlazaAgent` are specialized runtime shells over `BaseAgent`.
- `PhemacastSystem` demonstrates how a higher-level, multi-stage application can be built on top of these primitives.
