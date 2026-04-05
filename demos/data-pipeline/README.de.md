# Data Pipeline

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

## Was diese Demo zeigt

- eine Dispatcher-Queue für Datenerfassungs-Jobs
- ein Worker, der nach passenden Fähigkeiten pollt
- normalisierte ADS-Tabellen, die lokal in SQLite gespeichert sind
- ein Boss-UI zum Erstellen und Überwachen von Jobs
- ein Pulser, der die gesammelten Daten erneut bereitstellt
- ein Pfad zum Ersetzen der mitgelieferten Live-Collectoren durch Ihre eigenen Quell-Adapter

## Warum diese Demo SQLite mit Live-Collectoren verwendet

Die ADS-Konfigurationen im Produktionsstil in `ads/configs/` sind auf ein gemeinsames PostgreSQL-Deployment ausgelegt.

Diese Demo behält die Live-Collectoren bei, vereinfacht jedoch die Speicherseite:

- SQLite hält das Setup lokal und einfach
- der Worker und der Dispatcher teilen eine lokale ADS-Datenbankdatei, wodurch die Live-SEC-Bulk-Phase mit demselben Demo-Store kompatibel bleibt, den der Pulser liest
- dieselbe Architektur bleibt sichtbar, sodass Entwickler später auf die Produktionskonfigurationen umsteigen können
- einige Jobs rufen öffentliche Internetquellen auf, daher hängen die Zeiten beim ersten Durchlauf von den Netzwerkbedingungen und der Reaktionsfähigkeit der Quelle ab

## Dateien in diesem Ordner

- `dispatcher.agent`: SQLite-gestützte ADS-Dispatcher-Konfiguration
- `worker.agent`: SQLite-gestützte ADS-Worker-Konfiguration
- `pulsar.agent`: ADS-Pulser, der den Demo-Datenspeicher liest
- `boss.agent`: Boss-UI-Konfiguration zum Erstellen von Jobs
- `start-dispatcher.sh`: Dispatcher starten
- `start-worker.sh`: Worker starten
- `start-pulser.sh`: Pulser starten
- `start-boss.sh`: Boss-UI starten

Verwandte Beispiel-Quellenadapter und Live-Demo-Helfer befinden sich unter:

- `ads/examples/custom_sources.py`: importierbare Beispiel-Job-Limits für benutzerdefinierte News- und Preis-Feeds
- `ads/examples/live_data_pipeline.py`: Demo-orientierte Wrapper um die Live-SEC-ADS-Pipeline

Alle Laufzeitzustände werden unter `demos/data-pipeline/storage/` gespeichert.

## Voraussetzungen

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Start mit einem einzigen Befehl

Aus der Wurzel des Repositorys:
```bash
./demos/data-pipeline/run-demo.sh
```

Dies startet den Dispatcher, Worker, Pulser und die Boss-UI aus einem einzigen Terminal, öffnet eine Browser-Anleitungsseite und öffnet automatisch die Boss-plus-Pulser-UIs.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Plattform-Schnellstart

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

Verwenden Sie WSL2 mit Ubuntu oder einer anderen Linux-Distribution. Aus dem Repository-Root innerhalb von WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

Wenn Browser-Tabs nicht automatisch aus WSL heraus geöffnet werden, lassen Sie den Launcher weiter laufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

Native PowerShell / Command Prompt-Wrapper sind noch nicht enthalten, daher ist WSL2 heute der unterstützte Windows-Pfad.

## Quickstart

Öffnen Sie vier Terminals aus der Wurzel des Repositorys.

### Terminal 1: dispatcher starten
```bash
./demos/data-pipeline/start-dispatcher.sh
```

Erwartetes Ergebnis:

- dispatcher startet auf `http://127.0.0.1:9060`

### Terminal 2: den Worker starten
```bash
./demos/data-pipeline/start-worker.sh
```

Erwartetes Ergebnis:

- worker startet auf `127.0.0.1:9061`
- er fragt den dispatcher alle zwei Sekunden ab

### Terminal 3: pulser starten
```bash
./demos/data-pipeline/start-pulser.sh
```

Erwartetes Ergebnis:

- ADS pulser startet auf `http://120.0.0.1:9062`

### Terminal 4: Boss-UI starten
```bash
./demos/data-pipeline/start-boss.sh
```

Erwartetes Ergebnis:

- die boss UI startet unter `http://127.0.0.1:9063`

## Anleitung für den ersten Durchlauf

Öffnen Sie:

- `http://127.0.0.1:9063/`

Senden Sie in der Boss-UI diese Jobs in der folgenden Reihenfolge ab:

1. `security_master`
   Dies aktualisiert das gesamte in den USA börsennotierte Universum von Nasdaq Trader, daher ist kein Symbol-Payload erforderlich.
2. `daily_price`
   Verwenden Sie den Standard-Payload für `AAPL`.
3. `fundamentals`
   Verwenden Sie den Standard-Payload für `AAPL`.
4. `financial_statements`
   Verwenden Sie den Standard-Payload für `AAPL`.
5. `news`
   Verwenden Sie die Standard-RSS-Feed-Liste für SEC, CFTC und BLS.

Verwenden Sie die Standard-Payload-Templates, wenn diese erscheinen. `security_master`, `daily_price` und `news` sind normalerweise schnell abgeschlossen. Der erste SEC-gestützte Durchlauf von `fundamentals` oder `financial_statements` kann länger dauern, da die gecachten SEC-Archive unter `demos/data-pipeline/storage/sec_edgar/` aktualisiert werden, bevor das angeforderte Unternehmen zugeordnet wird.

Öffnen Sie dann:

- `http://127.0.0.1:9062/`

Dies ist der ADS pulser für denselben Demo-Datenspeicher. Er stellt die normalisierten ADS-Tabellen als Pulses bereit, was die Brücke von der Erfassung/Orchestrierung zum Downstream-Verbrauch bildet.

Empfohlene erste Pulser-Prüfungen:

1. Führen Sie `security_master_lookup` mit `{"symbol":"AAPL","limit":1}` aus
2. Führen Sie `daily_price_history` mit `{"symbol":"AAPL","limit":5}` aus
3. Führen Sie `company_profile` mit `{"symbol":"AAPL"}` aus
4. Führen Sie `financial_statements` mit `{"symbol":"AAPL","statement_type":"income_statement","limit":3}` aus
5. Führen Sie `news_article` mit `{"number_of_articles":3}` aus

Dies zeigt den gesamten ADS-Zyklus: Die Boss-UI gibt Jobs aus, der Worker sammelt Zeilen, SQLite speichert normalisierte Daten und `ADSPulser` stellt das Ergebnis über abfragbare Pulses bereit.

## Fügen Sie Ihre eigene Datenquelle zu ADSPulser hinzu

Das wichtige mentale Modell ist:

- Ihre Quelle wird als `job_capability` in den Worker eingespeist
- Der Worker schreibt normalisierte Zeilen in ADS-Tabellen
- `ADSPulser` liest diese Tabellen und stellt sie über Pulses bereit

Wenn Ihre Quelle einer der vorhandenen ADS-Tabellenstrukturen entspricht, müssen Sie `ADSPulser` in der Regel überhaupt nicht ändern.

### Der einfachste Weg: In eine bestehende ADS-Tabelle schreiben

Verwenden Sie eine dieser Tabellen-zu-Pulse-Kombinationen:

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### Beispiel: Einen benutzerdefinierten Pressemitteilungs-Feed hinzufügen

Das Repository enthält nun ein aufrufbares Beispiel hier:

- `ads/examples/custom_sources.py`

Um ihn in den Demo-Worker einzubinden, fügen Sie einen Capability-Namen und eine auf einem Callable basierende Job-Cap in `demos/data-pipeline/worker.agent` hinzu.

Fügen Sie diesen Capability-Namen hinzu:
```json
"press_release_feed"
```

Fügen Sie diesen job-capability-Eintrag hinzu:
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

Starten Sie dann den Worker neu und senden Sie einen Job über die Boss-UI mit einem Payload wie:
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

Nachdem dieser Job abgeschlossen ist, öffnen Sie die Pulser-UI unter `http://127.0.0.1:9062/` und führen Sie Folgendes aus:
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

gegen den `news_article` Pulse.

Was Sie sehen sollten:

- der benutzerdefinierte Collector schreibt eine normalisierte Zeile in `ads_news`
- der Rohinput bleibt im raw Payload des Jobs erhalten
- `ADSPulser` gibt den neuen Artikel über den bestehenden `news_article` Pulse zurück

