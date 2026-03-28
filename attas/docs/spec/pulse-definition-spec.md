# Pulse Definition Specification
Version: 0.1.0
Status: Draft

## 1. Purpose

This document defines the **Pulse Definition Specification (PDS)**.

A Pulse is a reusable semantic contract for a concept, metric, event, or artifact. The specification is designed to be:

- portable across applications
- extensible without breaking existing consumers
- compatible with external definitions and standards
- suitable for both human interpretation and machine validation

PDS is intended to support Attas and other systems without making Attas-specific assumptions part of the core semantic model.

---

## 2. Design goals

PDS has the following goals:

1. Separate semantic meaning from application constraints.
2. Allow coexistence with other definitions such as FIBO, vendor dictionaries, internal enterprise dictionaries, and future third-party schemas.
3. Support both canonical facts and higher-level analytics or artifacts.
4. Keep the base model transport-neutral and implementation-neutral.
5. Make validation straightforward through machine-readable schemas and examples.

---

## 3. Scope

PDS defines four resource types:

- `pulse_definition`
- `pulse_profile`
- `pulse_mapping`
- `pulse_catalog`

PDS does not define:

- a transport protocol
- a storage backend
- a query language
- a UI format
- a workflow engine

These may be added by applications or companion specifications.

---

## 4. Key concepts

### 4.1 Pulse

A Pulse is a reusable semantic contract for one concept, metric, event, or artifact.

A Pulse may represent:

- a canonical fact
- a derived analytic
- a narrative or report artifact

### 4.2 Base definition

A base definition captures the core semantic meaning of a Pulse.

It should remain application-neutral.

### 4.3 Profile

A profile is an application-specific overlay on a base Pulse.

A profile may add defaults, constraints, or presentation hints, but must not redefine the meaning of the base Pulse.

### 4.4 Mapping

A mapping connects a Pulse to an external system or definition.

Examples:

- FIBO concept URI
- LSEG field
- Bloomberg field
- internal database column
- legacy enterprise dictionary entry

### 4.5 Catalog

A catalog is a package of Pulse resources that can be reused together.

---

## 5. Normative language

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** in this document are to be interpreted as normative requirements.

---

## 6. Resource model

Every PDS resource MUST include:

- `pds_version`
- `resource_type`
- `id`
- `version`

### 6.1 Common fields

#### `pds_version`
The version of the Pulse Definition Specification that the resource conforms to.

Type: string

Example:
`"0.1.0"`

#### `resource_type`
The type of resource.

Allowed values:

- `pulse_definition`
- `pulse_profile`
- `pulse_mapping`
- `pulse_catalog`

#### `id`
A globally unique, stable identifier for the resource.

PDS recommends reverse-DNS or URI-like naming.

Examples:

- `ai.attas.finance.price.last_trade`
- `ai.attas.finance.fundamentals.revenue`
- `org.example.weather.current_temperature`

#### `version`
The version of the resource itself.

Semantic versioning is recommended.

Example:
`"1.0.0"`

---

## 7. Resource type: pulse_definition

A `pulse_definition` is the canonical semantic definition of a Pulse.

It describes meaning, interface, interoperability metadata, and optional derivation metadata.

### 7.1 Required fields

A `pulse_definition` MUST contain:

- `pds_version`
- `resource_type = "pulse_definition"`
- `id`
- `version`
- `title`
- `description`
- `pulse_class`
- `status`
- `concept`
- `interface`

### 7.2 Recommended fields

A `pulse_definition` SHOULD contain:

- `namespace`
- `name`
- `interop`
- `governance`
- `examples`

It MAY contain:

- `derivation`
- `extensions`

### 7.3 Field definitions

#### `namespace`
The issuing authority or namespace of the Pulse.

Type: string

Example:
`"ai.attas.finance.price"`

#### `name`
The local short name of the Pulse.

Type: string

Example:
`"last_trade"`

#### `title`
Human-readable label.

Type: string

Example:
`"Last Trade Price"`

#### `description`
Human-readable summary of the Pulse.

Type: string

#### `pulse_class`
The class of Pulse.

Allowed values:

- `fact`
- `analytic`
- `artifact`

Definitions:

- `fact`: canonical or sourced business meaning
- `analytic`: derived or computed result
- `artifact`: narrative, rendered, or presentation-oriented output

