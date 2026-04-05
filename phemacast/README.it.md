# Phemacast

## Traduzioni

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Flusso degli Agent

1. `CreatorAgent` crea un `Phema` (struttura dei contenuti + binding).
2. `PulserAgent` recupera i dati dinamici per ogni chiave di binding.
3. `PhemarAgent` lega i dati pulse nei template `{{binding.path}}`.
4. `CastrAgent` renderizza l'output finale per lo spettatore nel formato selezionato.

Formati di visualizzazione supportati:
- `json`
- `markdown`
- `text`

## Esempio rapido
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

## Regole di binding dinamico

- Sintassi del template: `{{binding.path}}`
- Il `binding` radice è una chiave di impulso restituita da `PulserAgent`
- I provider mancanti vengono restituiti come `{ "status": "missing-provider" }` per mantenere la resilienza dei cast

## Capacità pianificate di Phemacast

- più agenti `Phemar` focalizzati sulla rappresentazione dell'intelligenza umana, del giudizio e dell'interpretazione strutturata
- più agenti `Castr` in grado di produrre output da un `Phema` in formati quali PDS, PPTX, pagine web e multimedia
- creazione e perfezionamento di `Pulse` generati dall'IA, basati sul feedback umano, l'efficienza di runtime e i costi
- supporto diagrammi più ampio in `MapPhemar`
