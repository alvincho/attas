# Phemacast

## Traductions

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Flux d'Agents

1. `CreatorAgent` crée un `Phema` (structure de contenu + bindings).
2. `PulserAgent` récupère les données dynamiques pour chaque clé de binding.
3. `PhemarAgent` lie les données pulse dans les modèles `{{binding.path}}`.
4. `CastrAgent` génère la sortie finale pour le spectateur dans le format sélectionné.

Formats de visionnage pris en charge :
- `json`
- `markdown`
- `text`

## Exemple rapide
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

## Règles de liaison dynamique

- Syntaxe de modèle : `{{binding.path}}`
- Le `binding` racine est une clé de pulsation renvoyée par `PulserAgent`
- Les fournisseurs manquants sont renvoyés sous la forme `{ "status": "missing-provider" }` pour maintenir la résilience des casts

## Capacités prévues de Phemacast

- plus d'agents `Phemar` axés sur la représentation de l'intelligence humaine, du jugement et de l'interprétation structurée
- plus d'agents `Castr` pouvant produire des sorties à partir d'un `Phema` dans des formats tels que PDS, PPTX, pages web et multimédia
- création et affinement de `Pulse` générés par IA, basés sur les retours humains, l'efficacité d'exécution et le coût
- prise en charge de diagrammes plus large dans `MapPhemar`
