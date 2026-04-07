# Banco di Lavoro per la Ricerca Personale

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

- l'interfaccia utente del banco di lavoro personale in esecuzione localmente
- un Plaza che il banco di lavoro può consultare
- pulser di dati locali e in tempo reale con pulse reali eseguibili
- un flusso `Test Run` basato su diagrammi che trasforma i dati di mercato in una serie di indicatori calcolati
- un percorso da una demo rifinita a un'istanza self-hosted

## File in questa cartella

- `plaza.agent`: Plaza locale utilizzato solo per questa demo
- `file-storage.pulser`: pulser locale basato sul file system
- `yfinance.pulser`: pulser di dati di mercato opzionale basato sul modulo Python `yfinance`
- `technical-analysis.pulser`: pulser di percorso opzionale che calcola l'RSI dai dati OHLC
- `map_phemar.phemar`: configurazione MapPhemar locale della demo utilizzata dall'editor di diagrammi integrato
- `map_phemar_pool/`: archiviazione di diagrammi con una mappa OHLC-to-RSI pronta all'uso
- `start-plaza.sh`: avvia la demo Plaza
- `start-file-storage-pulser.sh`: avvia il pulser
- `start-yfinance-pulser.sh`: avvia il pulser YFinance
- `start-technical-analysis-pulser.sh`: avvia il pulser di analisi tecnica
- `start-workbench.sh`: avvia il workbench React/FastAPI

Tutti gli stati di runtime vengono scritti in `demos/personal-research-workbench/storage/`. Il launcher punta inoltre l'editor di diagrammi integrato ai file preconfigurati `map_phemar.phemar` e `map_phemar_pool/` in questa cartella.

## Prerequisiti

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/personal-research-workbench/run-demo.sh
```

Questo avvia lo stack del workbench da un terminale, apre una pagina di guida nel browser e quindi apre sia l'interfaccia utente principale di workbench che la rotta `MapPhemar` incorporata utilizzata nella guida principale.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher personal-research-workbench
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio rapido

Apri cinque terminali dalla radice del repository se desideri la demo completa, incluso il flusso del grafico YFinance e il flusso di test del diagramma.

### Terminal 1: avvia il Plaza locale

```bash
./demos/personal-research-workbench/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8241`

### Terminal 2: avvia il pulser di archiviazione file locale
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

Risultato atteso:

- il pulser si avvia su `http://127.0.0.1:8242`
- si registra presso il Plaza dal Terminal 1

### Terminal 3: avvia il pulser YFinance
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

Risultato previsto:

- il pulser si avvia su `http://127.0.0.1:8243`
- si registra presso il Plaza dal Terminal 1

Nota:

- questo passaggio richiede l'accesso a Internet in uscita perché il pulser recupera dati in tempo reale da Yahoo Finance tramite il modulo `yfinance`
- Yahoo può occasionalmente limitare la frequenza delle richieste, quindi questo flusso è meglio da considerare come una demo dal vivo piuttosto che come una parte fissa rigorosa

### Terminal 4: avvia il pulser di analisi tecnica
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

Risultato atteso:

- il pulser si avvia su `http://127.0.0.1:8244`
- si registra presso il Plaza dal Terminal 1

Questo pulser calcola `rsi` da un `ohlc_series` in entrata, oppure recupera le barre OHLC dal pulser demo YFinance quando si forniscono solo symbol, interval e date range.

### Terminal 5: avvia il workbench
```bash
./demos/personal-research-workbench/start-workbench.sh
```

Risultato previsto:

- il workbench si avvia su `http://127.0.0.1:8041`

## Guida alla prima esecuzione

Questa demo ha ora tre flussi di lavoro (workbench):

1. flusso di archiviazione locale con il pulser file-storage
2. flusso di dati di mercato in tempo reale con il pulser YFinance
3. flusso di test del diagramma con i pulsers YFinance e technical-analysis

Apri:

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### Flusso 1: sfoglia e salva dati locali

Segui poi questo breve percorso:

