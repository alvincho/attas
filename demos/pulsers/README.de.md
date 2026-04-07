# Pulser Demo-Set

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

Verwenden Sie diese in der folgenden Reihenfolge, wenn Sie das pulser-Modell zum ersten Mal lernen:

1. [`file-storage`](./file-storage/README.md): die sicherste rein lokale pulser-Demo
2. [`analyst-insights`](./analyst-insights/README.md): ein pulser im Besitz eines Analysten, der als wiederverwendbare Insight-Ansichten bereitgestellt wird
3. [`finance-briefings`](./finance

## Single-Command-Launcher

Jeder ausführbare pulser-Demo-Ordner enthält nun einen `run-demo.sh`-Wrapper, der die erforderlichen lokalen Dienste von einem Terminal aus startet, eine Browser-Anleitungsseite mit Sprachauswahl öffnet und die primären Demo-UI-Seiten automatisch öffnet.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Wrapper im Terminal bleiben soll, ohne Browser-Tabs zu öffnen.

## Plattform-Schnellstart

### macOS und Linux

Erstellen Sie im Repository-Root einmalig die virtuelle Umgebung, installieren Sie die Anforderungen und führen Sie dann einen beliebigen pulser-Wrapper wie `./demos/pulsers/file-storage/run-demo.sh` aus:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Verwenden Sie eine native Windows-Python-Umgebung. Aus der Wurzel des Repositorys in der PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

Wenn sich die Browser-Tabs nicht automatisch öffnen, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

## Was dieser Demo-Satz abdeckt

- wie ein pulser sich bei Plaza registriert
- wie man Pulse über den Browser oder mit `curl` testet
- wie man einen pulser als kleinen selbst gehosteten Dienst verpackt
- wie sich verschiedene pulser-Familien verhalten: Speicherung, Analysten-Einblicke, Finanzen, LLM und Datendienste

## Gemeinsame Einrichtung

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Jeder Demo-Ordner schreibt den lokalen Laufzeitstatus unter `demos/pulsers/.../storage/`.

## Demo-Katalog

### [`file-storage`](./file-storage/README.md)

- Runtime: Plaza + `SystemPulser`
- Externe Dienste: keine
- Was es beweist: Bucket-Erstellung, Objekt speichern/laden und rein lokaler Pulser-Status

### [`analyst-insights`](./analyst-insights/README.md)

- Runtime: Plaza + `PathPulser`
- Externe Dienste: keine für die strukturierte Ansicht, lokales Ollama für den Prompt-basierten News-Flow
- Was es beweist: wie ein Analyst sowohl feste Forschungsansichten als auch Prompt-gesteuerte Ollama-Ausgaben über mehrere wiederverwendbare Pulses veröffentlichen kann, um sie dann einem anderen Benutzer über einen persönlichen Agenten zugänglich zu machen

### [`finance-briefings`](./finance-briefages/README.md)

- Runtime: Plaza + `FinancialBriefingPulser`
- Externe Dienste: keine im lokalen Demo-Pfad
- Was es beweist: wie ein Attas-besitzender Pulser Finanz-Workflow-Schritte als Pulse-adressierbare Bausteine veröffentlichen kann, sodass MapPhemar diagrams und Personal Agent denselben Workflow-Graphen speichern, bearbeiten und ausführen können

### [`yfinance`](./yfinance/README.md)

- Runtime: Plaza + `YFinancePulser`
- Externe Dienste: Internetverbindung zu Yahoo Finance
- Was es beweist: Snapshot-Pulses, OHLC-Serien-Pulses und grafikfreundliche Output-Payloads

### [`llm`](./llm/README.md)

- Runtime: Plaza + `OpenAIPulser`, konfiguriert für OpenAI oder Ollama
- Externe Dienste: OpenAI API für den Cloud-Modus, lokaler Ollama-Daemon für den lokalen Modus
- Was es beweist: `llm_chat`, gemeinsam genutzte Pulser-Editor-UI und anbieterwechselbare LLM-Infrastruktur

### [`ads`](./ads/README.md)

- Runtime: ADS dispatcher + worker + pulser + boss UI
- Externe Dienste: keine im SQLite-Demo-Pfad
- Was es beweist: `ADSPulser` auf Basis normalisierter Datentabellen und wie eigene Collector in diese Pulses einfließen
