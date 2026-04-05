# Set di demo Pulser

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

## Inizia qui

Usali in questo ordine se stai imparando il modello pulser per la prima volta:

1. [`file-storage`](./file-storage/README.md): la demo pulser locale più sicura
2. [`analyst-insights`](./analyst-insights/README.md): un pulser di proprietà di un analista ed esposto come viste di approfondimento riutilizzabili
3. [`finance-briefings`](./finance-briefings/README.md): pulse di workflow finanziario pubblicati in una forma che MapPhemar e Personal Agent possono eseguire
4. [`yfinance`](./yfinance/README.md): un pulser di dati di mercato in tempo reale con output di serie temporali
5. [`llm`](./llm/README.md): pulser di chat locali Ollama e cloud OpenAI
6. [`ads`](./ads/README.md): il pulser ADS come parte della demo della pipeline SQLite

## Launcher a comando singolo

Ogni cartella demo di pulser eseguibile include ora un wrapper `run-demo.sh` che avvia i servizi locali richiesti da un unico terminale, apre una pagina di guida nel browser con selezione della lingua e apre automaticamente le pagine principali dell'interfaccia utente della demo.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il wrapper rimanga nel terminale senza aprire schede del browser.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository, crea l'ambiente virtuale una sola volta, installa i requisiti, quindi esegui qualsiasi wrapper pulser come `./demos/pulsers/file-storage/run-demo.sh`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Utilizza WSL2 con Ubuntu o un'altra distribuzione Linux. Dalla radice del repository all'interno di WSL, esegui gli stessi comandi:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

Se le schede del browser non si aprono automaticamente da WSL, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

I wrapper nativi per PowerShell / Command Prompt non sono ancora stati inclusi, quindi oggi la strada Windows supportata è WSL2.

## Cosa copre questo set di demo

- come un pulser si registra con Plaza
- come testare i impulsi dal browser o con `curl`
- come pacchettizzare un pulser come un piccolo servizio self-hosted
- come si comportano le diverse famiglie di pulser: archiviazione, insight dell'analista, finanza, LLM e servizi dati

## Configurazione condivisa

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Ogni cartella demo scrive lo stato di runtime locale in `demos/pulsers/.../storage/`.

## Catalogo Demo

### [`file-storage`](./file-storage/README.md)

- Runtime: Plaza + `SystemPulser`
- Servizi esterni: nessuno
- Cosa dimostra: creazione di bucket, salvataggio/caricamento di oggetti e stato del pulser solo locale

### [`analyst-insights`](./analyst-insights/README.md)

- Runtime: Plaza + `PathPulser`
- Servizi esterni: nessuno per la vista strutturata, Ollama locale per il flusso di notizie basato su prompt
- Cosa dimostra: come un analista possa pubblicare sia viste di ricerca fisse che output di Ollama di proprietà dei prompt attraverso molteplici pulse riutilizzabili, per poi esporli a un altro utente tramite un agente personale

### [`finance-briefings`](./finance-briefings/

- Runtime: Plaza + `FinancialBriefingPulser`
- Servizi esterni: nessuno nel percorso demo locale
- Cosa dimostra: come un pulser di proprietà di Attas possa pubblicare passaggi di workflow finanziario come blocchi costruttivi indirizzabili tramite pulse, in modo che MapPhemar diagrams e Personal Agent possano memorizzare, modificare ed eseguire lo stesso grafo di workflow

### [`yfinance`](./yfinance/README.md)

- Runtime: Plaza + `YFinancePulser`
- Servizi esterni: connessione internet verso Yahoo Finance
- Cosa dimostra: pulse snapshot, pulse di serie OHLC e payload di output adatti ai grafici

### [`llm`](./llm/README.md)

- Runtime: Plaza + `OpenAIPulser` configurato per OpenAI o Ollama
- Servizi esterni: API OpenAI per la modalità cloud, daemon locale di Ollama per la modalità locale
- Cosa dimostra: `llm_chat`, interfaccia utente dell'editor di pulser condivisa e infrastruttura LLM con fornitore intercambiabile

### [`ads`](./ads/README.md)

- Runtime: ADS dispatcher + worker + pulser + boss UI
- Servizi esterni: nessuno nel percorso demo SQLite
- Cosa dimostra: `ADSPulser` su tabelle dati normalizzate e come i propri collector fluiscono in quei pulse
