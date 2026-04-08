# Demo-Diagrammbibliothek

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

## Plattformhinweise

Dieser Ordner enthält JSON-Assets, keinen eigenständigen Launcher.

### macOS und Linux

Starten Sie zuerst eine der gekoppelten Demos und laden Sie dann diese Dateien in MapPhemar oder Personal Agent:
```bash
./demos/personal-research-workbench/run-demo.sh
```

Sie können auch starten:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Verwenden Sie eine native Windows-Python-Umgebung für die paarweisen Demo-Launcher, zum Beispiel `py -3 -m scripts.demo_launcher analyst-insights` und `py -3 -m scripts.demo_launcher finance-briefings`. Wenn der Stack läuft, öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser, falls die Tabs nicht automatisch geöffnet werden.

## Was befindet sich in diesem Ordner

Es gibt zwei Gruppen von Beispielen:

- technische Analyse-Diagramme, die OHLC-Marktdaten in Indikatorserien umwandeln
- LLM-orientierte Analysten-Diagramme, die rohe Marktnachrichten in strukturierte Forschungsnotizen umwandeln
- Finanz-Workflow-Diagramme, die normalisierte Forschungs-Inputs in Briefing-, Publikations- und NotebookLM-Export-Bundles umwandeln

## Dateien in diesem Ordner

### Technische Analyse

- `ohlc-to-sma-20-diagram.json`: `Input -> OHLC-Bars -> SMA 20 -> Output`
- `ohlc-to-ema-50-diagram.json`: `Input -> OHLC-Bars -> EMA 50 -> Output`
- `ohlc-to-macd-histogram-diagram.json`: `Input -> OHLC-Bars -> MACD-Histogramm -> Output`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `Input -> OHLC-Bars -> Bollinger-Bandbreite -> Output`
- `ohlc-to-adx-14-diagram.json`: `Input -> OHLC-Bars -> ADX 14 -> Output`
- `ohlc-to-obv-diagram.json`: `Input -> OHLC-Bars -> OBV -> Output`

### LLM / Analysten-Recherche

- `analyst-news-desk-brief-diagram.json`: `Input -> News Desk Briefing -> Output`
- `analyst-news-monitoring-points-diagram.json`: `Input -> Überwachungspunkte -> Output`
- `analyst-news-client-note-diagram.json`: `Input -> Kundennotiz -> Output`

### Finanz-Workflow-Paket

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `Input -> Morgenkontext vorbereiten -> Finanzschritt-Pulses -> Briefing zusammenstellen -> Report Phema + NotebookLM Paket -> Output`
- `finance-watchlist-check-notebooklm-diagram.json`: `Input -> Watchlist-Kontext vorbereiten -> Finanzschritt-Pulses -> Briefing zusammenstellen -> Report Phema + NotebookLM Paket -> Output`
- `finance-research-roundup-notebooklm-diagram.json`: `Input -> Forschungs-Kontext vorbereiten -> Finanzschritt-Pulses -> Briefing zusammenstellen -> Report Phema + NotebookLM Paket -> Output`

Diese drei gespeicherten Phemas bleiben zur Bearbeitung getrennt, teilen aber denselben Workflow-Einstiegs-Pulse und unterscheiden den Workflow durch den Knoten `paramsText.workflow_name`.

## Laufzeitannahmen

Diese Diagramme sind mit konkreten lokalen Adressen gespeichert, sodass sie ohne zusätzliche Bearbeitung ausgeführt werden können, wenn der erwartete Demo-Stack verfügbar ist.

### Technische Analyse-Diagramme

Die Indikator-Diagramme setzen voraus:

- Plaza unter `http://127.0.0.1:8241`
- `YFinancePulser` unter `http://127.0.0.1:8243`
- `TechnicalAnalysisPulser` unter `http://127.0.0.1:8244`

Die von diesen Diagrammen referenzierten Pulser-Konfigurationen befinden sich in:

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### LLM / Analysten-Diagramme

Die LLM-orientierten Diagramme setzen voraus:

- Plaza unter `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser` unter `http://127.0.0.1:8270`

Dieser Prompted-Analyst-Pulser selbst hängt ab von:

- `news-wire.pulser` unter `http://127.0.0.1:8268`
- `ollama.pulser` unter `http://127.0.0.1:8269`

Diese Demo-Dateien befinden sich in:

- `demos/pulsers/analyst-insights/`

### Finanz-Workflow-Diagramme

Die Finanz-Workflow-Diagramme setzen voraus:

- Plaza unter `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser` unter `http://127.0.0.1:8271`

