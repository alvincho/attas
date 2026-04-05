# Phemacast

## Traducciones

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Flujo de Agentes

1. `CreatorAgent` crea un `Phema` (estructura de contenido + bindings).
2. `PulserAgent` obtiene datos dinámicos para cada clave de binding.
3. `PhemarAgent` vincula los datos de pulse en las plantillas `{{binding.path}}`.
4. `CastrAgent` renderiza la salida final para el espectador en el formato seleccionado.

Formatos de visor compatibles:
- `json`
- `markdown`
- `text`

## Ejemplo rápido
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

## Reglas de vinculación dinámica

- Sintaxis de plantilla: `{{binding.path}}`
- El `binding` raíz es una clave de pulso devuelta por `PulserAgent`
- Los proveedores faltantes se devuelven como `{ "status": "missing-provider" }` para mantener la resiliencia de los casts

## Capacidades planificadas de Phemacast

- más agentes `Phemar` centrados en representar la inteligencia humana, el juicio y la interpretación estructurada
- más agentes `Castr` que pueden producir salidas de un `Phema` en formatos como PDS, PPTX, páginas web y multimedia
- creación y refinamiento de `Pulse` generados por IA, informados por la retroalimentación humana, la eficiencia en tiempo de ejecución y el costo
- soporte de diagramas más amplio en `MapPhemar`
