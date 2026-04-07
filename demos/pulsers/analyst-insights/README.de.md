# Analyst Insight Pulser Demo

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

## Was diese Demo zeigt

- ein Analyst-eigener Pulser mit mehreren strukturierten Insight-Pulses
- ein zweiter Analyst-eigener Pulser, der auf einem separaten News-Agent und einem lokalen Ollama-Agent aufbaut
- eine saubere Methode, um Rohdaten der Quelle von den vom Analysten verfassten Prompits und den endgültigen, für Endverbraucher bestimmten Ausgaben zu trennen
- ein Durchlauf durch den persönlichen Agenten, der denselben Stack aus der Sicht eines anderen Benutzers zeigt
- die exaklten Dateien, die ein Analyst oder PM bearbeiten würde, um seine eigene Sichtweise zu veröffentlichen

## Dateien in diesem Ordner

- `plaza.agent`: Lokales Plaza für die Analyst-Pulser-Demo
- `analyst-insights.pulser`: `PathPulser`-Konfiguration, die den öffentlichen Pulse-Katalog definiert
- `analyst_insight_step.py`: Gemeinsame Transformationslogik plus das vorbereitete Analysten-Coverage-Paket
- `news-wire.pulser`: Lokaler Upstream-News-Agent, der vorbereitete `news_article`-Pakete veröffentlicht
- `news_wire_step.py`: Vorbereitete Roh-News-Pakete, die vom Upstream-News-Agent zurückgegeben werden
- `ollama.pulser`: Lokaler, von Ollama unterstützter `llm_chat`-Pulser für die Analysten-Prompt-Demo
- `analyst-news-ollala.pulser`: Zusammengesetzter Analysten-Pulser, der News abruft, analysteneigene Prompts anwendet, Ollama aufruft und das Ergebnis in mehrere Pulses normalisiert
- `analyst_news_ollama_step.py`: Das analysteneigene Prompt-Paket plus JSON-Normalisierungslogik
- `start-plaza.sh`: Plaza starten
- `start-pulser.sh`: Den festen strukturierten Analysten-Pulser starten
- `start-news-pulser.sh`: Den vorbereiteten Upstream-News-Agenten starten
- `start-ollama-pulser.sh`: Den lokalen Ollama-Pulser starten
- `start-analyst-news-pulser.sh`: Den Prompt-basierten Analysten-Pulser starten
- `start-personal-agent.sh`: Die UI des persönlichen Agenten für den Consumer-View-Durchlauf starten
- `run-demo.sh`: Die Demo aus einem Terminal starten und den Browser-Guide sowie die Haupt-UI-Seiten öffnen

## Start mit einem einzigen Befehl

Aus der Wurzel des Repositorys:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

Dieser Wrapper startet standardmäßig den leichtgewichtigen strukturierten Flow.

Um stattdessen den erweiterten News + Ollama + Personal-Agent-Flow zu starten:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Plattform Quick Start

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

Für den fortgeschrittenen Pfad:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

Verwenden Sie eine native Windows-Python-Umgebung. Aus der Wurzel des Repositorys in der PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

Für den fortgeschrittenen Pfad:
```powershell
$env:DEMO_ANALYST_MODE = "advanced"
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

Falls die Browser-Tabs nicht automatisch geöffnet werden, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

## Demo 1: Strukturierte Analystenansichten

Dies ist der rein lokale Pfad ohne LLM.

Öffnen Sie zwei Terminals aus der Wurzel des Repositorys.

### Terminal 1: Plaza starten
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet unter `http://127.0.0.1:8266`

### Terminal 2: den pulser starten
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8267`
- er registriert sich beim Plaza auf `http://127.0.0.1:8266`

## Im Browser ausprobieren

Öffnen Sie:

- `http://127.0.0.1:8267/`

Testen Sie dann diese Pulses mit `NVDA`:

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

Empfohlene Parameter für alle vier:
```json
{
  "symbol": "NVDA"
}
```

Was Sie sehen sollten:

- `rating_summary` gibt die Hauptentscheidung, das Ziel, das Vertrauen und eine kurze Zusammenfassung zurück
- `thesis_bullets` gibt die positive These in Form von Aufzählungspunkten zurück
- `risk_watch` gibt die Hauptrisiken sowie die zu überwachenden Punkte zurück
- `scenario_grid` gibt Bull-, Basis- und Bear-Szenarien in einem einzigen strukturierten Payload zurück

