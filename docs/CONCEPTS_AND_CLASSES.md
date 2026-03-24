# attas: Autonomous Trading and Treasury Agents System Concepts and Class Reference

This document describes the runtime concepts and production classes in `prompits` and `phemacast`.

## Core Concepts

- Pit: Smallest framework abstraction. Carries identity metadata (`name`, `description`, `meta`).
- Practice: Mountable and executable capability attached to an agent. Exposed as API endpoints and/or callable runtime methods.
- Agent: Runtime process that hosts a FastAPI app, manages practices, and can communicate with other agents.
- Message: Canonical envelope for agent-to-agent and agent-to-practice communication.
- Pool: Pluggable persistence backend used for credentials, registry data, and practice metadata.
- Schema: Validation/type layer used for pool table and payload structure definitions.
- Plaza: Coordination layer for registration, auth, search/discovery, heartbeat, and relaying.
- Phemacast: Multi-role content pipeline (Creator -> Pulser -> Phemar -> Castr) built on Prompits primitives.

## Class-by-Class Reference

### `prompits/core/pit.py`

- `Pit`
  - Purpose: Base metadata abstraction for framework building blocks.
  - Key fields: `name`, `description`, `meta`.
  - Notes: No behavior by design; used as a shared conceptual base.

### `prompits/core/practice.py`

- `Practice`
  - Purpose: Base class for agent capabilities.
  - Lifecycle:
    - Construct metadata (`id`, tags, input/output modes, parameters).
    - `bind(agent)` to gain agent context.
    - `mount(app)` to expose HTTP routes.
    - `execute(...)` for direct callable logic.
  - Important conventions:
    - `path` auto-derived from `id` (`-` -> `_`).
    - Metadata is used in agent cards and Plaza search results.

### `prompits/core/message.py`

- `Message`
  - Purpose: Typed communication envelope.
  - Key fields: `sender`, `receiver`, `content`, `msg_type`, `timestamp`, `metadata`.
  - Routing: `msg_type` is the primary dispatch key.

### `prompits/core/pool.py`

- `DataItem`
  - Purpose: Abstract typed persistence item with `to_dict()` contract.
- `Pool`
  - Purpose: Abstract persistence interface.
  - Required methods: `_CreateTable`, `_TableExists`, `_Insert`, `_Query`, `_GetTableData`.
  - Optional lifecycle: `connect`, `disconnect`.
  - Used by: agents (credentials/practices), Plaza state (directory/history), and tests.

### `prompits/core/schema.py`

- `DataType`
  - Purpose: Standard type enum and value validator.
  - Includes: scalar, temporal, JSON/object/array, graph/vector, null, etc.
- `Schema` (abstract)
  - Purpose: Common schema base with validation contract.
- `TableSchema`
  - Purpose: Table-level schema (name, description, primary key, row schema).
- `RowSchema`
  - Purpose: Per-row/column schema and row validation.
- `TupleSchema`
  - Purpose: Ordered tuple validation against typed item schema.
- `JsonSchema`
  - Purpose: JSON Schema-based validation via `jsonschema`.

### `prompits/pools/filesystem.py`

- `FileSystemPool`
  - Purpose: JSON-on-filesystem pool implementation.
  - Storage model:
    - Table = directory.
    - Row = JSON file (`<id>.json`, encoded safely for filenames).
  - Tradeoff: highly transparent/simple, less efficient for large scans.

### `prompits/pools/sqlite.py`

- `SQLitePool`
  - Purpose: SQLite-backed pool implementation.
  - Runtime behavior:
    - Opens DB in WAL mode with busy timeout.
    - Supports table create, insert/upsert, SQL query, filtered select.
    - Performs lightweight JSON auto-serialization/deserialization.

### `prompits/pools/supabase.py`

- `SupabasePool`
  - Purpose: Supabase/PostgREST-backed pool implementation.
  - Notes:
    - Table creation is out-of-band (SQL/dashboard migration flow).
    - `_Query` maps to Supabase RPC calls.
    - `_Insert` uses upsert semantics.

### `prompits/agents/base.py`

- `BaseAgent` (abstract)
  - Purpose: Shared runtime agent engine.
  - Responsibilities:
    - FastAPI host and route setup.
    - Practice mounting and metadata persistence.
    - Plaza registration/auth/renew/heartbeat lifecycle.
    - Peer lookup, message send, and local/remote practice invocation.
  - Identity concepts:
    - `agent_id`: stable identity issued by Plaza.
    - `api_key`: persistent credential for relogin.
    - `plaza_token`: short-lived bearer token.
    - `agent_address`: canonical `plaza://<plaza>#<agent_id>` target.

### `prompits/agents/standby.py`

- `StandbyAgent`
  - Purpose: General-purpose worker agent.
  - Behavior:
    - Handles inbound `Message`.
    - Routes by `msg_type` to mounted practices.
    - Includes example command flow (`handle_command`) for demo automation.

