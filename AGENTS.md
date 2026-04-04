# Repository Architecture Guardrails

This file defines the intended dependency direction for this repository and should guide future coding work.

## Layer model

The repository has three product layers:

1. `prompits`
   A general multi-agent framework.
2. `phemacast`
   A content collaboration platform built on `prompits`.
3. `attas`
   A financial application built on `phemacast`.

The allowed dependency direction is:

```text
attas -> phemacast -> prompits
```

Reverse dependencies are not allowed.

## Hard rules

### `prompits`

`prompits` is the base framework layer.

It must not import from:

- `phemacast`
- `attas`

It must not depend on `phemacast` or `attas` concepts in:

- runtime code
- schemas
- templates
- static assets
- route names
- default config paths
- examples
- tests
- docs
- branding text

If something in `prompits` looks specific to content workflows or finance workflows, it likely belongs in `phemacast` or `attas` instead.

### `phemacast`

`phemacast` is the middle platform layer.

It may import from:

- `prompits`

It must not import from:

- `attas`

`phemacast` should contain reusable content-collaboration concepts, not finance-specific product logic or `attas` branding.

### `attas`

`attas` is the top application layer.

It may import from:

- `phemacast`
- `prompits`

`attas` owns finance-specific workflows, pulse catalogs, finance-oriented UIs, and product-specific branding.

## Refactoring rule

When code is shared across layers, move it upward only as far as it remains generic:

- If it is finance-specific, keep it in `attas`.
- If it is content-collaboration specific but not finance-specific, move it to `phemacast`.
- If it is generic multi-agent infrastructure, move it to `prompits`.

Do not solve reuse by importing downward from a lower-level package into a higher-level package.
Do not solve reuse by importing upward from `prompits` into `phemacast` or `attas`.

## Migration guidance

Legacy cross-layer references may still exist in the repository.
Treat them as technical debt to remove, not as precedent for new code.

When touching code near an existing violation:

1. Avoid adding any new reverse dependency.
2. Prefer extracting the shared logic to the correct layer.
3. Leave a note in the change summary if a boundary violation remains.

## Review checklist

Before finishing work that touches these packages, check:

- Does `prompits` reference `phemacast` or `attas` anywhere?
- Does `phemacast` reference `attas` anywhere?
- Are examples, fixtures, templates, and tests following the same dependency direction as the runtime code?
- Does branding match the owning layer?

Useful checks:

```bash
rg -n "from (phemacast|attas)\.|import (phemacast|attas)(\.|$)" prompits
rg -n "from attas\.|import attas(\.|$)" phemacast
```