## Testen Sie es mit Curl

Headline-Bewertung:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

Kernpunkte der Thesis:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

Risikoüberwachung:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## So passt ein Analyst diese Demo an

Es gibt zwei Hauptbearbeitungspunkte.

### 1. Die eigentliche Research-Ansicht ändern

Bearbeiten:

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

Diese Datei enthält das initialisierte `ANALYST_COVERAGE`-Paket. Dort ändern Sie:

- abgedeckte Symbole
- Analystenname
- Rating-Labels
- Zielpreise
- These-Aufzählungspunkte
- Hauptrisiken
- Bull/Base/Bear-Szenarien

### 2. Den öffentlichen Pulse-Katalog ändern

Bearbeiten:

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

Diese Datei steuert:

- welche Pulses existieren
- den Namen und die Beschreibung jedes Pulse
- Input- und Output-Schemas
- Tags und Adressen

Wenn Sie einen neuen Insight-Pulse hinzufügen möchten, kopieren Sie einen der vorhandenen Einträge und verweisen Sie ihn auf eine neue `insight_view`.

## Warum dieses Muster nützlich ist

- Portfolio-Tools können nur nach `rating_summary` fragen
- Report-Builder können nach `thesis_bullets` fragen
- Risiko-Dashboards können nach `risk_watch` fragen
- Bewertungs-Tools können nach `scenario_grid` fragen

Das bedeutet, dass der Analyst nur einen Dienst veröffentlicht, aber verschiedene Konsumenten genau den Teil abrufen können, den sie benötigen.

## Wie es weitergeht

Sobald diese lokale pulser-Form Sinn ergibt, sind die nächsten Schritte:

1. weitere abgedeckte Symbole zum Analysten-Coverage-Paket hinzufügen
2. Quellschritte vor dem letzten Python-Schritt hinzufügen, wenn Sie Ihre eigene Sichtweise mit den Ausgaben von YFinance, ADS oder LLM mischen möchten
3. den pulser über ein gemeinsames Plaza anstelle nur des lokalen Demo-Plaza bereitstellen

## Demo 2: Analyst Prompt Pack + Ollama + Persönlicher Agent

Dieser zweite Flow zeigt ein realistischeres Analysten-Setup:

- ein Agent veröffentlicht rohe `news_article`-Daten
- ein zweiter Agent stellt `llm_chat` über Ollama bereit
- der analysteneigene pulser verwendet sein eigenes prompt pack, um diese Rohnachrichten in mehrere wiederverwendbare pulses zu transformieren
- Der persönliche Agent konsumiert die fertigen Pulses aus der Sicht eines anderen Benutzers

### Voraussetzungen für den Prompt-Flow

Stelle sicher, dass Ollama lokal läuft und das Modell existiert:

```bash
ollama serve
ollama pull qwen3:8b
```

Öffnen Sie dann fünf Terminals aus der Wurzel des Repositorys.

### Terminal 1: Plaza starten

Wenn Demo 1 noch läuft, verwenden Sie weiterhin dasselbe Plaza.
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet auf `http://127.0.0.1:8266`

### Terminal 2: Starten des Upstream-News-Agents
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

Erwartetes Ergebnis:

- der news pulser startet auf `http://127.0.0.1:8268`
- er registriert sich beim Plaza unter `http://127.0.0.1:8266`

### Terminal 3: den Ollama pulser starten
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

Erwartetes Ergebnis:

- der Ollama pulser startet auf `http://127.0.0.1:8269`
- er registriert sich bei Plaza unter `http://127.0.0.1:8266`

### Terminal 4: den prompted analyst pulser starten

Starten Sie dies erst, nachdem die News- und Ollama-Agents bereits laufen, da der pulser seine Sample-Chains während des Starts validiert.
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

Erwartetes Ergebnis:

- der angeforderte Analysten-Pulser startet auf `http://127.0.0.1:8270`
- er registriert sich bei Plaza unter `http://127.0.0.1:8266`

### Terminal 5: persönlichen Agent starten
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

Erwartetes Ergebnis:

- der persönliche Agent startet auf `http://127.0.0.1:8061`

### Probieren Sie den Prompted Analyst Pulser direkt aus