#### `status`
Lifecycle status of the Pulse.

Recommended values:

- `draft`
- `stable`
- `deprecated`

---

## 8. Concept layer

The `concept` object defines the business meaning of a Pulse.

### 8.1 Required concept fields

A `concept` MUST contain:

- `definition`

### 8.2 Recommended concept fields

A `concept` SHOULD contain, where applicable:

- `entity_types`
- `tags`
- `dimensions`
- `identifiers`
- `units`
- `time_semantics`
- `quality_rules`

### 8.3 Concept field definitions

#### `definition`
Normative business meaning of the Pulse.

Type: string

This field MUST define the concept clearly enough that another system can distinguish it from similar concepts.

Bad example:
`"Latest price"`

Better example:
`"Most recent executed trade price for a financial instrument on a specified venue or consolidated feed."`

#### `entity_types`
The types of entities the Pulse applies to.

Type: array of strings

Examples:

- `financial_instrument`
- `issuer`
- `portfolio`
- `economic_region`

#### `tags`
Non-normative classification labels.

Type: array of strings

#### `dimensions`
Contextual axes that qualify the Pulse.

Type: array of strings

Examples:

- `venue`
- `currency`
- `session`
- `region`
- `tenor`
- `fiscal_period`

#### `identifiers`
Allowed identifier types for requesting or referencing the entity.

Type: array of strings

Examples:

- `symbol`
- `isin`
- `cusip`
- `figi`
- `lseg_ric`
- `bloomberg_ticker`
- `instrument_id`

#### `units`
Unit or currency semantics for the Pulse.

Type: object

Example:
```json
{
  "value_type": "currency_amount",
  "currency_required": true
}
```

#### `time_semantics`
Defines timing meaning.

Type: object

Recommended fields:

- `kind`
- `timestamp_field`
- `modes`

Recommended values for `kind`:

- `point_in_time`
- `interval`
- `effective_dated`
- `announcement_dated`
- `filing_dated`

Example:
```json
{
  "kind": "point_in_time",
  "timestamp_field": "observed_at",
  "modes": ["realtime", "delayed", "eod"]
}
```

#### `quality_rules`
Validation or sanity constraints.

Type: array of strings

Examples:

- `value >= 0`
- `currency is required when value is present`
- `period_end must be after period_start`

---

## 9. Interface layer

The `interface` object defines logical request and response contracts.

### 9.1 Required interface fields

An `interface` MUST contain:

- `schema_language`
- `request_schema`
- `response_schema`

### 9.2 Supported schema languages

The default and recommended schema language is:

- `json-schema-2020-12`

Other schema languages MAY be used in future versions or application extensions.

### 9.3 Request schema

The request schema defines the accepted input shape for requesting the Pulse.

### 9.4 Response schema

The response schema defines the output shape for returning the Pulse.

### 9.5 Example

```json
"interface": {
  "schema_language": "json-schema-2020-12",
  "request_schema": {
    "type": "object",
    "properties": {
      "symbol": { "type": "string" },
      "lseg_ric": { "type": "string" },
      "bloomberg_ticker": { "type": "string" },
      "venue": { "type": "string" }
    }
  },
  "response_schema": {
    "type": "object",
    "properties": {
      "value": { "type": "number" },
      "currency": { "type": "string" },
      "observed_at": { "type": "string", "format": "date-time" },
      "venue": { "type": "string" }
    },
    "required": ["value"]
  }
}
```

---

## 10. Interoperability layer

The `interop` object allows a Pulse to coexist with other definitions.

### 10.1 Recommended fields

- `aliases`
- `external_refs`
- `related_pulses`

### 10.2 `aliases`

Alternative names for the Pulse.

Type: array of strings

Examples:

- `last_price`
- `trade_price_last`

### 10.3 `external_refs`

References to external definitions.

Type: array of objects

Each reference SHOULD include:

- `system`
- `ref`
- `relation`

It MAY include:

- `confidence`
- `notes`

### 10.4 Relation vocabulary

Recommended relation values:

- `equivalent_match`
- `close_match`
- `broader_than`
- `narrower_than`
- `derived_from`
- `implements`
- `related`

These relation types MUST be explicit. A system MUST NOT assume equivalence without a declared relation.

