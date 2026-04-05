# Demo des Finance-Briefing-Workflows

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

- ein Attas-eigenes `FinancialBriefingPulser`, das workflow-seed pulses und finance briefing step pulses bereitstellt
- ein Workflow-Eintritts-Kontext-Pulse:
  - `prepare_finance_briefing_context`
  - Unterscheidung des Workflows mit `workflow_name`: `morning_desk_imbriefing`, `watchlist_check` oder `research_roundup`
- gemeinsame Finanzschritt-Pulses:
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_briefing_payload`
- Downstream-Veröffentlichungs-/Export-Pulses:
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## Warum dies existiert

MapPhemar führt Diagramme aus, indem es pulsers und pulses aufruft. Die finance briefing Workflows begannen als einfache Python-Funktionen in `attas`, aber die aktuellen Diagramme unterteilen diese Workflows in editierbare Schrittknoten, sodass die Laufzeit nun einen Attas-nativen pulser anstelle eines generischen MCP-Wrappers verwendet.

Die Runtime-Oberfläche ist:

- [finance-briefings.pulument](./finance-briefings.pulser): Demo-Konfiguration für `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser`
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): Attas-eigene pulser-Klasse, die den Workflow-Seed und die Schritt-Pulses hostet
- [briefings.py](../../../attas/workflows/briefings.py): öffentliche finance briefing Schritt-Helfer, die vom pulser verwendet werden

## Laufzeitannahmen

- Plaza unter `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` unter `http://127.0.0.1:8271`

## Start mit einem einzigen Befehl

Aus der Wurzel des Repositorys:
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

Dies startet den lokalen Plaza sowie den Finance Briefing Pulser von einem Terminal aus, öffnet eine Browser-Anleitungsseite und öffnet automatisch die Pulser-UI.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Plattform Quick Start

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Verwenden Sie WSL2 mit Ubuntu oder einer anderen Linux-Distribution. Aus dem Repository-Root innerhalb von WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

Wenn Browser-Tabs nicht automatisch aus WSL heraus geöffnet werden, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

Native PowerShell / Command Prompt Wrapper sind noch nicht eingecheckt, daher ist WSL2 heute der unterstützte Windows-Pfad.

## Manueller Start

Aus dem Repository-Root:
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## Verwandte Diagrammdateien

Diese Diagramme befinden sich in `demos/files/diagrams/`:

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

Jedes Diagramm folgt derselben editierbaren Struktur:

`Input -> Workflow Context -> Finance Step

Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## Aktuelle MapPhemar-Passgenauigkeit

Diese Workflows lassen sich in das aktuelle MapPhemar-Modell integrieren, ohne einen neuen Knotentyp oder ein neues Schema hinzuzufügen:

- ausführbare Schritte sind reguläre `rectangle`-Knoten
- Grenzen verwenden `pill`
- Verzweigungen bleiben über `branch` verfügbar
- das Fan-out von Artefakten wird durch mehrere ausgehende Kanten des Workflow-Knotens gehandhabt

Aktuelle Laufzeitbeschränkung:

- `Input` kann mit genau einem nachgeschalteten Knoten verbunden werden, daher muss das Fan-out nach dem ersten ausführbaren Workflow-Knoten erfolgen und nicht direkt von `Input` aus

Für diese schrittweisen Finanz-Workflows war kein neuer MapPhemar-Knotentyp oder eine Schemaerweiterung erforderlich. Reguläre ausführbare Knoten plus die Attas pulser Oberfläche reichen für die aktuelle Speicherung, Bearbeitung und Ausführung aus.
