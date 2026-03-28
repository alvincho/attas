# AGENTS.md

## Purpose

This repository builds **Attas**, a system that uses **Pulses** as reusable semantic contracts across financial and non-financial applications.

A Pulse is not just a vendor field. A Pulse may represent:

- a canonical fact
- a derived analytic
- a report or narrative artifact

The codebase should preserve that distinction and keep the core Pulse model reusable beyond Attas.

---

## Read first

Before making changes, read these files when they exist:

- `docs/spec/pulse-definition-spec.md`
- `schemas/pds.schema.json`
- `docs/architecture/attas-overview.md`
- `examples/pulses/`

When working on a specific module, also read nearby documentation, tests, and existing patterns in that module before proposing structural changes.

---

## Product context

Attas uses Pulses as the semantic layer between:

- business meaning
- application behavior
- vendor/source mappings
- agent-to-agent interoperability

The system must support coexistence with:

- FIBO and other ontologies
- vendor dictionaries such as LSEG and Bloomberg
- internal legacy definitions
- future third-party application profiles

Do not design Pulses as if they are tied to one data vendor, one UI, one transport, or one product workflow.

---

## Core modeling rules

### 1. Keep base Pulse definitions portable

A base `pulse_definition` must describe the concept itself, not one application's preference.

Examples of portable meaning:

- last trade price
- revenue
- cash dividend
- implied volatility

Examples of non-portable details that do **not** belong in the base definition:

- a specific screen layout
- one vendor's field code
- one application's mandatory output fields
- one workflow's default parameters

Application-specific constraints belong in `pulse_profile`.

Vendor/source-specific bindings belong in `pulse_mapping`.

---

### 2. Preserve the resource split

The Pulse Definition Specification uses distinct resource types. Keep them separate.

- `pulse_definition` = semantic meaning + interface contract
- `pulse_profile` = application-specific constraints or defaults
- `pulse_mapping` = external system mapping
- `pulse_catalog` = package of reusable pulse resources

Do not collapse these into one large object unless the task explicitly requires a compatibility layer.

---

### 3. Coexist with external definitions

Attas Pulses must be able to coexist with, reference, or map to:

- FIBO
- vendor data dictionaries
- internal enterprise dictionaries
- public standards
- other applications' definitions

Do not assume Attas is the only source of truth.
Do not rename external concepts to hide their provenance.
Do not hardcode equivalence when the relationship is only approximate.

Use explicit relation types such as:

- `equivalent_match`
- `close_match`
- `broader_than`
- `narrower_than`
- `derived_from`
- `implements`
- `related`

---

### 4. Respect semantic stability

Pulse IDs are meaning-bound.

If the meaning materially changes, create a new Pulse ID instead of silently changing the existing one.

Examples of material semantic change:

- changing from last traded price to midpoint
- changing from instrument-level data to issuer-level data
- changing from raw fact to derived metric

Non-material changes may use normal version bumps:

- optional field additions
- documentation improvements
- additional examples
- new mappings

---

### 5. Support extensions safely

Unknown extensions must be preserved or ignored safely according to the spec.

Rules:

- custom metadata goes under `extensions`
- extension keys should be namespace-qualified when possible
- extensions must not silently override core semantics
- consumers should tolerate unknown extensions

Do not reject valid resources just because they contain unfamiliar extension metadata.

---

## Pulse-specific implementation guidance

### Required concept integrity

For base Pulse definitions, prefer clear support for:

- business definition
- entity type or subject
- identifiers
- dimensions
- time semantics
- units or currency semantics where applicable
- quality or validation rules
- request/response schema

Avoid vague definitions such as "latest value" without defining latest relative to what.

---

### Pulse classes

The standard Pulse classes are:

- `fact`
- `analytic`
- `artifact`

Use them consistently.

Guidance:

- `fact` = canonical or sourced business meaning
- `analytic` = derived result, should declare dependencies or methodology
- `artifact` = narrative, presentation, or report-oriented output

Do not treat all Pulses as facts.

---

### Derivation rules

For `analytic` and `artifact` Pulses, include derivation metadata whenever the task touches their logic.

Preferred derivation elements:

