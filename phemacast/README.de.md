# Phemacast

## Uebersetzungen

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Agenten-Ablauf

1. `CreatorAgent` erstellt ein `Phema` (Inhaltsstruktur + Bindings).
2. `PulserAgent` ruft dynamische Daten für jeden Binding-Schlüssel ab.
3. `PhemarAgent` bindet Pulse-Daten in `{{binding.path}}`-Templates ein.
4. `CastrAgent` rendert die endgültige Ausgabe für den Betrachter im ausgewählten Format.

Unterstützte Viewer-Formate:
- `json`
- `markdown`
- `text`

## Schnelles Beispiel
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

## Dynamische Bindungsregeln

- Template-Syntax: `{{binding.path}}`
- Das Root-`binding` ist ein Pulse-Key, der von `PulserAgent` zurückgegeben wird
- Fehlende Provider werden als `{ "status": "missing-provider" }` zurückgegeben, um die Resilienz der Casts zu gewährleisten

## Geplante Phemacast-Funktionen

- mehr `Phemar`-Agenten, die sich auf die Darstellung menschlicher Intelligenz, Urteilskraft und strukturierter Interpretation konzentrieren
- mehr `Castr`-Agenten, die Ausgaben von einem `Phema` in Formaten wie PDS, PPTX, Webseiten und Multimedia erzeugen können
- KI-generierte `Pulse`-Erstellung und -Verfeinerung basierend auf menschlichem Feedback, Laufzeiteffizienz und Kosten
- breitere Diagrammunterstützung in `MapPhemar`
