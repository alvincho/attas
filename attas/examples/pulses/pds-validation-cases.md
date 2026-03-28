# PDS Validation Cases

Version: 0.1.0

This file documents the expected validation outcome for the example Pulse Definition Specification files in this starter package.

## Purpose

These cases are intended to help implementers verify that:

- valid PDS resources pass schema validation
- invalid PDS resources fail schema validation
- each resource type has at least one concrete example
- negative examples are preserved for regression testing

This file is descriptive. The schema itself remains the normative machine-readable validation source.

---

## Expected passing cases

The following files should pass validation against `schemas/pds.schema.json`.

### pulse_definition examples

- `examples/pulses/last_trade.json`  
  Expected result: pass  
  Notes: canonical `fact` pulse for market pricing

- `examples/pulses/revenue.json`  
  Expected result: pass  
  Notes: canonical `fact` pulse for fundamentals and reporting-period semantics

- `examples/pulses/rsi.json`  
  Expected result: pass  
  Notes: `analytic` pulse with derivation metadata

- `examples/pulses/rating_summary.json`  
  Expected result: pass  
  Notes: `artifact` pulse with synthesis-oriented derivation metadata

### pulse_mapping examples

- `examples/pulses/lseg-last-trade.mapping.json`  
  Expected result: pass  
  Notes: vendor mapping example kept outside the base pulse definition

### pulse_profile examples

- `examples/pulses/attas-equity-research-last-trade.profile.json`  
  Expected result: pass  
  Notes: application-specific overlay for Attas equity research

### pulse_catalog examples

- `examples/pulses/finance-core.catalog.json`  
  Expected result: pass  
  Notes: starter catalog referencing example definitions, mapping, and profile

---

## Expected failing cases

The following files should fail validation against `schemas/pds.schema.json`.

- `examples/pulses/invalid-last-trade.missing-interface.json`  
  Expected result: fail  
  Failure reason: required `interface` object is missing for a `pulse_definition`

---

## Recommended validator behavior

A validation harness should:

1. load `schemas/pds.schema.json`
2. validate each example file individually
3. assert that passing cases succeed
4. assert that failing cases fail
5. report the specific schema error path for failures

---

## Suggested automated test table

| File | Resource type | Expected |
|---|---|---|
| `last_trade.json` | `pulse_definition` | pass |
| `revenue.json` | `pulse_definition` | pass |
| `rsi.json` | `pulse_definition` | pass |
| `rating_summary.json` | `pulse_definition` | pass |
| `lseg-last-trade.mapping.json` | `pulse_mapping` | pass |
| `attas-equity-research-last-trade.profile.json` | `pulse_profile` | pass |
| `finance-core.catalog.json` | `pulse_catalog` | pass |
| `invalid-last-trade.missing-interface.json` | `pulse_definition` | fail |

---

## Future negative cases to add

Recommended next invalid examples:

- missing `concept.definition`
- invalid `pulse_class`
- invalid `relation` in `pulse_mapping`
- invalid semantic version in `version`
- `pulse_profile` missing `base_pulse_id`
- `pulse_catalog` with empty `items`
- `pulse_definition` with unsupported `schema_language`

These cases will improve regression coverage as the schema evolves.

---

## Notes for Codex or CI setup

When wiring automated validation:

- keep valid and invalid examples in separate lists or directories
- fail fast on unexpected pass/fail results
- print the schema error path to make debugging easier
- treat examples as part of the public contract, not disposable fixtures