### `prompits/agents/user.py`

- `UserAgent`
  - Purpose: UI-facing agent with templates/static assets and helper APIs.
  - Routes:
    - `/` and `/plazas`: UI pages.
    - `/api/plazas_status`: Plaza health + directory status.
    - `/api/send_message`: UI-triggered messaging.
  - Special handling: retries/re-register logic if auth/search fails.

### `prompits/core/plaza.py`

- `PlazaAgent`
  - Purpose: Agent host role for Plaza service process.
  - Notes:
    - Core Plaza endpoints are supplied via `PlazaPractice` mount.
    - Exposes `/.well-known/agent-card` for self-description.

### `prompits/practices/chat.py`

- `ChatPractice`
  - Purpose: Unified LLM interaction practice.
  - Providers: `ollama`, `openai`.
  - Features:
    - `/chat` endpoint with message-forwarding behavior.
    - Model listing endpoint.
    - Agent-conditioned system prompt injection.
    - Ollama missing-model fallback to available model.

### `prompits/practices/plaza.py`

#### Request Models

- `RegisterRequest`: registration/relogin input payload.
- `RenewRequest`: token renewal payload.
- `RelayMessage`: relay target/payload/message-type envelope.
- `HeartbeatRequest`: heartbeat payload.
- `AuthenticateRequest`: credential login payload.

#### Persistence and State

- `PlazaCredentialStore`
  - Purpose: credential + login history persistence adapter.
  - Tables:
    - `plaza_credentials`
    - `plaza_login_history`
  - Safety: login-history writes are fail-open and never block core flow.

- `PlazaState`
  - Purpose: shared mutable runtime state across all Plaza endpoints.
  - Tracks:
    - registry/address mappings
    - token map and expiration
    - agent cards and pit types
    - credentials and login history
    - last heartbeat activity
    - optional durable directory table (`plaza_directory`)

#### Endpoint Practice Hierarchy

- `PlazaEndpointPractice`
  - Purpose: base endpoint-practice class bound to shared `PlazaState`.

- `PlazaRegisterPractice`
  - Purpose: issue new identities or accept credential relogin.
  - Side effects: updates registry, card store, credential persistence, login history, directory.

- `PlazaRenewPractice`
  - Purpose: rotate bearer token while preserving agent identity.

- `PlazaAuthenticatePractice`
  - Purpose: authenticate either by bearer token or (`agent_id`, `api_key`) pair.

- `PlazaHeartbeatPractice`
  - Purpose: authenticated heartbeat updates with identity consistency checks.

- `PlazaSearchPractice`
  - Purpose: directory search with filters (`name`, `agent_id`, `pit_type`, `practice`, etc.).
  - Data source order:
    - durable directory table when available,
    - in-memory state fallback otherwise.

- `PlazaRelayPractice`
  - Purpose: relay payloads between agents through Plaza.
  - Routing: uses `/chat` for `chat-practice`, else defaults to `/mailbox`.

- `PlazaPractice`
  - Purpose: composite bundle that mounts all Plaza endpoint practices.
  - Compatibility: mirrors state fields as direct attributes for existing callers/tests.

### `phemacast/models.py`

- `Persona`
  - Purpose: output voice profile (`name`, `tone`, `style`).
- `PhemaBlock`
  - Purpose: one templated render block with explicit binding keys.
- `Phema`
  - Purpose: blueprint of a castable narrative/data composition.
- `Pulse`
  - Purpose: timestamped payload from one pulse source.

### `phemacast/system.py`

- `CreatorAgent`
  - Purpose: creates `Phema` structures from prompt + binding list.
- `PulserAgent`
  - Purpose: fetches pulse data via `PulsePractice` providers.
- `PhemarAgent`
  - Purpose: binds pulse data into `PhemaBlock` templates.
- `CastrAgent`
  - Purpose: renders bound data into JSON/text/markdown outputs.
- `PhemacastSystem`
  - Purpose: orchestrates full pipeline and emits trace `Message`s per stage.
  - Pipeline flow:
    - create phema
    - gather pulse data
    - bind templates
    - cast viewer output
    - append trace events for observability

### `phemacast/agents/pulser.py`

- `Pulser`
  - Purpose: lightweight standby-agent shell for pulse-oriented runtime tasks.
  - Current state: minimal wrapper around `StandbyAgent`; intended for future expansion.

## Relationship Summary

- `BaseAgent` is the runtime hub. It mounts `Practice` instances and uses a `Pool` for persistence.
- `PlazaPractice` is a composite `Practice` whose sub-practices use one `PlazaState`.
- `UserAgent`, `StandbyAgent`, and `PlazaAgent` are concrete `BaseAgent` variants for different operational roles.
- `PhemacastSystem` is a higher-level orchestrator that uses Prompits message concepts to track multi-step collaboration.
