# Phemacast

Phemacast is a Prompits-based collaborative pipeline where multiple agents create and render dynamic content.

## Agent Flow

1. `CreatorAgent` creates a `Phema` (content structure + bindings).
2. `PulserAgent` fetches dynamic data for each binding key.
3. `PhemarAgent` binds pulse data into `{{binding.path}}` templates.
4. `CastrAgent` renders final output for the viewer in the selected format.

Supported viewer formats:
- `json`
- `markdown`
- `text`

## Quick Example

```python
from phemacast import PhemacastSystem, Persona

system = PhemacastSystem()

system.register_pulse_source("summary", lambda ctx: {"value": f"Market pulse for {ctx['symbol']}"})
system.register_pulse_source("price", lambda ctx: {"value": 63890.42})

phema = system.create_phema(
    title="BTC Brief",
    prompt="Creator view",
    bindings=["price"],
    default_persona=Persona(name="analyst", tone="professional", style="short"),
)

output, trace = system.cast(
    phema_id=phema.phema_id,
    viewer_format="markdown",
    context={"symbol": "BTC"},
)

print(output)
```

## Dynamic Binding Rules

- Template syntax: `{{binding.path}}`
- Root `binding` is a pulse key returned by `PulserAgent`
- Missing providers are returned as `{ "status": "missing-provider" }` to keep casts resilient