Dieser Demo-Pulser ist ein Attas-eigenes `FinancialBriefingPulser`, unterstützt durch:

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

Diese Diagramme sind sowohl in MapPhemar als auch in den eingebetteten Personal Agent MapPhemar-Routen bearbeitbar, da es sich um gewöhnliche, diagrammbasierte Phema-JSON-Dateien handelt.

## Quickstart

### Option 1: Dateien in MapPhemar laden

1. Öffnen Sie eine MapPhemar-Editor-Instanz.
2. Laden Sie eine der JSON-Dateien aus diesem Ordner.
3. Bestätigen Sie, dass die gespeicherte `plazaUrl` und die Pulser-Adressen mit Ihrer lokalen Umgebung übereinstimmen.
4. Führen Sie `Test Run` mit einem der unten aufgeführten Beispiel-Payloads aus.

Wenn Ihre Dienste andere Ports oder Namen verwenden, bearbeiten Sie:

- `meta.map_phemar.diagram.plazaUrl`
- den `pulserName` jedes Knotens
- die `pulserAddress` jedes Knotens

### Option 2: Als Seed-Dateien verwenden

Sie können diese JSON-Dateien auch in einen beliebigen MapPhemar-Pool unter einem `phemas/`-Verzeichnis kopieren und sie über die Agent-UI auf die gleiche Weise laden, wie es die personal-research-workbench-Demo tut.

## Beispiel-Inputs

### Technische Analysediagramme

Verwenden Sie eine Payload wie:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

Erwartetes Ergebnis:

- der Schritt `OHLC Bars` ruft eine historische Bar-Serie ab
- der Indikatorknoten berechnet ein `values`-Array
- die endgültige Ausgabe gibt Zeitstempel/Wert-Paare zurück

### LLM / Analysten-Diagramme

Verwenden Sie eine Payload wie:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Erwartetes Ergebnis:

- der prompt-gesteuerte analyst pulser ruft Rohnachrichten ab
- das prompt pack wandelt diese Nachrichten in eine strukturierte Analystenansicht um
- die Ausgabe liefert forschungsbereite Felder wie `desk_note`, `monitor_now` oder `client_note`

### Finanz-Workflow-Diagramme

Verwenden Sie eine Payload wie:
```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

Erwartetes Ergebnis:

- der Workflow-Kontext-Knoten initialisiert den gewählten Finanz-Workflow
- die zwischengeschalteten Finanz-Knoten erstellen Quellen, Zitate, Fakten, Risiken, Katalysatoren, Konflikte, Erkenntnisse, Fragen und Zusammenfassungsblöcke
- der Assembly-Knoten erstellt ein `attas.finance_briefing` Payload
- der Report-Knoten konvertiert dieses Payload in ein statisches Phema
- der NotebookLM-Knoten generiert Export-Artefakte aus demselben Payload
- die finale Ausgabe führt alle drei Ergebnisse für die Inspektion in MapPhemar oder Personal Agent zusammen

## Aktuelle Editor-Beschränkungen

Diese Finanz-Workflows passen in das aktuelle MapPhemar-Modell, ohne dass ein neuer Knotentyp hinzugefügt werden muss.

Es gelten weiterhin zwei wichtige Laufzeitregeln:

- `Input` muss mit genau einer nachgeschalteten Form verbunden sein
- jeder ausführbare, nicht verzweigende Knoten muss sich auf einen Pulse und einen erreichbaren Pulser beziehen

Das bedeutet, dass das Fan-out des Workflows nach dem ersten ausführbaren Knoten erfolgen muss und die Workflow-Schritte weiterhin als in einem Pulser gehostete Pulse exponiert werden müssen, wenn das Diagramm von Ende zu Ende durchlaufen werden soll.

## Verwandte Demos

Wenn Sie die unterstützenden Dienste ausführen möchten, anstatt nur die Diagramme zu inspizieren:

- `demos/personal-research-workbench/README.md`: visueller Diagramm-Workflow mit dem Seeded-RSI-Beispiel
- `demos/pulsers/analyst-insights/README.md`: Prompted-Analyst-News-Stack, der von den LLM-orientierten Diagrammen verwendet wird
- `demos/pulsers/llm/README.md`: eigenständige `llm_chat` Pulser-Demo für OpenAI und Ollama

## Verifizierung

Diese Dateien sind durch die Repo-Tests abgedeckt:
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

Diese Testsuite überprüft, ob die gespeicherten Diagramme End-to-End gegen simulierte oder Referenz-pulser-Flows ausgeführt werden.
