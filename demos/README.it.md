# Guide alle demo pubbliche

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

Se stai scegliendo un demo da provare per primo, utilizzali in questo ordine:

1. [`hello-plaza`](./hello-plaza/README.md): il demo di scoperta multi-agente più leggero.
2. [`pulsers`](./pulsers/README.md): demo focalizzati su archiviazione file, YFinance, LLM e ADS pulsers.
3. [`personal-research-workbench`](./personal-research-workbench/README.md): la presentazione del prodotto più visiva.
4. [`data-pipeline`](./data-pipeline/README.md): una pipeline ADS con supporto SQLite locale con boss UI e pulser.

## Launcher con singolo comando

Ogni cartella demo eseguibile include ora un wrapper `run-demo.sh` che avvia i servizi richiesti da un unico terminale, apre una pagina di guida nel browser con selezione della lingua e apre automaticamente le pagine principali dell'interfaccia utente della demo.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il wrapper rimanga nel terminale senza aprire schede del browser.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository, crea l'ambiente virtuale una sola volta, installa i requisiti, quindi esegui qualsiasi wrapper demo come `./demos/hello-plaza/run-demo.sh`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Utilizza WSL2 con Ubuntu o un'altra distribuzione Linux. Dalla radice del repository all'interno di WSL, esegui gli stessi comandi:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

Se le schede del browser non si aprono automaticamente da WSL, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

I wrapper nativi per PowerShell / Command Prompt non sono ancora stati inclusi, quindi oggi la strada Windows supportata è WSL2.

## Configurazione condivisa

Dalla root del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Di solito vorrai avere aperte 2-4 finestre del terminale, perché la maggior parte dei demo avvia alcuni processi a lunga esecuzione.

Queste cartelle demo scrivono il proprio stato di runtime in `demos/.../storage/`. Tale stato viene ignorato da git, così le persone possono sperimentare liberamente.

## Catalogo Demo

### [`hello-plaza`](./hello-plaza/README.md)

- Pubblico: sviluppatori alle prime armi
- Runtime: Plaza + worker + user agent orientato al browser
- Servizi esterni: nessuno
- Cosa dimostra: registrazione agent, discovery e una semplice interfaccia utente nel browser

### [`pulsers`](./pulserm/README.md)

- Pubblico: sviluppatori che desiderano esempi di pulser piccoli e diretti
- Runtime: stack Plaza + pulser ridotti, oltre a una guida ADS pulser che riutilizza la pipeline SQLite
- Servizi esterni: nessuno per l'archiviazione dei file, internet in uscita per YFinance e OpenAI, daemon locale Ollama per Ollama
- Cosa dimostra: packaging pulser standalone, test, comportamento del pulse specifico del provider, come gli analisti possono pubblicare i propri pulse di insight strutturati o guidati da prompt, e come questi pulse appaiono all'interno di un agent personale dal punto di vista del consumatore

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- Pubblico: persone che desiderano una demo di prodotto più completa
- Runtime: workbench React/FastAPI + Plaza locale + pulser di archiviazione file locale + pulser YFinance opzionale + pulser di analisi tecnica opzionale + archiviazione diagrammi con seed
- Servizi esterni: nessuno per il flusso di archiviazione, internet in uscita per il flusso dei grafici YFinance e il flusso dei diagrammi OHLC-to-RSI live
- Cosa dimostra: workspace, layout, navigazione Plaza, rendering di grafici ed esecuzione di pulser guidata da diagrammi da un'interfaccia utente più ricca

### [`data-pipeline`](./data-pipeline/README.md)

- Pubblico: sviluppatori che valutano l'orchestrazione e i flussi di dati normalizzati
- Runtime: ADS dispatcher + worker + pulser + interfaccia boss
- Servizi esterni: nessuno nella configurazione della demo
- Cosa dimostra: job in coda, esecuzione worker, archiviazione normalizzata, re-esposizione tramite un pulser e il percorso per collegare le proprie fonti dati

## Per l'hosting pubblico

Queste demo sono progettate per essere facili da auto-ospitare dopo che un'esecuzione locale ha avuto successo. Se le pubblichi pubblicamente, i valori predefiniti più sicuri sono:

- rendere le demo ospitate in sola lettura o reimpostarle secondo una pianificazione
- disattiva le integrazioni basate su API o a pagamento nella prima versione pubblica
- indirizza le persone verso i file di configurazione utilizzati dalla demo in modo che possano fare il fork direttamente
- includi i comandi locali esatti del README della demo accanto all'URL live
