# Pipeline dei dati

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

- una coda di dispatch per i lavori di raccolta dati
- un worker che effettua il polling per capacità corrispondenti
- tabelle ADS normalizzate memorizzate localmente in SQLite
- un'interfaccia boss per emettere e monitorare i lavori
- un pulser che riespone i dati raccolti
- un percorso per sostituire i live collectors inclusi con i propri adattatori di sorgente

## Perché questo demo utilizza SQLite con collector in tempo reale

Le configurazioni ADS in stile produzione in `ads/configs/` sono destinate a un deployment PostgreSQL condiviso.

Questo demo mantiene i collector in tempo reale ma semplifica la parte di storage:

- SQLite mantiene la configurazione locale e semplice
- il worker e il dispatcher condividono un unico file di database ADS locale, il che mantiene la fase bulk SEC in tempo reale compatibile con lo stesso store del demo che il pulser legge
- la stessa architettura è ancora visibile, in modo che gli sviluppatori possano passare alle configurazioni di produzione in seguito
- alcuni job chiamano fonti internet pubbliche, quindi i tempi della prima esecuzione dipendono dalle condizioni della rete e dalla reattività della fonte

## File in questa cartella

- `dispatcher.agent`: Configurazione del dispatcher ADS con supporto SQLite
- `worker.agent`: Configurazione del worker ADS con supporto SQLite
- `pulser.agent`: ADS pulser che legge il data store della demo
- `boss.agent`: Configurazione dell'interfaccia utente boss per l'emissione di job
- `start-dispatcher.sh`: avvia il dispatcher
- `start-worker.sh`: avvia il worker
- `start-pulser.sh`: avvia il pulser
- `start-boss.sh`: avvia l'interfaccia utente boss

Gli adattatori sorgente di esempio correlati e gli helper per la live-demo si trovano in:

- `ads/examples/custom_sources.py`: limiti dei job di esempio importabili per feed di notizie e prezzi definiti dall'utente
- `ads/examples/live_data_pipeline.py`: wrapper orientati alla demo attorno alla pipeline ADS SEC live

Tutti gli stati di runtime vengono scritti in `demos/data-pipeline/storage/`.

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
./demos/data-pipeline/run-demo.sh
```

Questo avvia il dispatcher, il worker, il pulser e l'interfaccia utente di boss da un unico terminale, apre una pagina di guida nel browser e apre automaticamente le interfacce utente di boss plus pulser.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher data-pipeline
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio rapido

Apri quattro terminali dalla radice del repository.

### Terminale 1: avvia il dispatcher
```bash
./demos/data-pipeline/start-dispatcher.sh
```

Risultato atteso:

- il dispatcher si avvia su `http://127.0.0.1:9060`

### Terminal 2: avvia il worker
```bash
./demos/data-pipeline/start-worker.sh
```

Risultato atteso:

- il worker si avvia su `127.0.0.1:9061`
- interroga il dispatcher ogni due secondi

### Terminale 3: avvia il pulser
```bash
./demos/data-pipeline/start-pulser.sh
```

Risultato previsto:

- ADS pulser si avvia su `http://127.0.0.1:9062`

### Terminal 4: avvia l'interfaccia boss
```bash
./demos/data-pipeline/start-boss.sh
```

Risultato atteso:

- l'interfaccia UI di boss si avvia su `http://120.0.0.1:9063`

## Guida alla prima esecuzione

Apri:

- `http://127.0.0.1:9063/`

Nell'interfaccia boss UI, invia questi job in ordine:

1. `security_master`
   Questo aggiorna l'intero universo quotato negli Stati Uniti da Nasdaq Trader, quindi non richiede un payload di simbolo.
2. `daily_price`
   Usa il payload predefinito per `AAPL`.
3. `fundamentals`
   Usa il payload predefinito per `AAPL`.
4. `financial_statements`
   Usa il payload predefinito per `AAPL`.
5. `news`
   Usa l'elenco predefinito dei feed RSS di SEC, CFTC e BLS.

Usa i template di payload predefiniti quando compaiono. `security_master`, `daily_price` e `un news` solitamente terminano rapidamente. La prima esecuzione di `fundamentals` o `financial_statements` basata su SEC potrebbe richiedere più tempo perché aggiorna gli archivi SEC in cache sotto `demos/data-pipeline/storage/sec_edgar/` prima di mappare l'azienda richiesta.

Poi apri:

- `http://127.0.0.1:9062/`

Questo è l'ADS pulser per lo stesso archivio dati demo. Espone le tabelle ADS normalizzate come pulse, che rappresentano il ponte dalla raccolta/orchestrazione al consumo downstream.

Verifiche suggerite per il primo pulser:

1. Esegui `security_master_lookup` con `{"symbol":"AAPL","limit":1}`
2. Esegui `daily_price_history` con `{"symbol":"AAPL","limit":5}`
3. Esegui `company_profile` con `{"symbol":"AAPL"}`
4. Esegui `financial_statements` con `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`
5. Esegui `news_article` con `{"number_of_articles":3}`

Questo mostra il ciclo completo di ADS: l'interfaccia boss UI emette i job, il worker raccoglie le righe, SQLite memorizza i dati normalizzati e `ADSPulser` espone il risultato attraverso pulse interrogabili.