1. Apri il flusso delle impostazioni nel workbench.
2. Vai alla sezione `Connection`.
3. Imposta l'URL predefinito di Plaza su `http://127.0.0.1:8241`.
4. Aggiorna il catalogo Plaza.
5. Apri o crea una finestra del browser nel workbench.
6. Scegli il pulser file-storage registrato.
7. Esegui uno dei pulse integrati come `list_bucket`, `bucket_create` o `bucket_browse`.

Prima interazione suggerita:

- crea un bucket pubblico chiamato `demo-assets`
- sfoglia quel bucket
- salva un piccolo oggetto di testo
- caricalo di nuovo

Questo offre un ciclo completo: UI ricca, scoperta in Plaza, esecuzione del pulser e stato locale persistente.

### Flusso 2: visualizza i dati e disegna un grafico dal pulser YFinance

Usa la stessa sessione del workbench, quindi:

1. Aggiorna nuovamente il cataloga Plaza in modo che appaia il pulser YFinance.
2. Aggiungi un nuovo pannello del browser o riconfigura un pannello dati esistente.
3. Scegli il pulse `ohlc_bar_series`.
4. Scegli il pulser `DemoYFinancePulser` se il workbench non lo seleziona automaticamente.
5. Apri `Pane Params JSON` e usa un payload come questo:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. Clicca su `Get Data`.
7. In `Display Fields`, attiva `ohlc_series`. Se è già selezionato un altro campo, disattivalo in modo che l'anteprima punti alla serie temporale stessa.
8. Cambia `Format` in `chart`.
9. Imposta `Chart Style` su `candle` per le candele OHLC o `line` per una semplice visualizzazione dell'andamento.

Cosa dovresti vedere:

- il pannello recupera i dati delle barre per il simbolo e l'intervallo di date richiesti
- l'anteprima passa da dati strutturati a un grafico
- cambiare il simbolo o l'intervallo di date ti fornisce un nuovo grafico senza lasciare il workbench

Variazioni consigliate:

- sostituisci `AAPL` con `MSFT` o `NVDA`
- accorcia l'intervallo di date per una visualizzazione recente più dettagliata
- confronta `line` e `candle` utilizzando la stessa risposta `ohlc_bar_series`

### Flusso 3: carica un diagramma e usa Test Run per calcolare una serie RSI

Apri la rotta dell'editor di diagrammi:

- `http://127.0.0.1:8041/map-phemar/`

Poi procedi lungo questo percorso:

1. Conferma che l'URL di Plaza nell'editor di diagrammi sia `http://127.0.0.1:8241`.
2. Clicca su `Load Phema`.
3. Scegli `OHLC To RSI Diagram`.
4. Ispeziona il grafico predefinito. Dovrebbe mostrare `Input -> OHLC Bars -> RSI 14 -> Output`.
5. Clicca su `Test Run`.
6. Usa questo payload di input:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. Esegui la mappa ed espandi gli output dei passaggi.

Cosa dovresti vedere:

- il passaggio `OHLC Bars` chiama il pulser demo YFinance e restituisce `ohlc_series`
- il passaggio `RSI 14` inoltra queste barre al pulser technical-analysis con `window: 14`
- il payload finale `Output` contiene un array `values` calcolato con voci `timestamp` e `value`

Se desideri ricostruire lo stesso diagramma da zero invece di caricare il seed:

1. Aggiungi un nodo arrotondato chiamato `OHLC Bars`.
2. Collegalo a `DemoYFinancePulser` e al pulse `ohlc_bar_series`.
3. Aggiungi un nodo arrotondato chiamato `RSI 14`.
4. Collegalo a `DemoTechnicalAnalysisPulser` e al pulse `rsi`.
5. Imposta i parametri del nodo RSI su:
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. Connettere `Input -> OHLC Bars -> RSI 14 -> Output`.
7. Lasciare le mappature dei bordi come `{}` in modo che i nomi dei campi corrispondenti fluiscano automaticamente.

## Cosa evidenziare in una chiamata di demo

