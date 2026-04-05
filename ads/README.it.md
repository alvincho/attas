# Attas Data Services

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

## Copertura

Le attuali tabelle del dataset normalizzato sono:

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

Il dispatcher gestisce anche:

- `ads_jobs`
- `ads_worker_capabilities`

L'implementazione utilizza i prefissi delle tabelle `ads_` invece dei nomi letterali `ads-*`, in modo che gli stessi identificatori funzionino correttamente su SQLite, Postgres e SQL basato su Supabase.

## Forma di runtime

Dispatcher:

- è un agente `prompits`
- possiede la coda condivisa e le tabelle di archiviazione normalizzate
- espone `ads-submit-job`, `ads-get-job`, `arg-register-worker` e `ads-post-job-result`
- consegna ai worker un payload `JobDetail` tipizzato quando richiedono lavoro
- accetta un payload `JobResult` tipizzato per finalizzare i lavori e persistere le righe raccolte più i payload grezzi

Worker:

- è un agente `prompits`
- pubblicizza le proprie capacità attraverso i metadati dell'agente e la tabella delle capacità del dispatcher
- carica `job_capabilities` dalla configurazione e registra i nomi delle capacità su Plaza metadata
- utilizza oggetti `JobCap` come percorso di esecuzione predefinito per i lavori richiesti
- può essere eseguito una volta o in un loop di polling, con un intervallo predefinito di 10 secondi
- accetta un `process_job()` sovrascritto o un callback di gestione esterno

Pulser:

- è un pulser `phemacast`
- legge le tabelle ADS normalizzate dal pool condiviso
- espone pulse per security master, prezzi giornalieri, fondamentali, bilanci, news e ricerca di payload grezzi

## File

- `ads/agents.py`: agent dispatcher e worker
- `ads/jobcap.py`: astrazione `JobCap` e caricatore di capacità basato su callable
- `ads/models.py`: `JobDetail` e `JobResult`
- `ads/pulser.py`: implementazione del pulser ADS
- `ads/boss.py`: agente UI boss operator
- `ads/practices.py`: pratiche di dispatching
- `ads/schema.py`: schemi delle tabelle condivisi
- `ads/iex.py`: capacità di job a fine giornata IEX
- `ads/twse.py`: capacità di job a fine giornata della Borsa di Taiwan
- `ads/rss_news.py`: capacità di raccolta notizie RSS multi-feed
- `ads/sec.py`: capacità di importazione bulk dati grezzi SEC EDGAR e mappatura per azienda
- `ads/us_listed.py`: capacità master titoli quotati USA di Nasdaq Trader
- `ads/yfinance.py`: capacità di job a fine giornata Yahoo Finance
- `ads/runtime.py`: helper di normalizzazione
- `ads/configs/*.agent`: esempi di configurazioni ADS
- `ads/sql/ads_tables.sql`: DDL Postgres/Supabase

## Esempi locali

