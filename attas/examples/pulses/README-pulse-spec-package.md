# Attas Pulse Specification Package

Version: 0.1.0

This package is a starter set of files for implementing the Pulse Definition Specification (PDS) in Attas.

## What is included

### Core documentation

- `AGENTS.md`  
  Repository-level coding guidance for Codex and contributors

- `docs/spec/pulse-definition-spec.md`  
  Human-readable normative specification for PDS

- `docs/architecture/attas-overview.md`  
  Short system overview explaining how Pulses fit into Attas

### Machine-readable schema

- `schemas/pds.schema.json`  
  JSON Schema for validating the four PDS resource types:
  - `pulse_definition`
  - `pulse_profile`
  - `pulse_mapping`
  - `pulse_catalog`

### Example resources

#### Base Pulse definitions

- `examples/pulses/last_trade.json`  
  Example `fact` pulse for market pricing

- `examples/pulses/revenue.json`  
  Example `fact` pulse for issuer fundamentals

- `examples/pulses/rsi.json`  
  Example `analytic` pulse with derivation metadata

- `examples/pulses/rating_summary.json`  
  Example `artifact` pulse for research output

#### Mapping example

- `examples/pulses/lseg-last-trade.mapping.json`  
  Example vendor binding kept outside the base definition

#### Profile example

- `examples/pulses/attas-equity-research-last-trade.profile.json`  
  Example application-specific profile for Attas equity research

#### Catalog example

- `examples/pulses/finance-core.catalog.json`  
  Starter catalog that bundles the example resources

#### Negative validation example

- `examples/pulses/invalid-last-trade.missing-interface.json`  
  Example invalid resource that should fail schema validation

### Validation notes

- `tests/pds-validation-cases.md`  
  Expected pass/fail behavior for the example files

---

## Recommended repository layout

A good repository layout for these files is:

```text
AGENTS.md
docs/
  architecture/
    attas-overview.md
  spec/
    pulse-definition-spec.md
schemas/
  pds.schema.json
examples/
  pulses/
    last_trade.json
    revenue.json
    rsi.json
    rating_summary.json
    lseg-last-trade.mapping.json
    attas-equity-research-last-trade.profile.json
    finance-core.catalog.json
    invalid-last-trade.missing-interface.json
tests/
  pds-validation-cases.md
```

---

## Recommended implementation order

1. Add `AGENTS.md`
2. Add the human-readable spec
3. Add the JSON Schema
4. Add the valid example resources
5. Add the invalid example resources
6. Wire schema validation into tests or CI
7. Add language-specific model types and validators in the codebase

---

## How Codex should use this package

When asking Codex to implement PDS support, tell it to read these first:

- `AGENTS.md`
- `docs/spec/pulse-definition-spec.md`
- `schemas/pds.schema.json`
- `docs/architecture/attas-overview.md`
- `examples/pulses/`
- `tests/pds-validation-cases.md`

Recommended task pattern:

1. ask for a plan
2. review the plan
3. ask for implementation in a narrow scope
4. require schema validation and tests
5. request a summary of changed files and unresolved ambiguities

---

## Suggested first coding task

A good first implementation task is:

- create strongly typed models for the four PDS resource types
- load and validate example JSON files against `schemas/pds.schema.json`
- add a test harness that checks expected pass/fail outcomes from `tests/pds-validation-cases.md`
- keep vendor mappings separate from base Pulse definitions
- preserve unknown extensions safely

---

## Future files to add

Recommended next additions:

- `examples/pulses/bid_ask_quote.json`
- `examples/pulses/net_income.json`
- `examples/pulses/investment_thesis_bullets.json`
- `examples/pulses/bloomberg-last-trade.mapping.json`
- `examples/pulses/common.catalog.json`
- `tests/pds-invalid-cases/` with more negative examples
- language-specific validator examples such as:
  - `examples/code/typescript/validate-pds.ts`
  - `examples/code/python/validate_pds.py`

---

## Design reminders

Keep this package aligned with the following principles:

- base Pulse definitions are portable semantic contracts
- application-specific constraints belong in profiles
- vendor and external-system bindings belong in mappings
- catalogs are reusable bundles
- unknown extensions should not break consumers
- semantic meaning should not be changed silently under the same Pulse ID

---

## Package status

This package is a draft starter set for Attas and should evolve with:

- new domains
- additional examples
- stronger validation coverage
- implementation-specific guidance once the first code integration is complete
