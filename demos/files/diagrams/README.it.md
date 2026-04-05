# Libreria di diagrammi demo

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

## Note sulla piattaforma

Questa cartella contiene asset JSON, non un launcher indipendente.

### macOS e Linux

Avvia prima uno dei demo accoppiati, quindi carica questi file in MapPhemar o Personal Agent:
```bash
./demos/personal-research-workbench/run-demo.sh
```

È possibile avviare anche:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Utilizzare WSL2 con Ubuntu o un'altra distribuzione Linux per i launcher demo accoppiati. Dopo l'avvio dello stack, aprire l'URL `guide=` stampata in un browser Windows se le schede non si aprono automaticamente.

I wrapper nativi per PowerShell / Command Prompt non sono ancora stati inclusi, quindi oggi la strada supportata su Windows è WSL2.

## Cosa c'è in questa cartella

Ci sono due gruppi di esempi:

- diagrammi di analisi tecnica che trasformano i dati di mercato OHLC in serie di indicatori
- diagrammi di analisti orientati agli LLM che trasformano le notizie di mercato grezze in note di ricerca strutturate
- diagrammi di workflow finanziario che trasformano gli input di ricerca normalizzati in pacchetti di briefing, pubblicazione ed esportazione per NotebookLM

## File in questa cartella

### Analisi tecnica

- `ohlc-to-sma-20-diagram.json`: `Input -> Barre OHLC -> SMA 20 -> Output`
- `ohlc-to-ema-50-diagram.json`: `Input -> Barre OHLC -> EMA 50 -> Output`
- `ohlc-to-macd-histogram-diagram.json`: `Input -> Istogramma MACD -> Output`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `Input -> Bande di Bollinger -> Output`
- `ohlc-to-adx-14-diagram.json`: `Input -> Barre OHLC -> ADX 14 -> Output`
- `ohlc-to-obv-diagram.json`: `Input -> Barre OHLC -> OBV -> Output`

### Ricerca LLM / Analista

- `analyst-news-desk-brief-diagram.json`: `Input -> Briefing della redazione -> Output`
- `analyst-news-monitoring-points-diagram.json`: `Input -> Punti di monitoraggio -> Output`
- `analyst-news-client-note-diagram.json`: `Input -> Nota per il cliente -> Output`

### Pacchetto Workflow Finanziario

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `Input -> Prepara contesto mattutino -> Pulse passaggi finanziari -> Assembla briefing -> Report pacchetto Phema + NotebookLM -> Output`
- `finance-watchlist-check-notebooklm-diagram.json`: `Input -> Prepara contesto watchlist -> Pulse passaggi finanziari -> Assembla briefing -> Report pacchetto Phema + NotebookLM -> Output`
- `finance-research-roundup-notebooklm-diagram.json`: `Input -> Prepara contesto ricerca -> Pulse passaggi finanziari -> Assembla briefing -> Report pacchetto Phema + NotebookLM -> Output`

Questi tre Phemas salvati rimangono separati per la modifica, ma condividono lo stesso workflow-entry pulse e distinguono il workflow con il nodo `paramsText.workflow_name`.

## Assunzioni di runtime

Questi diagrammi sono salvati con indirizzi locali concreti in modo da poter essere eseguiti senza ulteriori modifiche quando lo stack demo previsto è disponibile.

### Diagrammi di analisi tecnica

I diagrammi degli indicatori assumono:

- Plaza a `http://127.0.0.1:8011`
- `YFinancePulser` a `http://127.0.0.1:8020`
- `TechnicalAnalysisPulser` a `http://127.0.0.1:8033`

Le configurazioni pulser referenziate da questi diagrammi si trovano in:

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### Diagrammi LLM / Analyst

I diagrammi orientati all'LLM assumono:

- Plaza a `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser` a `http://12rypt.0.0.1:8270`

Quel pulser dell'analista basato su prompt dipende a sua volta da:

- `news-wire.pulser` a `http://127.0.0.1:8268`
- `ollama.pulser` a `http://127.0.0.1:8269`