Le configurazioni ADS incluse ora presuppongono un database PostgreSQL condiviso. Imposta
`POSTGRES_DSN` o `DATABASE_URL` prima di avviare gli agent. Puoi opzionalmente
impostare `ADS_POSTGRES_SCHEMA` per utilizzare uno schema diverso da `public`, e
`ADS_POSTGRES_SSLMODE` per sovrascrivere il comportamento predefinito `disable` (adatto all'ambiente locale)
quando è necessario SSL per PostgreSQL gestito.

Avvia il dispatcher:
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

Avvia un worker:
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

La configurazione di esempio del worker include una funzionalità live `US Listed Sec to security master` supportata da `ads.us_listed:USListedSecJobCap`, mock handler per `fundamentals`, `financial_statements` e `news`, e utilizza `ads.sec:USFilingBulkJobCap` denominato `US Filing Bulk`, `ads.sec:USFilingMappingJobCap` denominato `US Filing Mapping`, `ads.yfinance:YFinanceEODJobCap` denominato `YFinance EOD`, `ads.yfinance:YFinanceUSMarketEODJobCap` denominato `YFinance US Market EOD`, oltre a `ads.twse:TWSEMarketEODJobCap` denominato `TWSE Market EOD` per la raccolta live a fine giornata, e `ads.rss_news:RSSNewsJobCap` denominato `RSS News` per la raccolta di notizie da più feed. `YFinance EOD` utilizza il modulo `yfinance` installato e non richiede una chiave API separata. `YFinance US Market EOD` scansiona `ads_security_master` alla ricerca di simboli `USD` attivi, li ordina per `metadata.yfinance.eod_at`, aggiorna quel timestamp simbolo per simbolo e mette in coda job `YFinance EOD` di un singolo simbolo in modo che i nomi più obsoleti vengano aggiornati per primi. `TWSE Market EOD` legge il rapporto giornaliero delle quotazioni `MI_INDEX` ufficiale di TWSE e memorizza la tabella completa delle quotazioni di mercato in righe normalizzate `ads_daily_price`. Quando `ads_dummy_price` è vuoto, avvia un breve intervallo recente per impostazione predefinita invece di tentare un ripristino completo di tutto il mercato per più anni; usa un `start_date` esplicito se desideri la copertura storica TWSE. `USListedSecJobCap` legge i file della directory dei simboli Nasdaq Trader `nasdaqlisted.txt` e `otherlisted.txt`, preferisce le copie ospitate sul web `https://www.nasdaqtrader.com/dynamic/SymDir/` con fallback FTP, filtra i simboli di test e aggiorna l'attuale universo quotato negli Stati Uniti in `ads_security_master`. `RSS News` recupera i feed configurati SEC, CFTC e BLS in un unico job e memorizza le voci dei feed normalizzate in `ads_news`. `US Filing Bulk` scarica l'EDGAR della SEC ogni notte
gli archivi `companyfacts.zip` e `submissions.zip`, scrive le righe JSON grezze per azienda in `ads_sec_companyfacts` e `ads_sec_submissions`, e invia un header `User-Agent` SEC dichiarato. `US Filing Mapping` legge una società da quelle tabelle SEC grezze e la mappa in `ads_fundamentals` più `ads_financial_statements` quando un simbolo è disponibile nei metadati di submissions.
Avvia il pulser:
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

Avvia l'interfaccia utente di boss:
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

L'interfaccia utente di boss ora include una barra di connessione live di Plaza nella parte superiore della pagina,
una pagina `Issue Job`, una vista `/monitor` per sfogliare i job ADS in coda, assegnati,
completati e falliti, oltre ai relativi record del payload grezzo, e una
pagina `Settings` per i valori predefiniti del dispatcher lato boss e le preferenze di aggiornamento del monitor.

## Note
<<<LANG:it>>>
- Le configurazioni di esempio fornite utilizzano `PostgresPool`, quindi dispatcher, worker, pulser e boss puntano tutti allo stesso database ADS invece di file SQLite per ogni agente.
- `PostgresPool` risolve le impostazioni di connessione da `POSTGRES_DSN`, `DATABASE_URL`, `SUPABASE_DB_URL` o dalle variabili d'ambiente standard libpq `PG*`.
- `ads/configs/boss.agent`, `ads/configs/dispatcher.agent` e `ads/configs/worker.agent` devono rimanere allineati quando vengono introdotti nuovi JobCaps; le configurazioni fornite espongono `US Listed Sec to security master`, `US Filing Bulk`, `US Filing Mapping`, `YFinance EOD`, `YFinance US Market EOD`, `TWSE Market EOD` e `RSS News`.
- Le configurazioni dei worker possono dichiarare voci `ads.job_capabilities` con un nome di capacità e un percorso chiamabile come `ads.examples.job_caps:mock_daily_price_cap`.
- Le configurazioni dei worker possono anche dichiarare capacità basate su classi con `type`, ad esempio `ads.iex:IEXEODJobCap`, `ads.rss_news:RSSNewsJobCap`, `ads.sec:USFilingBulkJobCap`, `ads.sec:USFilingMappingJobCap`, `ads.twse:TWSEMarketEODJobCap`, `ads.us_listed:USListedSecJobCap` o `ads.yfinance:YFinanceEODJobCap`, che restituiscono righe normalizzate più payload grezzi per la persistenza del dispatcher.
- Le voci `ads.job_capabilities` del worker supportano `disabled: true` per disabilitare temporaneamente un job cap configurato senza eliminare la sua voce di configurazione.
- Le configurazioni dei worker possono impostare `ads.yfinance_request_cooldown_sec` (predefinito `120`) in modo che un worker interrompa temporaneamente l'annuncio di capacità relative a YFinance dopo una risposta di rate-limit di Yahoo.
- `ads/sql/ads_tables.sql` è incluso per implementazioni Postgres o Supabase.
- Dispatcher e worker utilizzano di default un token diretto locale condiviso, quindi le chiamate remote `UsePractice(...)` funzionano su una singola macchina anche prima che l'autenticazione Plaza sia configurata.
- Tutti e tre i componenti rispettano le convenzioni esistenti del repository, quindi possono ancora partecipare alla registrazione in Plaza e alle chiamate remote `UsePractice(...)` quando configurati per farlo.