- Il workbench carica comunque utili dati simulati per la dashboard anche prima che vengano aggiunte connessioni live.
- L'integrazione di Plaza è opzionale e può puntare a un ambiente locale o remoto.
- Il pulser per l'archiviazione dei file è solo locale, il che rende la demo pubblica sicura e riproducibile.
- Il pulser YFinance aggiunge una seconda storia: lo stesso workbench può navigare nei dati di mercato live e renderizzarli come un grafico.
- L'editor di diagrammi aggiunge una terza storia: lo stesso backend può orchestrare flussi multi-step ed esporre ogni passaggio tramite `Test Run`.

## Crea la tua istanza personalizzata

Esistono tre percorsi di personalizzazione comuni:

### Modificare i dati iniziali della dashboard e dell'area di lavoro

Il workbench legge lo snapshot della dashboard da:

- `attas/personal_agent/data.py`

È il modo più rapido per inserire le tue watchlists, metriche o impostazioni predefinite dell'area di lavoro.

### Modificare l'interfaccia visiva

L'attuale runtime live del workbench viene servito da:

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

Se desideri cambiare il tema della demo o semplificare l'interfaccia utente per il tuo pubblico, parti da qui.

### Modificare i Plaza e i pulsers connessi

Se desideri un backend differente:

1. copia `plaza.agent`, `file-storage.pulser`, `yfinance.pulser` e `technical-analysis.pulser`
2. rinomina i servizi
3. aggiorna le porte e i percorsi di archiviazione
4. modifica il diagramma iniziale in `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` o creane uno tuo dal workbench
5. sostituisci i pulsers della demo con i tuoi agent quando sei pronto

## Impostazioni opzionali del Workbench

Lo script di avvio supporta un paio di variabili d'ambiente utili:
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

Utilizzare `PHEMACAST_PERSONAL_AGENT_RELOAD=1` quando si modifica attivamente l'app FastAPI durante lo sviluppo.

## Risoluzione dei problemi

### Il workbench si carica, ma i risultati di Plaza sono vuoti

Controlla queste tre cose:

- `http://127.0.0.1:8241/health` è raggiungibile
- i terminali file-storage, YFinance e technical-analysis pulser sono ancora in esecuzione quando hai bisogno di quei flussi
- le impostazioni `Connection` del workbench puntano a `http://127.0.0.1:8241`

### Il pulser non mostra ancora alcun oggetto

È normale al primo avvio. Il backend di archiviazione della demo parte vuoto.

### Il pannello YFinance non disegna un grafico

Controlla queste cose:

- il terminale YFinance pulser è in esecuzione
- il pulse selezionato è `ohlc_bar_series`
- `Display Fields` include `ohlc_series`
- `Format` è impostato su `chart`
- `Chart Style` è `line` o `candle`

Se la richiesta stessa fallisce, prova un altro simbolo o riesegui dopo una breve attesa perché Yahoo può limitare la frequenza o rifiutare le richieste in modo intermittente.

### Il diagramma `Test Run` fallisce

Controlla queste cose:

- `http://127.0.0.1:8241/health` è raggiungibile
- il YFinance pulser è in esecuzione su `http://127.0.0.1:8243`
- il technical-analysis pulser è in esecuzione su `int http://127.0.0.1:8244`
- il diagramma caricato è `OHLC To RSI Diagram`
- il payload di input include `symbol`, `interval`, `start_date` e `end_date`

Se il passaggio `OHLC Bars` fallisce per primo, il problema è solitamente l'accesso live a Yahoo o il rate limiting. Se il passaggio `RSI 14` fallisce, la causa più comune è che il technical-analysis pulser non è in esecuzione o che la risposta OHLC a monte non includeva `ohlc_series`.

### Vuoi resettare la demo

Il reset più sicuro è puntare i valori `root_path` a un nuovo nome di cartella, o rimuovere la cartella `demos/personal-research-workbench/storage/` quando non ci sono processi demo in esecuzione.

## Interrompere la demo

Premi `Ctrl-C` in ogni finestra del terminale.
