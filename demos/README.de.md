# Öffentliche Demo-Leitfäden

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

## Hier beginnen

Wenn Sie sich für einen Demo zur ersten Erprobung entscheiden, verwenden Sie diese in der folgenden Reihenfolge:

1. [`hello-plaza`](./hello-plaza/README.md): der leichteste Multi-Agent-Discovery-Demo.
2. [`pulsers`](./pulsers/README.md): fokussierte Demos für Dateispeicherung, YFinance, LLM und ADS pulsers.
3. [`personal-research-workbench`](./personal-research-workbench/README.md): die visuellste Produktvorführung.
4. [`data-pipeline`](./data-pipeline/README.md): eine lokale, SQLite-gestützte ADS-Pipeline mit boss UI und pulser.

## Single-Command-Launcher

Jeder ausführbare Demo-Ordner enthält nun einen `run-demo.sh`-Wrapper, der die erforderlichen Dienste von einem Terminal aus startet, eine Browser-Anleitungsseite mit Sprachauswahl öffnet und die Haupt-UI-Seiten der Demo automatisch öffnet.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Wrapper im Terminal bleiben soll, ohne Browser-Tabs zu öffnen.

## Plattform Schnellstart

### macOS und Linux

Erstellen Sie im Repository-Root einmalig die virtuelle Umgebung, installieren Sie die Anforderungen und führen Sie dann einen beliebigen Demo-Wrapper wie `./demos/hello-plaza/run-demo.sh` aus:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Verwenden Sie WSL2 mit Ubuntu oder einer anderen Linux-Distribution. Führen Sie im Root-Verzeichnis des Repositorys innerhalb von WSL dieselben Befehle aus:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

Wenn Browser-Tabs nicht automatisch aus WSL heraus geöffnet werden, lassen Sie den Launcher weiter laufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

Native PowerShell / Command Prompt-Wrapper sind noch nicht enthalten, daher ist WSL2 heute der unterstützte Windows-Pfad.

## Gemeinsame Einrichtung

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Normalerweise möchten Sie 2-4 Terminalfenster geöffnet haben, da die meisten Demos einige lang laufende Prozesse starten.

Diese Demo-Ordner schreiben ihren Laufzeitstatus unter `demos/.../storage/`. Dieser Status wird von git ignoriert, sodass man frei experimentieren kann.

## Demo-Katalog

### [`hello-plaza`](./hello-plaza/README.md)

- Zielgruppe: Erstentwickler
- Laufzeitumgebung: Plaza + Worker + browserorientierter User Agent
- Externe Dienste: keine
- Was es beweist: Agent-Registrierung, Discovery und eine einfache Browser-UI

### [`pulsers`](./pulsers/README.md)

- Zielgruppe: Entwickler, die kleine, direkte Pulser-Beispiele suchen
- Laufzeitumgebung: kleine Plaza + Pulser-Stacks, plus ein ADS-Pulser-Leitfaden, der die SQLite-Pipeline wiederverwendet
- Externe Dienste: keine für die Dateispeicherung, Internet-Ausgang für YFinance und OpenAI, lokaler Ollama-Daemon für Ollama
- Was es beweist: eigenständige Pulser-Verpackung, Testen, anbieterspezifisches Pulse-Verhalten, wie Analysten ihre eigenen strukturiert oder promptgesteuerten Insight-Pulse veröffentlichen können und wie diese Pulse aus der Sicht eines Konsumenten innerhalb eines persönlichen Agents aussehen

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- Zielgruppe: Personen, die eine stärkere Produkt-Demo suchen
- Laufzeitumgebung: React/FastAPI Workbench + lokales Plaza + lokaler Datei-Speicher-Pulser + optionaler YFinance-Pulser + optionaler Technical-Analysis-Pulser + Seeded-Diagramm-Speicher
- Externe Dienste: keine für den Speicherfluss, Internet-Ausgang für den YFinance-Chart-Flow und den Live-OHLC-zu-RSI-Diagramm-Flow
- Was es beweist: Workspaces, Layouts, Plaza-Browsing, Chart-Rendering und diagrammgesteuerte Pulser-Ausführung aus einer reichhaltigeren UI

### [`data-pipeline`](./data-pipeline/README.md)

- Zielgruppe: Entwickler, die Orchestrierung und normalisierte Datenflüsse bewerten
- Laufzeitumgebung: ADS Dispatcher + Worker + Pulser + Boss-UI
- Externe Dienste: keine im Demo-Setup
- Was es beweist: Warteschlangen-Jobs, Worker-Ausführung, normalisierte Speicherung, Re-Exposition durch einen Pulser und der Pfad zum Einbinden eigener Datenquellen

## Für öffentliches Hosting

Diese Demos sind so konzipiert, dass sie nach einem erfolgreichen lokalen Durchlauf einfach selbst gehostet werden können. Wenn Sie sie öffentlich veröffentlichen, sind die sichersten Standardwerte:

- die gehosteten Demos schreibgeschützt machen oder sie nach einem Zeitplan zurücksetzen
- Deaktivieren Sie API-gestützte oder kostenpflichtige Integrationen in der ersten öffentlichen Version
- weisen Sie die Benutzer auf die von der Demo verwendeten Konfigurationsdateien hin, damit sie diese direkt forken können
- füge die exakten lokalen Befehle aus dem Demo-README neben der Live-URL hinzu