### 10.5 Example

```json
"interop": {
  "aliases": ["last_price", "trade_price_last"],
  "external_refs": [
    {
      "system": "fibo",
      "ref": "https://example.org/fibo/concept/last-trade-price",
      "relation": "close_match",
      "confidence": 0.86
    },
    {
      "system": "internal_legacy_dictionary",
      "ref": "PX_LAST",
      "relation": "related"
    }
  ],
  "related_pulses": [
    "ai.attas.finance.price.bid_ask_quote",
    "ai.attas.finance.price.daily_ohlcv_bar"
  ]
}
```

---

## 11. Derivation layer

The `derivation` object is optional for `fact` Pulses and recommended for `analytic` and `artifact` Pulses.

### 11.1 Recommended fields

- `input_pulse_ids`
- `method_type`
- `method_ref`
- `parameters_schema`
- `notes`

### 11.2 Requirements

If `pulse_class` is `analytic` or `artifact`, the definition SHOULD include derivation metadata whenever the output is meaningfully dependent on other Pulses or a defined method.

### 11.3 Example

```json
"derivation": {
  "input_pulse_ids": [
    "ai.attas.finance.price.daily_ohlcv_bar"
  ],
  "method_type": "formula",
  "method_ref": "wilder-rsi-14",
  "parameters_schema": {
    "type": "object",
    "properties": {
      "window": { "type": "integer", "default": 14 }
    }
  }
}
```

---

## 12. Governance layer

The `governance` object captures ownership and lifecycle metadata.

### 12.1 Recommended fields

- `owner`
- `license`
- `created_at`
- `updated_at`
- `deprecated_by`
- `change_notes`

### 12.2 Example

```json
"governance": {
  "owner": "Attas Core Team",
  "license": "Apache-2.0",
  "created_at": "2026-03-26T00:00:00Z",
  "updated_at": "2026-03-26T00:00:00Z"
}
```

---

## 13. Resource type: pulse_profile

A `pulse_profile` is an application-specific overlay on a base Pulse.

A profile MAY:

- tighten request constraints
- tighten response requirements
- define defaults
- add presentation hints
- add workflow metadata

A profile MUST NOT:

- change the core semantic meaning
- invert the logic of the base Pulse
- redefine the meaning of existing external references

### 13.1 Required fields

A `pulse_profile` MUST contain:

- `pds_version`
- `resource_type = "pulse_profile"`
- `id`
- `version`
- `base_pulse_id`

### 13.2 Recommended fields

- `application`
- `constraints`
- `defaults`
- `presentation`
- `extensions`

### 13.3 Example

```json
{
  "pds_version": "0.1.0",
  "resource_type": "pulse_profile",
  "id": "ai.attas.profile.equity_research.last_trade",
  "version": "1.0.0",
  "base_pulse_id": "ai.attas.finance.price.last_trade",
  "application": "attas.equity_research",
  "constraints": {
    "request": {
      "require_one_of": ["symbol", "lseg_ric", "bloomberg_ticker"]
    },
    "response": {
      "required": ["value", "currency", "observed_at"]
    }
  },
  "defaults": {
    "venue": "primary_listing"
  },
  "presentation": {
    "field_order": ["value", "currency", "observed_at", "venue"]
  },
  "extensions": {
    "ai.attas": {
      "panel": "market_snapshot"
    }
  }
}
```

---

## 14. Resource type: pulse_mapping

A `pulse_mapping` binds a Pulse to an external definition or source system.

Examples:

- ontology concept
- vendor field
- message standard element
- database field
- internal dictionary code

### 14.1 Required fields

A `pulse_mapping` MUST contain:

- `pds_version`
- `resource_type = "pulse_mapping"`
- `id`
- `version`
- `pulse_id`
- `source_system`
- `relation`

### 14.2 Recommended fields

- `source_ref`
- `mapping_type`
- `field_map`
- `transforms`
- `tests`
- `coverage`
- `confidence`
- `notes`

### 14.3 Mapping rules

Mappings MUST be explicit.

Mappings MUST NOT be embedded as hardcoded vendor assumptions inside a base `pulse_definition`.

### 14.4 Example