- input pulse IDs
- method type
- method reference
- parameter schema
- lineage notes

Analytics without declared dependencies become hard to validate and hard to reuse.

---

### Mapping rules

Mappings must remain explicit.

A mapping should capture, when available:

- source system
- product or dataset
- source field or reference
- relation type
- field mapping
- transforms
- confidence
- coverage notes
- test cases

Do not bury vendor mappings inside core Pulse definitions.

---

## Coding rules

### Follow existing repository patterns

Prefer the existing stack, file layout, naming conventions, validation approach, and test style already present in the repository.

Do not introduce a new framework, schema library, ORM, or state-management pattern unless the task clearly requires it.

---

### Keep changes scoped

For each task:

- modify only files relevant to the requested change
- avoid opportunistic refactors unless necessary for correctness
- note any adjacent cleanup as follow-up work instead of mixing it into the same change

---

### Prefer explicitness over magic

When implementing Pulse models and validation:

- use clear type names
- prefer explicit transformations
- make schema validation rules readable
- avoid hidden coupling between profiles, mappings, and definitions

---

### Preserve backward compatibility

Unless the task explicitly requests a breaking change:

- do not break existing serialized Pulse resources
- do not remove accepted fields without migration handling
- do not tighten validation in a way that invalidates known examples without documenting it

If a breaking change is necessary, document it clearly.

---

## Documentation rules

When semantics change, update the relevant docs.

Typical files to update:

- `docs/spec/pulse-definition-spec.md`
- `schemas/pds.schema.json`
- `examples/pulses/`
- changelog or decision records if present

Examples are part of the spec surface. Keep them current.

---

## Test and validation expectations

Every meaningful change should include validation.

When applicable:

- add or update unit tests
- add or update schema validation tests
- add positive and negative example cases
- verify examples still match the schema
- verify mappings and profiles do not violate base definition assumptions

If the repository exposes standard validation commands, run them before finishing.

Preferred checks, if available:

- lint
- typecheck
- unit tests
- schema validation tests

If a command fails because the project is not configured for it, do not invent a workaround silently. Note the limitation in the final summary.

---

## Task workflow

### For larger tasks

Start by understanding the current design before coding.

Good workflow:

1. read relevant spec and code
2. identify impacted files
3. make a small implementation plan
4. implement in narrow steps
5. run validation
6. summarize changes and unresolved issues

### For ambiguous tasks

Choose the interpretation that best preserves:

- semantic clarity
- portability
- backward compatibility
- separation of definition, profile, and mapping

Do not resolve ambiguity by hardcoding one vendor or one application's assumptions into the shared model.

---

## Deliverables

For spec-related work, a complete implementation usually includes some combination of:

- model or type updates
- schema updates
- example resources
- tests
- documentation changes

At the end of the task, summarize:

- what changed
- which files changed
- whether the change is backward compatible
- any unresolved ambiguities or follow-up recommendations

---

## Anti-patterns to avoid

Avoid these mistakes:

- treating Pulse definitions as a flat vendor field dictionary
- embedding LSEG or Bloomberg assumptions into core semantic types
- mixing application profile rules into base Pulse definitions
- changing meaning without changing identity
- using extensions to override core semantics
- collapsing fact, analytic, and artifact into one undifferentiated model
- silently assuming external equivalence without relation typing

---

## Preferred architectural direction

For Attas, the preferred layering is:

1. **base pulse definitions** as portable semantic contracts
2. **profiles** for Attas applications such as research, screening, monitoring, and reporting
3. **mappings** for vendor systems, ontologies, and legacy definitions
4. **catalogs** for reusable domain bundles

This layering should remain visible in both code and documentation.

---

## When adding new files

Prefer these locations when relevant:

- `docs/spec/` for normative specifications
- `docs/architecture/` for system context and design explanation
- `schemas/` for machine-readable schemas
- `examples/pulses/` for example Pulse resources
- `tests/` or the repo's existing test directories for validation coverage

If the repository already uses different locations, follow the existing structure.

---

## Final note

Attas is building a reusable Pulse ecosystem, not a one-off app schema.

Make choices that keep Pulses:

- semantically clear
- portable across applications
- compatible with external definitions
- safe to extend
- easy to validate