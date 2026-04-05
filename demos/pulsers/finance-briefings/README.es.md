# Demo del flujo de trabajo de informes financieros

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

## Qué muestra esta demo

- un `FinancialBriefingPulser` propiedad de Attas que expone workflow-seed pulses y finance briefing step pulses
- un pulse de contexto de entrada de flujo de trabajo:
  - `prepare_finance_briefing_context`
  - distingue el flujo de trabajo con `workflow_name`: `morning_desk_briefing`, `watchlist_check` o `research_roundup`
- pulses de pasos financieros compartidos:
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
- pulses de publicación/exportación downstream:
  - `briefing_to_imphema`
  - `notebooklm_export_pack`

## Por qué existe esto

MapPhemar ejecuta diagramas llamando a pulsers y pulses. Los flujos de trabajo de finance briefing comenzaron como funciones simples de Python en `attas`, pero los diagramas actuales dividen esos flujos de trabajo en nodos de paso editables, por lo que el tiempo de ejecución ahora utiliza un pulser nativo de Attas en lugar de un envoltorio MCP genérico.

La superficie de ejecución es:

- [finance-briefings.pulser](./finance-breifings.pulser): configuración de demo para `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser`
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): clase pulser propiedad de Attas que aloja la semilla del flujo de trabajo y los pasos de pulses
- [briefings.py](../../../attas/workflows/briefings.py): ayudantes de paso de finance briefing públicos consumidos por el pulser

## Suposiciones de tiempo de ejecución

- Plaza en `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` en `http://127.0.0.1:8271`

## Lanzamiento con un solo comando

Desde la raíz del repositorio:
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

Esto inicia el Plaza local más el pulser de informes financieros desde una sola terminal, abre una página de guía en el navegador y abre la interfaz de usuario de pulser automáticamente.

Establezca `DEMO_OPEN_BROWSER=0` si desea que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Utilice WSL2 con Ubuntu u otra distribución de Linux. Desde la raíz del repositorio dentro de WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

Si las pestañas del navegador no se abren automáticamente desde WSL, mantén el lanzador ejecutándose y abre la URL `guide=` impresa en un navegador de Windows.

Los wrappers nativos de PowerShell / Command Prompt aún no se han incluido, por lo que hoy en día la ruta de Windows compatible es WSL2.

## Lanzamiento manual

Desde la raíz del repositorio:
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## Archivos de diagramas relacionados

Estos diagramas se encuentran en `demos/files/diagrams/`:

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

Cada diagrama sigue la misma estructura editable:

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## Ajuste actual de MapPhemar

Estos flujos de trabajo encajan dentro del modelo MapPhemar actual sin añadir un nuevo tipo de nodo o esquema:

- los pasos ejecutables son nodos `rectangle` regulares
- los límites utilizan `pill`
- la ramificación sigue disponible a través de `branch`
- la dispersión (fan-out) de artefactos se gestiona mediante múltiples bordes salientes del nodo de flujo de trabajo

Limitación actual de tiempo de ejecución:

- `Input` puede conectarse a exactamente un nodo descendente, por lo que la dispersión debe ocurrir después del primer nodo de flujo de trabajo ejecutable en lugar de directamente desde `Input`

No se necesitó ningún nuevo tipo de nodo MapPhemar ni extensión de esquema para estos flujos de trabajo financieros paso a paso. Los nodos ejecutables regulares más la superficie de Attas pulser son suficientes para el almacenamiento, la edición y la ejecución actuales.