### Zweites Beispiel: Hinzufügen eines benutzerdefinierten Preis-Feeds hinzu

Wenn Ihre Quelle näher an Preisen als an Nachrichten liegt, funktioniert dasselbe Muster mit:
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

Dieses Beispiel schreibt Zeilen in `ads_daily_price`, was bedeutet, dass das Ergebnis sofort über `daily_price_history` abfragbar ist.

### Wann Sie ADSPulser selbst ändern sollten

Ändern Sie `ads/pulser.py` nur dann, wenn Ihre Quelle nicht sauber auf eine der vorhandenen normalisierten ADS-Tabellen abgebildet werden kann oder wenn Sie eine völlig neue Pulsform (pulse shape) benötigen.

In diesem Fall ist der übliche Weg:

1. Eine Speichertabelle für die neuen normalisierten Zeilen hinzufügen oder auswählen
2. Einen neuen unterstützten Pulse-Eintrag in der Pulser-Konfiguration hinzufügen
3. `ADSPulser.fetch_pulse_payload()` erweitern, damit der Puls weiß, wie er die gespeicherten Zeilen lesen und formen kann

Wenn Sie das Schema noch entwerfen, speichern Sie zunächst die Rohdaten (raw payload) und untersuchen Sie diese zuerst über `raw_collection_array`. So bleibt die Quellenintegration in Bewegung, während Sie entscheiden, wie die endgültige normalisierte Tabelle aussehen soll.

## Was in einem Demo-Call hervorgehoben werden sollte

- Jobs werden asynchron in Warteschlangen eingereiht und abgeschlossen.
- Der Worker ist von der Boss-UI entkoppelt.
- Die gespeicherten Zeilen landen in normalisierten ADS-Tabellen anstatt in einem einzigen generischen Blob-Speicher.
- Der Pulser ist eine zweite Schnittstellenebene über den gesammelten Daten.
- Das Hinzufügen einer neuen Quelle bedeutet in der Regel nur das Hinzufügen eines weiteren Worker-Job-Limits, nicht den Neuaufbau des gesamten ADS-Stacks.

## Erstellen Sie Ihre eigene Instanz

Es gibt zwei natürliche Upgrade-Pfade von dieser Demo.

### Behalten Sie die lokale Architektur bei, aber ersetzen Sie die Collector durch Ihre eigenen

Bearbeiten Sie `worker.agent` und ersetzen Sie die enthaltenen Live-Demo-Job-Caps durch Ihre eigenen Job-Caps oder andere ADS-Job-Cap-Typen.

Zum Beispiel:

- `ads.examples.custom_sources:demo_press_release_cap` zeigt, wie ein benutzerdefinierter Artikel-Feed in `ads_news` geladen wird
- `ads.essentials.custom_sources:demo_alt_price_cap` zeigt, wie eine benutzerdefinierte Preisquelle in `</strong>ads_daily_price` geladen wird
- die Produktionskonfigurationen in `ads/configs/worker.agent` zeigen, wie Live-Funktionen für SEC, YFinance, TWSE und RSS angebunden sind

### Wechseln Sie von SQLite zu gemeinsam genutztem PostgreSQL

Sobald die lokale Demo den Workflow unter Beweis gestellt hat, vergleichen Sie diese Demo-Konfigurationen mit den Produktions-Konfigurationen in:

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

Der Hauptunterschied liegt in der Pool-Definition:

- diese Demo verwendet `SQLitePool`
- die Produktions-Konfigurationen verwenden `PostgresPool`

## Fehlerbehebung

### Jobs bleiben in der Warteschlange

Überprüfen Sie diese drei Dinge:

- das Dispatcher-Terminal läuft noch
- das Worker-Terminal läuft noch
- der Job-Fähigkeitsname in der Boss-UI stimmt mit einem vom Worker beworbenen überein

### Die Boss-UI wird geladen, sieht aber leer aus

Stelle sicher, dass die boss-Konfiguration weiterhin auf Folgendes verweist:

- `dispatcher_address = http://127.0.0.1:9060`

### Sie möchten einen sauberen Durchlauf oder müssen alte Mock-Zeilen entfernen

Stoppen Sie die Demo-Prozesse und entfernen Sie `demos/data-pipeline/storage/`, bevor Sie erneut starten.

## Demo stoppen

Drücken Sie `Ctrl-C` in jedem Terminalfenster.
