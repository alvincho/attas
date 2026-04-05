# Attas Data Services

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

## Abdeckung

Die aktuellen normalisierten Datensatz-Tabellen sind:

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

Der Dispatcher verwaltet außerdem:

- `ads_jobs`
- `ads_worker_capabilities`

Die Implementierung verwendet `ads_`-Tabellenpräfixe anstelle der wörtlichen `ads-*`-Namen, sodass dieselben Identifikatoren in SQLite, Postgres und Supabase-gestütztem SQL einwandfrei funktionieren.

## Runtime-Struktur

Dispatcher:

- ist ein `prompits`-Agent
- verwaltet die gemeinsame Warteschlange und die normalisierten Speichertabellen
- stellt `ads-submit-lo-job`, `ads-get-job`, `ads-register-worker` und `ads-post-job-result` bereit
- übergibt Workern eine typisierte `JobDetail`-Payload, wenn diese Arbeit beanspruchen
- akzeptiert eine typisierte `JobResult`-Payload, um Jobs abzuschließen und die gesammelten Zeilen sowie die Roh-Payloads zu persistieren

Worker:

- ist ein `prompits`-Agent
- bewirbt seine Fähigkeiten über Agent-Metadaten und die Dispatcher-Fähigkeitstabelle
- lädt `job_capabilities` aus der Konfiguration und registriert diese Funktionsnamen in den Plaza-Metadaten
- verwendet `JobCap`-Objekte als Standardausführungspfad für beanspruchte Jobs
- kann einmalig oder in einer Polling-Schleife ausgeführt werden, standardmäßig mit einem Intervall von 10 Sekunden
- akzeptiert entweder ein überschriebenes `process_job()` oder einen externen Handler-Callback

Pulser:

- ist ein `phemacast`-Pulser
- liest normalisierte ADS-Tabellen aus dem gemeinsamen Pool
- stellt Pulses für Security Master, Tagespreise, Fundamentaldaten, Statements, News und Roh-Payload-Lookup bereit

## Dateien

