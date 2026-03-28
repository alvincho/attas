# Attas Overview
Version: 0.1.0
Status: Draft

## 1. Purpose

Attas is a system for defining, discovering, exchanging, and consuming reusable semantic contracts called **Pulses**.

A Pulse is the core unit of meaning in Attas. A Pulse can represent:

- a canonical fact
- a derived analytic
- a narrative or presentation artifact

Attas is designed so Pulses can be used by multiple applications, agents, services, and external systems without being locked to a single vendor, UI, or workflow.

---

## 2. Why Attas uses Pulses

Traditional data dictionaries are usually flat lists of fields tied to one product or one database. That is too limited for Attas.

Attas needs a unit that can carry:

- business meaning
- interface contracts
- time semantics
- identifier requirements
- mappings to vendor fields or external standards
- derivation metadata for analytics
- compatibility with multiple applications

A Pulse provides that unit.

In Attas, a Pulse is not just a field definition. It is a reusable semantic contract that can be shared between humans, applications, and agents.

---

## 3. Architectural principles

### 3.1 Portable semantics first

The core meaning of a Pulse should be defined independently from any one application.

### 3.2 Profiles for application behavior

Application-specific constraints should be layered on top of a base Pulse, not embedded in the base definition.

### 3.3 Explicit interoperability

Attas should coexist with external systems such as:

- FIBO
- vendor data dictionaries
- internal enterprise dictionaries
- legacy schemas
- third-party applications

### 3.4 Separation of meaning and mapping

A Pulse definition describes what something means.
A mapping describes how another system represents it.
These must remain separate.

### 3.5 Safe extensibility

Applications must be able to add metadata without breaking consumers that do not understand those extensions.

---

## 4. Core resource model

Attas uses the Pulse Definition Specification with four main resource types.

### 4.1 pulse_definition

Defines the semantic meaning and interface contract of a Pulse.

### 4.2 pulse_profile

Adds application-specific rules such as defaults, required fields, display hints, or workflow constraints.

### 4.3 pulse_mapping

Connects a Pulse to an external definition or system.

Examples:

- FIBO concept
- LSEG field
- Bloomberg field
- internal column or API field

### 4.4 pulse_catalog

Publishes a reusable package of Pulse resources.

---

## 5. Pulse classes

Attas recognizes three standard Pulse classes.

### 5.1 fact

A canonical or sourced business concept.

Examples:

- last trade price
- revenue
- market capitalization
- cash dividend

### 5.2 analytic

A derived metric or computed result.

Examples:

- RSI
n- implied volatility summary
- valuation multiple
- sentiment score

### 5.3 artifact

A narrative, report-oriented, or presentation-oriented result.

Examples:

- investment thesis bullets
- rating summary
- scenario narrative
- report section output

These classes should not be collapsed into one undifferentiated model.

---

## 6. How Attas should use Pulses

Attas should organize Pulses into layers.

### 6.1 Base semantic layer

This layer contains portable `pulse_definition` resources.

It is the stable meaning layer used across applications.

### 6.2 Application layer

This layer contains `pulse_profile` resources.

Examples of Attas applications:

- equity research
- screening
- monitoring
- portfolio analysis
- report generation

### 6.3 Interoperability layer

This layer contains `pulse_mapping` resources.

It is where external systems are linked to Attas Pulses.

### 6.4 Distribution layer

This layer contains `pulse_catalog` resources.

Catalogs allow bundles of related definitions, profiles, and mappings to be reused together.

---

## 7. External coexistence

Attas should not force external definitions to disappear behind Attas-native names.

Instead, Attas should make the relationship explicit.

Examples:

- a Pulse may have a `close_match` reference to a FIBO concept
- a Pulse mapping may state that an LSEG field is a `close_match`
- a Bloomberg field may be treated as `related` rather than equivalent

This lets Attas act as a semantic coordination layer instead of pretending all systems already match perfectly.

---