Öffnen Sie:

- `http://127.0.0.1:8270/`

Testen Sie dann diese Pulses mit `NVDA`:

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

Empfohlene Parameter:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Was Sie sehen sollten:

- `news_desk_brief` verwandelt die Upstream-Artikel in eine PM-Stil-Positionierung und eine kurze Notiz
- `news_monitoring_points` verwandelt dieselben Rohartikel in Beobachtungspunkte und Risikoflaggen
- `news_client_note` verwandelt dieselben Rohartikel in eine sauberere, kundenorientierte Notiz

Der wichtige Punkt ist, dass der Analyst die Prompits in einer Datei steuert, während Downstream-Benutzer nur stabile Pulse-Schnittstellen sehen.

### Den persönlichen Agenten aus der Sicht eines anderen Benutzers verwenden

Öffnen:

- `http://127.0.0.1:8061/`

Gehen Sie dann diesen Pfad durch:

1. Öffnen Sie `Settings`.
2. Gehen Sie zum Tab `Connection`.
3. Setzen Sie die Plaza-URL auf `http://127.0.0.1:8266`.
4. Klicken Sie auf `Refresh Plaza Catalog`.
5. Erstellen Sie ein `New Browser Window`.
6. Versetzen Sie das Browserfenster in den `edit`-Modus.
7. Fügen Sie ein erstes plain pane hinzu und richten Sie es auf `DemoAnalystNewsWirePulser -> news_article`.
8. Verwenden Sie Pane-Parameter:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. Klicken Sie auf `Get Data`, damit der Benutzer die Rohartikel sehen kann.
10. Fügen Sie ein zweites einfaches Fenster hinzu und verweisen Sie es auf `DemoAnalystPromptedNewsPulser -> news_desk_brief`.
11. Verwenden Sie dieselben Parameter erneut und klicken Sie auf `Get Data`.
12. Fügen Sie ein drittes Fenster mit entweder `news_monitoring_points` oder `news_client_note` hinzu.

Was Sie sehen sollten:

- ein Fenster zeigt die rohen Upstream-News von einem anderen Agenten
- das nächste Fenster zeigt die verarbeitete Ansicht des Analysten
- das dritte Fenster zeigt, wie dasselbe Analysten-Prompt-Paket eine andere Oberfläche für ein anderes Publikum veröffentlichen kann

Das ist die entscheidende Consumer-Story: Ein anderer Benutzer muss nicht die interne Kette kennen. Er durchsucht einfach Plaza, wählt einen Pulse aus und konsumiert das fertige Analysten-Ergebnis.

## Wie ein Analyst den Prompt-Flow anpasst

Es gibt drei Hauptbearbeitungspunkte in Demo 2.

### 1. Das Upstream-News-Paket ändern

Bearbeiten:

- `demos/pulsers/analyst-insights/news_wire_step.py`

Dort ändern Sie die Seed-Artikel, die der Upstream-Quellen-Agent veröffentlicht.

### 2. Die eigenen Prompts des Analysten ändern

Bearbeiten:

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

Diese Datei enthält das dem Analysten gehörende Prompt-Paket, einschließlich:

- Prompt-Profilnamen
- Zielgruppe und Zielsetzung
- Tonfall und Schreibstil
- Erforderlicher JSON-Ausgabevertrag

Dies ist der schnellste Weg, um aus denselben Rohnachrichten eine andere Forschungsstimme zu erzeugen.

### 3. Den öffentlichen Pulse-Katalog ändern

Bearbeiten:

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

Diese Datei steuert:

- welche prompted pulses existieren
- welches Prompt-Profil jeder Pulse verwendet
- welche Upstream-Agenten aufgerufen werden
- die Input- und Output-Schemas, die Downstream-Benutzern angezeigt werden

## Warum das fortgeschrittene Muster nützlich ist

- der Upstream-News-Agent kann später durch YFinance, ADS oder einen internen Collector ersetzt werden
- der Analyst behält die Inhaberschaft des Prompt-Packs, anstatt einmalige Notizen hart in einer UI zu kodieren
- verschiedene Konsumenten können verschiedene Pulses verwenden, ohne die vollständige dahinterliegende Kette zu kennen
- der persönliche Agent wird zu einer sauberen Consumer-Oberfläche, anstatt der Ort, an dem die Logik lebt
