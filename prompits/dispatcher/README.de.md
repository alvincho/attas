# Prompits Dispatcher

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

## Enthaltene Komponenten

- `DispatcherAgent`: Queue-basierter Job-Dispatcher
- `DispatcherWorkerAgent`: Worker, der nach passenden Jobs sucht und Ergebnisse meldet
- `DispatcherBossAgent`: Browser-UI zum Erstellen von Jobs und zur Überprüfung des Laufzeitstatus
- `JobCap`: Fähigkeitsabstraktion für steckbare Job-Handler
- gemeinsame Praktiken, Schemata, Runtime-Helfer und Beispielkonfigurationen

## Interne Tabellen

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

Wenn ein Worker Zeilen für eine konkrete `target_table` zurückgibt und ein Schema bereitstellt, kann der Dispatcher diese Tabelle ebenfalls erstellen und persistieren. Wenn kein Schema bereitgestellt wird, werden die Zeilen generisch in `dispatcher_job_results` gespeichert.

## Praktiken

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## Anwendungsbeispiel

Starten Sie den Dispatcher:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

Einen Worker starten:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

Starten Sie das boss UI:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

Die Beispiel-Worker-Konfiguration verwendet eine minimale Beispiel-Funktion von
`prompits.dispatcher.examples.job_caps`.

## Hinweise

- Das Paket verwendet standardmäßig einen gemeinsamen lokalen direkten Token, sodass `UsePractice(...)`-Aufrufe lokal funktionieren, bevor die Plaza-Authentifizierung konfiguriert ist.
- Die Beispielkonfigurationen verwenden `PostgresPool`, aber die Tests decken auch SQLite ab.
- Der Worker kann über den Konfigurationsabschnitt `dispatcher.job_capabilities` aufrufbare oder klassenbasierte Fähigkeiten ankündigen.