## 8. Relationship to FIBO and vendor dictionaries

### 8.1 FIBO

FIBO is useful as a semantic reference layer for business meaning.

Attas should use FIBO where it helps define canonical financial concepts such as:

- instruments
- issuers
- venues
- prices
- corporate actions
- accounting concepts

Attas should not assume every Pulse has a direct one-to-one FIBO equivalent.

### 8.2 Vendor dictionaries

Vendor dictionaries are useful for source mappings, not as the core semantic model.

Attas should treat vendor fields as implementation bindings.

Examples:

- LSEG field codes
- Bloomberg field mnemonics
- internal dataset column names

Those belong in `pulse_mapping`, not in the base definition.

---

## 9. Semantic stability

Pulse IDs are meaning-bound.

If the meaning materially changes, Attas should create a new Pulse ID instead of silently changing the existing one.

Examples of semantic changes that require a new ID:

- changing from last trade price to midpoint
- changing from instrument-level meaning to issuer-level meaning
- changing from raw fact to derived metric
- changing from venue-specific value to consolidated value

This rule is important for agent interoperability, validation, and long-term catalog stability.

---

## 10. Derivation and lineage

Analytics and artifacts should declare where they come from.

Attas should capture derivation metadata such as:

- input Pulse IDs
- method type
- method reference
- parameter schema
- lineage notes

Without derivation metadata, analytic Pulses become difficult to validate and compare across systems.

---

## 11. Application neutrality

Attas should keep the base Pulse model neutral with respect to:

- one frontend or screen layout
- one transport protocol
- one agent runtime
- one vendor
- one database schema
- one report format

This is critical if Pulses are to be reused outside the original Attas application context.

---

## 12. Recommended repository structure

A clean starting structure is:

```text
AGENTS.md
docs/
  spec/
    pulse-definition-spec.md
  architecture/
    attas-overview.md
schemas/
  pds.schema.json
examples/
  pulses/
    last_trade.json
    revenue.json
    rsi.json
    rating_summary.json
```

This structure keeps:

- durable instructions in `AGENTS.md`
- semantic rules in `docs/spec/`
- architecture context in `docs/architecture/`
- machine validation in `schemas/`
- working examples in `examples/`

---

## 13. Implementation direction

When coding Attas, the preferred implementation order is:

1. define the resource models
2. define the machine-readable schema
3. create example Pulse resources
4. add validators and tests
5. add application profiles
6. add mappings to external systems
7. expose discovery and consumption APIs if needed

This order reduces ambiguity and keeps the semantic layer stable before integrations expand.

---

## 14. Initial finance domains for Attas

A practical initial set of catalogs for financial use includes:

- finance_core
- equity_research
- macro
- news
- options
- portfolio_monitoring

A practical initial set of canonical Pulse areas includes:

- instrument master
- issuer profile
- venue and listing
- prices and bars
- corporate actions
- fundamentals
- estimates
- ownership

Derived analytics and report artifacts should be added on top of that canonical base.

---

## 15. Non-financial reuse

Although Attas currently emphasizes financial use cases, the Pulse model should remain generic enough for other domains.

The same structure can support domains such as:

- weather
- healthcare
- industrial monitoring
- logistics
- legal information
- scientific data products

This is another reason to keep base Pulse semantics application-neutral and mapping-aware.

---

## 16. What Attas is not doing

Attas is not trying to:

- replace all ontologies
- replace all vendor dictionaries
- force one universal schema on every application
- flatten facts, analytics, and artifacts into the same kind of object

Instead, Attas provides a stable semantic coordination model that different systems can share.

---

## 17. Summary

Attas uses Pulses as reusable semantic contracts.

The architectural model is:

- **definitions** for portable meaning
- **profiles** for application rules
- **mappings** for external interoperability
- **catalogs** for reusable bundles

This approach lets Attas remain flexible, extensible, and compatible with other ecosystems while still giving agents and applications a strong common contract.
