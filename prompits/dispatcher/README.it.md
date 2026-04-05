# Prompits Dispatcher

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

## Componenti inclusi

- `DispatcherAgent`: dispatcher di job basato su coda
- `DispatcherWorkerAgent`: worker che interroga job corrispondenti e riporta i risultati
- `DispatcherBossAgent`: interfaccia utente browser per emettere job e ispezionare lo stato di runtime
- `JobCap`: astrazione di capacità per handler di job pluggable
- pratiche condivise, schemi, helper di runtime e configurazioni di esempio

## Tabelle interne

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

Se un worker restituisce righe per una `target_table` concreta e fornisce uno schema, il dispatcher può creare e persistere anche quella tabella. Se non viene fornito alcuno schema, le righe vengono memorizzate in modo generico in `dispatcher_job_results`.

## Pratiche

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## Esempio di utilizzo

Avvia il dispatcher:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

Avvia un worker:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

Avvia l'interfaccia utente di boss:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

La configurazione di esempio del worker utilizza una capacità di esempio minima da
`prompits.dispatcher.examples.job_caps`.

## Note

- Il pacchetto utilizza di default un token diretto locale condiviso, quindi le chiamate a `UsePractice(...)` funzionano localmente prima che l'autenticazione Plaza sia configurata.
- Le configurazioni di esempio utilizzano `PostgresPool`, ma i test coprono anche SQLite.
- Il worker può annunciare capacità basate su classi o funzioni chiamabili attraverso la sezione di configurazione `dispatcher.job_capabilities`.
