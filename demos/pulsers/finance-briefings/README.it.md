# Demo del workflow di briefing finanziari

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

## Cosa mostra questa demo

- un `FinancialBriefingPulser` di proprietà di Attas che espone workflow-seed pulses e finance briefing step pulses
- un pulse di contesto di ingresso del workflow:
  - `prepare_finance_briefim_context`
  - distingue il workflow con `workflow_name`: `morning_desk_briefing`, `watchlist_check` o `research_roundup`
- pulse di passaggi finanziari condivisi:
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
- pulse di pubblicazione/esportazione downstream:
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## Perché esiste

MapPhemar esegue i diagrammi chiamando pulsers e pulses. I workflow di finance briefing sono iniziati come semplici funzioni Python in `attas`, ma gli attuali diagrammi suddividono questi workflow in nodi di passaggio modificabili, quindi il runtime ora utilizza un pulser nativo di Attas invece di un wrapper MCP generico.

La superficie di runtime è:

- [finance-briefings.pulser](./finance-briefings.pulser): configurazione demo per `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser`
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py): classe pulser di proprietà di Attas che ospita il seed del workflow e i pulse dei passaggi
- [briefings.py](../../../attas/workflows/briefings.py): helper per i passaggi di finance briefing pubblici utilizzati dal pulser

## Assunzioni di runtime

- Plaza a `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` a `http://127.0.0.1:8271`

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

Questo avvia il Plaza locale più il pulser dei briefing finanziari da un unico terminale, apre una pagina di guida nel browser e apre automaticamente l'interfaccia utente di pulser.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher finance-briefings
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio manuale

Dalla radice del repository:
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## File dei diagrammi correlati

Questi diagrammi si trovano in `demos/files/diagrams/`:

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

Ogni diagramma segue la stessa struttura modificabile:

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## Attualità di MapPhemar

Questi workflow si adattano all'attuale modello MapPhemar senza aggiungere un nuovo tipo di nodo o schema:

- i passaggi eseguibili sono nodi `rectangle` regolari
- i confini utilizzano `pill`
- la ramificazione rimane disponibile tramite `branch`
- la diffusione (fan-out) degli artefatti è gestita da molteplici archi in uscita dal nodo del workflow

Limitazione attuale dell'esecuzione:

- `Input` può connettersi a esattamente un nodo a valle, quindi la diffusione deve avvenire dopo il primo nodo di workflow eseguibile piuttosto che direttamente da `Input`

Non è stato necessario alcun nuovo tipo di nodo MapPhemar o estensione dello schema per questi workflow finanziari sequenziali. I regolari nodi eseguibili più la superficie Attas pulser sono sufficienti per l'attuale archiviazione, modifica ed esecuzione.