```json
{
  "pds_version": "0.1.0",
  "resource_type": "pulse_mapping",
  "id": "ai.attas.mapping.lseg.last_trade",
  "version": "1.0.0",
  "pulse_id": "ai.attas.finance.price.last_trade",
  "source_system": "lseg",
  "source_ref": {
    "product": "realtime",
    "field": "TRDPRC_1"
  },
  "relation": "close_match",
  "mapping_type": "direct",
  "field_map": {
    "value": "TRDPRC_1",
    "currency": "CURRENCY",
    "observed_at": "TRDTIM_1"
  },
  "transforms": [
    {
      "target_field": "observed_at",
      "operation": "parse_timestamp"
    }
  ],
  "confidence": 0.9
}
```

---

## 15. Resource type: pulse_catalog

A `pulse_catalog` publishes a package of reusable Pulse resources.

### 15.1 Required fields

A `pulse_catalog` MUST contain:

- `pds_version`
- `resource_type = "pulse_catalog"`
- `id`
- `version`
- `items`

### 15.2 Recommended fields

- `title`
- `description`
- `imports`

### 15.3 Example

```json
{
  "pds_version": "0.1.0",
  "resource_type": "pulse_catalog",
  "id": "ai.attas.catalog.finance_core",
  "version": "1.0.0",
  "title": "Attas Finance Core",
  "imports": [
    "ai.attas.catalog.common"
  ],
  "items": [
    { "ref": "ai.attas.finance.price.last_trade" },
    { "ref": "ai.attas.finance.price.bid_ask_quote" },
    { "ref": "ai.attas.finance.fundamentals.revenue" },
    { "ref": "ai.attas.profile.equity_research.last_trade" },
    { "ref": "ai.attas.mapping.lseg.last_trade" }
  ]
}
```

---

## 16. Extensions

Extensions are the primary way to add custom metadata without breaking interoperability.

### 16.1 Rules

- Extensions MUST be placed under `extensions`.
- Consumers MUST ignore unknown extensions unless a stricter application profile says otherwise.
- Extensions MUST NOT silently override the meaning of core semantic fields.
- Extension keys SHOULD be namespace-qualified when practical.

### 16.2 Example

```json
"extensions": {
  "ai.attas": {
    "discovery_score": 0.91
  },
  "com.example.risk": {
    "stress_bucket": "equity_large_cap"
  }
}
```

---

## 17. Identity and semantic stability

Pulse IDs are meaning-bound.

If the meaning materially changes, a new Pulse ID MUST be created.

### 17.1 Material semantic changes

Examples of changes that require a new ID:

- changing from last executed trade price to midpoint
- changing from instrument-level value to issuer-level value
- changing from raw fact to computed metric
- changing from venue-specific price to consolidated price

### 17.2 Non-material changes

Examples of changes that do not require a new ID:

- adding optional fields
- correcting documentation
- adding examples
- adding new mappings
- adding non-breaking extensions

---

## 18. Versioning

PDS resources SHOULD use semantic versioning.

### 18.1 Major version

Increment major when the resource changes incompatibly.

### 18.2 Minor version

Increment minor for backward-compatible additions.

### 18.3 Patch version

Increment patch for non-semantic fixes such as typos or example corrections.

---

## 19. Minimal conformance

### 19.1 pulse_definition
A resource is a conformant `pulse_definition` if it contains:

- `pds_version`
- `resource_type = "pulse_definition"`
- `id`
- `version`
- `title`
- `description`
- `pulse_class`
- `status`
- `concept.definition`
- `interface.schema_language`
- `interface.request_schema`
- `interface.response_schema`

### 19.2 pulse_profile
A resource is a conformant `pulse_profile` if it contains:

- `pds_version`
- `resource_type = "pulse_profile"`
- `id`
- `version`
- `base_pulse_id`

### 19.3 pulse_mapping
A resource is a conformant `pulse_mapping` if it contains:

- `pds_version`
- `resource_type = "pulse_mapping"`
- `id`
- `version`
- `pulse_id`
- `source_system`
- `relation`

### 19.4 pulse_catalog
A resource is a conformant `pulse_catalog` if it contains:

- `pds_version`
- `resource_type = "pulse_catalog"`
- `id`
- `version`
- `items`

---

## 20. Recommended Attas usage

Attas should use PDS with clear layering:

