# Codex Task 2

## Goal

Implement catalog loading and reference resolution for the Attas Pulse Definition Specification (PDS).

This task builds on the first validation task. It should make the system able to load a `pulse_catalog`, resolve the resources it references, and return a usable in-memory bundle while preserving the separation between definitions, profiles, mappings, and catalogs.

---

## Read first

Before changing code, read these files:

- `AGENTS.md`
- `docs/spec/pulse-definition-spec.md`
- `docs/architecture/attas-overview.md`
- `schemas/pds.schema.json`
- `examples/pulses/finance-core.catalog.json`
- `examples/pulses/`
- `tests/pds-validation-cases.md`

If Task 1 already introduced typed models and validation utilities, review those first and reuse them.

---

## Scope

Implement support for:

- loading a `pulse_catalog`
- resolving each `items[].ref`
- optionally reading `imports`
- returning a typed catalog bundle
- reporting missing or invalid referenced resources clearly

Keep this task focused on loading and resolution.

Do not build full execution logic, dependency graphs, or application-specific business behavior in this task.

---

## Requirements

### 1. Add a catalog loader

Create a loader that can:

- read a catalog JSON file
- validate it against `schemas/pds.schema.json`
- collect referenced resource IDs from:
  - `items`
  - optionally `imports`
- resolve those IDs to actual resource files or objects

The loader should return a structured result, not just raw JSON.

A good result shape would include:

- the validated catalog
- resolved resource objects
- unresolved references
- validation or resolution diagnostics

---

### 2. Keep resource types distinct after loading

When a catalog is resolved, the implementation must preserve the distinction between:

- `pulse_definition`
- `pulse_profile`
- `pulse_mapping`
- `pulse_catalog`

Do not flatten everything into one untyped array if the codebase can avoid it.

A practical structure could group resolved resources by type, for example:

- definitions
- profiles
- mappings
- nested catalogs

---

### 3. Reference resolution rules

Implement clear rules for reference resolution.

At minimum:

- `items[].ref` should resolve to a known PDS resource ID
- duplicate references should not produce duplicate loaded resources unless the current architecture requires it
- unresolved references should be reported explicitly
- invalid referenced files should fail validation before being treated as resolved resources

For this task, simple deterministic resolution is enough.

Examples of acceptable strategies:

- index all example resources by `id`
- resolve from a configured directory
- resolve from a manifest built at startup

Do not hardcode one vendor or one domain into the resolution logic.

---

### 4. Support import handling conservatively

If `imports` are present in a catalog:

- parse them
- expose them in the loader result
- attempt resolution if there is an obvious local mechanism
- report unresolved imports clearly if they cannot be resolved

Do not invent a complex package manager in this task.

A minimal import mechanism is enough.

---

### 5. Add tests

Add automated tests for catalog loading behavior.

At minimum, cover:

- valid catalog loads successfully
- all referenced example resources in `finance-core.catalog.json` resolve correctly
- unresolved reference produces a structured error
- invalid referenced resource is rejected if resolution tries to load it as a valid PDS resource
- duplicate refs do not cause unstable behavior

If helpful, add a small synthetic test catalog fixture for unresolved reference scenarios.

---

## Deliverables

A complete result should include, where appropriate:

- catalog loading utility
- reference resolution utility
- structured diagnostics for missing refs
- tests for successful and failing resolution
- minimal documentation update if new loader behavior needs explanation

---

## Suggested implementation plan

1. Reuse the Task 1 validator and typed models.
2. Add a resource indexing strategy keyed by `id`.
3. Implement catalog parsing and validation.
4. Implement reference resolution for `items`.
5. Add conservative support for `imports`.
6. Add tests for success and failure paths.
7. Summarize changed files and unresolved questions.

---

## Constraints

- Do not merge profiles or mappings into base Pulse definitions during loading.
- Do not assume imported catalogs are always locally available.
- Do not silently ignore unresolved references.
- Do not treat external references inside `interop` as local resource refs.
- Do not over-engineer distribution or remote registry logic in this task.

---

## Output requested from Codex

At the end, provide:

1. a concise summary of what changed
2. the list of changed files
3. whether the catalog loader is backward compatible with Task 1 resources
4. any unresolved design questions for package resolution or catalog composition

---

## Optional stretch goal

If the repository structure makes it easy, add one convenience helper that:

- loads all PDS resources from a directory
- builds an ID index
- validates each resource
- resolves one named catalog into a structured bundle

Keep it small and generic.
