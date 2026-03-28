# Codex Task 1

## Goal

Implement the first working foundation for the Attas Pulse Definition Specification (PDS).

This task should add the minimum code needed to load, type, and validate PDS resources without introducing Attas-specific assumptions into the core model.

---

## Read first

Before changing code, read these files:

- `AGENTS.md`
- `docs/spec/pulse-definition-spec.md`
- `docs/architecture/attas-overview.md`
- `schemas/pds.schema.json`
- `examples/pulses/`
- `tests/pds-validation-cases.md`

These files define the intended meaning of Pulses and the separation between definitions, profiles, mappings, and catalogs.

---

## Scope

Implement support for these four resource types:

- `pulse_definition`
- `pulse_profile`
- `pulse_mapping`
- `pulse_catalog`

Keep the implementation focused on parsing, typing, and validation.

Do not build full business logic, UI rendering, workflow execution, or vendor adapters in this task.

---

## Requirements

### 1. Add strongly typed models

Create language-appropriate models or types for:

- `pulse_definition`
- `pulse_profile`
- `pulse_mapping`
- `pulse_catalog`

The models should reflect the schema in `schemas/pds.schema.json`.

They should preserve the separation between:

- semantic meaning
- application-specific constraints
- external mappings
- resource packaging

Do not collapse all resource types into one loose untyped object unless the existing codebase makes that unavoidable.

---

### 2. Add schema validation

Wire the project to validate example JSON resources against:

- `schemas/pds.schema.json`

The validator should:

- load JSON files
- validate them individually
- expose readable validation errors
- preserve unknown extension fields where allowed by the schema

---

### 3. Add example validation coverage

Use the example resources in `examples/pulses/`.

Expected valid files:

- `last_trade.json`
- `revenue.json`
- `rsi.json`
- `rating_summary.json`
- `lseg-last-trade.mapping.json`
- `attas-equity-research-last-trade.profile.json`
- `finance-core.catalog.json`

Expected invalid file:

- `invalid-last-trade.missing-interface.json`

The test harness should assert that:

- valid resources pass
- invalid resources fail

---

### 4. Preserve architectural boundaries

Enforce these design rules in the implementation:

- base Pulse definitions remain application-neutral
- application-specific behavior belongs in profiles
- vendor-specific bindings belong in mappings
- catalogs only package references and metadata
- external references must not be assumed to be equivalent unless relation type says so
- unknown extensions must not break parsing when permitted by schema

---

### 5. Keep changes small and local

Do not refactor unrelated modules.

Do not invent a larger framework around PDS unless the current repository structure already supports it.

Prefer a narrow, well-tested first implementation.

---

## Deliverables

A complete result should include, where appropriate:

- typed models or interfaces
- JSON loading utilities
- schema validator wiring
- automated tests for pass/fail examples
- minimal documentation updates if implementation details need clarification

---

## Suggested implementation plan

1. Read the spec and examples.
2. Identify the code location for shared domain models.
3. Add models for the four PDS resource types.
4. Add a schema validator wrapper around `schemas/pds.schema.json`.
5. Add tests that walk the example files.
6. Confirm expected pass/fail behavior.
7. Summarize changed files and open questions.

---

## Constraints

- Do not hardcode LSEG or Bloomberg assumptions into core Pulse definition types.
- Do not move vendor mapping fields into `pulse_definition`.
- Do not change Pulse meaning under the same ID.
- Do not reject namespaced extensions simply because they are unfamiliar.
- Do not modify the example semantics unless the schema clearly requires it.

---

## Output requested from Codex

At the end, provide:

1. a concise summary of what changed
2. the list of changed files
3. whether the implementation is backward compatible
4. any spec ambiguities or follow-up work that should be addressed next

---

## Optional stretch goal

If the repository already has a clean place for it, add one convenience helper that:

- loads a JSON file
- determines its PDS resource type
- validates it
- returns the typed object or a structured validation error

Keep this helper small and generic.