1. base `pulse_definition` resources for portable meaning
2. `pulse_profile` resources for application-specific behavior
3. `pulse_mapping` resources for vendor, ontology, and legacy integration
4. `pulse_catalog` resources for domain bundles

Recommended Attas domains include:

- finance_core
- equity_research
- macro
- news
- options
- portfolio_monitoring

---

## 21. Worked example

### 21.1 Base definition

```json
{
  "pds_version": "0.1.0",
  "resource_type": "pulse_definition",
  "id": "ai.attas.finance.price.last_trade",
  "namespace": "ai.attas.finance.price",
  "name": "last_trade",
  "version": "1.0.0",
  "title": "Last Trade Price",
  "description": "Most recent executed trade price for a financial instrument on a specified venue or consolidated feed.",
  "pulse_class": "fact",
  "status": "stable",
  "concept": {
    "definition": "Most recent executed trade price for a financial instrument on a specified venue or consolidated feed.",
    "entity_types": ["financial_instrument"],
    "tags": ["pricing", "market-data"],
    "dimensions": ["venue", "currency", "session"],
    "identifiers": ["symbol", "lseg_ric", "bloomberg_ticker"],
    "units": {
      "value_type": "currency_amount",
      "currency_required": true
    },
    "time_semantics": {
      "kind": "point_in_time",
      "timestamp_field": "observed_at",
      "modes": ["realtime", "delayed", "eod"]
    },
    "quality_rules": [
      "value >= 0",
      "currency is required when value is present"
    ]
  },
  "interface": {
    "schema_language": "json-schema-2020-12",
    "request_schema": {
      "type": "object",
      "properties": {
        "symbol": { "type": "string" },
        "lseg_ric": { "type": "string" },
        "bloomberg_ticker": { "type": "string" },
        "venue": { "type": "string" }
      }
    },
    "response_schema": {
      "type": "object",
      "properties": {
        "value": { "type": "number" },
        "currency": { "type": "string" },
        "observed_at": { "type": "string", "format": "date-time" },
        "venue": { "type": "string" }
      },
      "required": ["value"]
    }
  },
  "interop": {
    "aliases": ["last_price"],
    "external_refs": [
      {
        "system": "fibo",
        "ref": "https://example.org/fibo/concept/last-trade-price",
        "relation": "close_match"
      }
    ]
  }
}
```

### 21.2 Profile

```json
{
  "pds_version": "0.1.0",
  "resource_type": "pulse_profile",
  "id": "ai.attas.profile.equity_research.last_trade",
  "version": "1.0.0",
  "base_pulse_id": "ai.attas.finance.price.last_trade",
  "application": "attas.equity_research",
  "constraints": {
    "response": {
      "required": ["value", "currency", "observed_at"]
    }
  },
  "defaults": {
    "venue": "primary_listing"
  }
}
```

### 21.3 Mapping

```json
{
  "pds_version": "0.1.0",
  "resource_type": "pulse_mapping",
  "id": "ai.attas.mapping.lseg.last_trade",
  "version": "1.0.0",
  "pulse_id": "ai.attas.finance.price.last_trade",
  "source_system": "lseg",
  "relation": "close_match",
  "source_ref": {
    "product": "realtime",
    "field": "TRDPRC_1"
  },
  "mapping_type": "direct",
  "field_map": {
    "value": "TRDPRC_1",
    "currency": "CURRENCY",
    "observed_at": "TRDTIM_1"
  }
}
```

---

## 22. Starter implementation guidance

For a practical first implementation, start with:

1. one base schema for all four resource types
2. three to five example base Pulses
3. one profile for a concrete Attas application
4. one mapping each for FIBO and one vendor
5. positive and negative validation tests

Suggested first base Pulses:

- `ai.attas.finance.price.last_trade`
- `ai.attas.finance.price.bid_ask_quote`
- `ai.attas.finance.fundamentals.revenue`
- `ai.attas.finance.corporate_actions.cash_dividend`
- `ai.attas.finance.analytics.rsi_14`

---

## 23. Future extensions

Likely future areas for expansion include:

- stronger relation vocabularies
- standardized lineage metadata
- authorization and entitlements metadata
- service-level metadata such as freshness and latency
- multi-transport bindings
- localization for titles and descriptions
- formal compatibility profiles for specific ecosystems

These should be added in a way that preserves the base portability of PDS.