Quei file demo si trovano in:

- `demos/pulsers/analyst-insights/`

### Diagrammi di workflow finanziario

I diagrammi del workflow finanziario assumono:

- Plaza a `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser` a `http://127.0.0.1:8271`

Quel pulser demo è un `FinancialBriefingPulser` di proprietà di Attas supportato da:

- `demos/pulsers/finance-briefines/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

Questi diagrammi sono modificabili sia in MapPhemar che nelle rotte integrate di Personal Agent MapPhemar perché sono comuni file JSON Phema basati su diagrammi.

## Avvio rapido

### Opzione 1: Caricare i file in MapPhemar

1. Apri un'istanza dell'editor MapPhemar.
2. Carica uno dei file JSON presenti in questa cartella.
3. Conferma che il `plazaUrl` salvato e gli indirizzi pulser corrispondano al tuo ambiente locale.
4. Esegui `Test Run` con uno dei payload di esempio qui sotto.

Se i tuoi servizi utilizzano porte o nomi diversi, modifica:

- `meta.map_phemar.diagram.plazaUrl`
- il `pulserName` di ogni nodo
- la `pulserAddress` di ogni nodo

### Opzione 2: Utilizzarli come file seed

Puoi anche copiare questi file JSON in qualsiasi pool MapPhemar sotto una directory `phemas/` e caricarli tramite l'interfaccia utente dell'agente nello stesso modo in cui viene fatto nella demo personal-research-workbench.

## Input di esempio

### Diagrammi di analisi tecnica

Utilizza un payload come:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

Risultato previsto:

- il passaggio `OHLC Bars` recupera una serie storica di barre
- il nodo dell'indicatore calcola un array `values`
- l'output finale restituisce coppie timestamp/valore

### Diagrammi LLM / Analista

Usa un payload come:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Risultato previsto:

- l'analyst pulser basato su prompt recupera le notizie grezze
- il prompt pack trasforma tali notizie in una vista analista strutturata
- l'output restituisce campi pronti per la ricerca come `desk_note`, `monitor_now` o `client_note`

### Diagrammi del flusso di lavoro finanziario

Usa un payload come:
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

Risultato previsto:

- il nodo del contesto del workflow avvia il workflow finanziario scelto
- i nodi finanziari intermedi costruiscono fonti, citazioni, fatti, rischi, catalizzatori, conflitti, punti chiave, domande e blocchi di riepilogo
- il nodo di assemblaggio costruisce un payload `attas.finance_briefing`
- il nodo di report converte quel payload in un Phema statico
- il nodo NotebookLM genera artefatti di esportazione dallo stesso payload
- l'output finale unisce tutti e tre i risultati per l'ispezione in MapPhemar o Personal Agent

## Limiti attuali dell'editor

Questi workflow finanziari si adattano all'attuale modello MapPhemar senza aggiungere un nuovo tipo di nodo.

Si applicano ancora due importanti regole di runtime:

- `Input` deve connettersi esattamente a una forma a valle
- ogni nodo eseguibile non ramificato deve fare riferimento a un pulse più un pulser raggiungibile

Ciò significa che l'espansione (fan-out) del workflow deve avvenire dopo il primo nodo eseguibile, e i passaggi del workflow devono ancora essere esposti come pulse ospitati da un pulser se si desidera che il diagramma venga eseguito end-to-end.

## Demo Correlate

Se desideri eseguire i servizi di supporto invece di ispezionare solo i diagrammi:

- `demos/personal-research-workbench/README.md`: workflow di diagramma visivo con l'esempio RSI seedato
- `demos/pulsers/analyst-insights/README.md`: stack di notizie dell'analista con prompt utilizzato dai diagrammi orientati a LLM
- `demos/pulsers/llm/README.md`: demo pulser `llm_chat` standalone per OpenAI e Ollama

## Verifica

Questi file sono coperti dai test del repository:
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

Quella suite di test verifica che i diagrammi salvati vengano eseguiti end-to-end rispetto a flussi pulser simulati o di riferimento.