- `ads/agents.py`: Dispatcher- und Worker-Agents
- `ads/jobcap.py`: `JobCap`-Abstraktion und Callable-basiertes Capability-Loader
- `ads/models.py`: `JobDetail` und `JobResult`
- `ads/pulser.py`: ADS-Pulser-Implementierung
- `ads/boss.py`: Boss-Operator-UI-Agent
- `ads/practices.py`: Dispatcher-Praktiken
- `ads/schema.py`: Gemeinsame Tabellenschemata
- `ads/iex.py`: IEX End-of-Day-Job-Funktion
- `ads/twse.py`: Taiwan Stock Exchange End-of-Day-Job-Funktion
- `ads/rss_news.py`: Multi-Feed-RSS-News-Collection-Funktion
- `capacité d'importation massive de données brutes SEC EDGAR et mappage par entreprise : `ads/sec.py`
- `ads/us_listed.py`: Nasdaq Trader U.S. Listed Security Master-Funktion
- `ads/yfinance.py`: Yahoo Finance End-of-Day-Job-Funktion
- `ads/runtime.py`: Normalisierungs-Helfer
- `ads/configs/*.agent`: Beispiel-ADS-Konfigurationen
- `ads/sql/ads_tables.sql`: Postgres/Supabase DDL

## Lokale Beispiele

Die mitgelieferten ADS-Konfigurationen gehen nun von einer gemeinsamen PostgreSQL-Datenbank aus.
Setzen Sie `POSTGRES_DSN` oder `DATABASE_URL`, bevor Sie die Agenten starten. Sie können optional
`ADS_POSTGRES_SCHEMA` festlegen, um ein anderes Schema als `public` zu verwenden, und
`ADS_POSTGRES_SSLMODE`, um das standardmäßige, lokal-freundliche `disable`-Verhalten zu überschreiben,
wenn Sie SSL für verwaltetes PostgreSQL benötigen.

Starten Sie den Dispatcher:
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

Einen Worker starten:
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

Die Beispiel-Worker-Konfiguration enthält eine Live-Funktion `US Listed Sec to security master`, die durch `ads.us_listed:USListedSecJobCap` unterstützt wird, Mock-Handler für `fundamentals`, `financial_statements` und `news`, und verwendet `ads.sec:USFilingBulkJobCap` mit dem Namen `US Filing Bulk`, `ads.sec:FilingMappingJobCap` mit dem Namen `US Filing Mapping`, `ads.yfinance:YFinanceEODJobCap` mit dem Namen `YFinance EOD`, `ads.yfinance:YFinanceUSMarketEODJobCap` mit dem Namen `YFinance US Market EOD`, sowie `ads.twse:TWSEMarketEODJobCap` mit dem Namen `TWSE Market EOD` für die Live-End-of-Day-Erfassung und `ads.rss_news:RSSNewsJobCap` mit dem Namen `RSS News` für die Multi-Feed-News-Erfassung. `YFinance EOD` verwendet das installierte `yfinance`-Modul und benötigt keinen separaten API-Schlüssel. `YFinance US Market EOD` scannt `ads_security_pass` nach aktiven `USD`-Symbolen, sortiert sie nach `metadata.yfinance.eod_at`, aktualisiert diesen Zeitstempel Symbol für Symbol und stellt ein-Symbol-`YFinance EOD`-Jobs in eine Warteschlange, sodass die veraltetsten Namen zuerst aktualisiert werden. `TWSE Market EOD` liest den offiziellen täglichen `MI_INDEX`-Kursbericht der TWSE und speichert die vollständige marktweite Kurstabelle in normalisierten `ads_daily_price`-Zeilen. Wenn `ads_daily_price` leer ist, wird standardmäßig ein kurzes aktuelles Zeitfenster initialisiert, anstatt einen mehrjährigen vollständigen Markt-Backfill zu versuchen; verwenden Sie ein explizites `start_date`, wenn Sie eine historische TWSE-Abdeckung wünschen. `USListedSecJobCap` liest die Nasdaq Trader Symbolverzeichnisdateien `nasdaqlisted.txt` und `otherlisted.txt`, bevorzugt die webgehosteten Kopien unter `https://www.nasdaqtrader.com/dynamic/SymDir/` mit FTP-Fallback, filtert Testsymbole heraus und führt ein Upsert des aktuellen in den USA gelisteten Universums in `ads_security_master` durch. `RSS News` ruft die konfigurierten SEC-, CFTC- und BLS-Feeds in einem Job ab und speichert normalisierte Feed-Einträge in `ads_news`. `US Filing Bulk` lädt die nächtlichen SEC EDGAR
die Archive `companyfacts.zip` und `submissions.zip`, schreibt rohe JSON-Zeilen pro Unternehmen in `ads_sec_companyfacts` und `ads_sec_submissions` und sendet einen deklarierten SEC `User-Agent`-Header. `US Filing Mapping` liest ein Unternehmen aus diesen rohen SEC-Tabellen und mappt es in `ads_fundamentals` plus `ads_financial_statements`, wenn ein Symbol in den submissions-Metadaten verfügbar ist.
Starte den pulser:
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

Starten Sie das boss UI:
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

Die Boss-UI enthält nun oben auf der Seite einen Live-Plaza-Verbindungsstreifen,
eine `Issue Job`-Seite, eine `/monitor`-Ansicht zum Durchsuchen von wartenden, beanspruchten,
abgeschlossenen und fehlgeschlagenen ADS-Jobs sowie deren Rohdaten-Payload-Datensätzen und eine
`Settings`-Seite für die Standardwerte des Boss-seitigen Dispatchers und die Einstellungen für die Monitor-Aktualisierung.

## Hinweise
<<<LANG:de>>>
- Die mitgelieferten Beispielkonfigurationen verwenden `PostgresPool`, sodass Dispatcher, Worker, Pulser und Boss alle auf dieselbe ADS-Datenbank verweisen, anstatt auf agentenspezifische SQLite-Dateien.
- `PostgresPool` löst Verbindungseinstellungen aus `POSTGRES_DSN`, `DATABASE_URL`, `SUPABASE_DB_URL` oder Standard-libpq `PG*` Umgebungsvariablen auf.
- `ads/configs/boss.agent`, `ads/configs/dispatcher.agent` und `ads/configs/worker.agent` sollten bei der Einführung neuer JobCaps synchron bleiben; die mitgelieferten Konfigurationen bieten `US Listed Sec to security master`, `US Filing Bulk`, `US Filing Mapping`, `YFinance EOD`, `YFinance US Market EOD`, `TWSE Market EOD` und `RSS News` an.
- Worker-Konfigurationen können `ads.job_capabilities`-Einträge mit einem Funktionsnamen und einem aufrufbaren Pfad wie `ads.examples.job_caps:mock_daily_price_cap` deklarieren.
- Worker-Konfigurationen können auch klassenbasierte Fähigkeiten mit `type` deklarieren, zum Beispiel `ads.iex:IEXEODJobCap`, `ads.rss_news:RSSNewsJobCap`, `ads.sec:USFilingBulkJobCap`, `ads.sec:USFilingMappingJobCap`, `ads.twse:TWSEMarketEODJobCap`, `ads.us_listed:USListedSecJobCap` oder `ads.yfinance:YFinanceEODJobCap`, die normalisierte Zeilen plus Rohdaten für die Dispatcher-Persistenz zurückgeben.
- Worker `ads.job_capabilities`-Einträge unterstützen `disabled: true`, um eine konfigurierte Job-Cap vorübergehend zu deaktivieren, ohne deren Konfigurationseintrag zu löschen.
- Worker-Konfigurationen können `ads.yfinance_request_cooldown_sec` (Standard `120`) festlegen, sodass ein Worker nach einer Yahoo-Rate-Limit-Antwort vorübergehend aufhört, YFinance-bezogene Fähigkeiten anzubieten.
- `ads/sql/ads_tables.sql` ist für Postgres- oder Supabase-Bereitstellungen enthalten.
- Dispatcher und Worker verwenden standardmäßig ein gemeinsam genutztes lokales direktes Token, sodass Remote-Aufrufe von `UsePractice(...)` auf einer Maschine funktionieren, noch bevor die Plaza-Authentifizierung konfiguriert ist.
- Alle drei Komponenten entsprechen den bestehenden Repo-Konventionen, sodass sie weiterhin an der Plaza-Registrierung und an Remote-`UsePractice(...)`-Aufrufen teilnehmen können, wenn sie entsprechend konfiguriert sind.