## Aggiungi la tua sorgente dati a ADSPulser

Il modello mentale importante è:

- la tua sorgente si collega al worker come una `job_capability`
- il worker scrive righe normalizzate nelle tabelle ADS
- `ADSPulser` legge quelle tabelle e le espone attraverso i pulse

Se la tua sorgente si adatta a una delle forme di tabella ADS esistenti, di solito non è necessario modificare affatto `ADSPulser`.

### La strada più semplice: scrivere in una tabella ADS esistente

Usa una di queste combinazioni tabella-pulse:

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### Esempio: aggiungere un feed di comunicati stampa personalizzato

Il repository include ora un esempio chiamabile qui:

- `ads/examples/custom_sources.py`

Per collegarlo al worker demo, aggiungi un nome di capability e un job cap basato su un callable in `demos/data-pipeline/worker.agent`.

Aggiungi questo nome di capability:
```json
"press_release_feed"
```

Aggiungi questa voce job-capability:
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

Quindi riavvia il worker e invia un lavoro dall'interfaccia di boss con un payload come:
```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

Dopo il completamento di quel lavoro, apri l'interfaccia utente di Pulser su `http://127.0.0.1:9062/` ed esegui:
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

contro il pulse `news_article`.

Cosa dovresti vedere:

- il collector definito dall'utente scrive una riga normalizzata in `ads_news`
- l'input grezzo è ancora preservato nel payload raw del job
- `ADSPulser` restituisce il nuovo articolo attraverso l'esistente pulse `news_article`

### Secondo esempio: aggiungere un feed di prezzi personalizzato

Se la tua sorgente è più vicina ai prezzi che alle notizie, lo stesso schema funziona con:
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

L'esempio scrive righe in `ads_daily_price`, il che significa che il risultato diventa immediatamente interrogabile tramite `daily_price_history`.

### Quando dovresti modificare ADSPulser stesso

Modifica `ads/pulser.py` solo quando la tua sorgente non si mappa chiaramente su una delle tabelle ADS normalizzate esistenti o quando hai bisogno di una forma d'impulso (pulse shape) completamente nuova.

In tal caso, il percorso abituale è:

1. aggiungere o scegliere una tabella di archiviazione per le nuove righe normalizzate
2. aggiungere una nuova voce di impulso supportata nella configurazione del pulser
3. estendere `ADSDulser.fetch_pulse_payload()` in modo che l'impulso sappia come leggere e dare forma alle righe archiviate

Se stai ancora progettando lo schema, inizia memorizzando il payload grezzo e ispezionalo prima tramite `raw_collection_payload`. Ciò mantiene l'integrazione della sorgente in movimento mentre decidi come dovrebbe essere la tabella normalizzata finale.

## Cosa evidenziare durante una chiamata demo

- I lavori vengono messi in coda ed eseguiti in modo asincrono.
- Il worker è disaccoppiato dall'interfaccia utente di Boss.
- Le righe memorizzate finiscono in tabelle ADS normalizzate invece di un unico archivio blob generico.
- Il pulser è un secondo livello di interfaccia sopra i dati raccolti.
- L'integrazione di una nuova sorgente significa solitamente aggiungere un limite di job worker, non ricostruire l'intero stack ADS.

## Crea la tua istanza personalizzata

Ci sono due percorsi di aggiornamento naturali da questa demo.

### Mantieni l'architettura locale ma sostituisci con i tuoi collector

Modifica `worker.agent` e sostituisci i job cap della demo live inclusi con i tuoi job cap o altri tipi di ADS job-cap.

Per esempio:

- `ads.examples.custom_sources:demo_press_release_cap` mostra come inserire un feed di articoli personalizzato in `ads_news`
- `ads.essentials.custom_sources:demo_alt_price_cap` mostra come inserire una fonte di prezzi personalizzata in `ads_daily_price`
- le configurazioni di produzione in `ads/configs/worker.agent` mostrano come le funzionalità live siano collegate per SEC, YFinance, TWSE e RSS

### Passa da SQLite a PostgreSQL condiviso

Una volta che la demo locale ha dimostrato il workflow, confronta queste configurazioni della demo con le configurazioni in stile produzione in:

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

La differenza principale è la definizione del pool:

- questa demo utilizza `SQLitePool`
- le configurazioni in stile produzione utilizzano `PostgresPool`

## Risoluzione dei problemi

### I lavori rimangono in coda

Controlla queste tre cose:

- il terminale del dispatcher è ancora in esecuzione
- il terminale del worker è ancora in esecuzione
- il nome della capacità del lavoro nell'interfaccia di Boss corrisponde a uno pubblicizzato dal worker

### L'interfaccia di Boss si carica ma appare vuota

Assicurati che la configurazione di boss punti ancora a:

- `dispatcher_address = http://127.0.0.1:9060`

### Desideri un'esecuzione pulita o hai bisogno di rimuovere le vecchie righe di simulazione

Interrompi i processi di demo e rimuovi `demos/data-pipeline/storage/` prima di riavviare.

## Interrompere la Demo

Premi `Ctrl-C` in ogni finestra del terminale.
