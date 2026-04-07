# ADS Pulser Demo

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

## Was diese Demo abdeckt

- wie `ADSPulser` auf normalisierten ADS-Tabellen aufbaut
- wie die Aktivität von Dispatcher und Worker in für den Pulser sichtbare Daten umgewandelt wird
- wie Ihre eigenen Collector Daten in ADS-Tabellen schreiben und über bestehende Pulses angezeigt werden können

## Setup

Folgen Sie der Kurzanleitung in:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

O verwenden Sie den auf pulser ausgerichteten Single-Command-Wrapper aus der Repository-Wurzel:
```bash
./demos/pulsers/ads/run-demo.sh
```

Dieser Wrapper startet denselben SQLite ADS-Stack wie `data-pipeline`, öffnet aber einen Browser-Leitfaden und Tabs, die sich auf den pulser-first Walkthrough konzentrieren.

Dies startet:

1. den ADS dispatcher
2. den ADS worker
3. den ADS pulser
4. das boss UI

## Schnellstart der Plattform

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Verwenden Sie eine native Windows-Python-Umgebung. Aus der Wurzel des Repositorys in der PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher ads
```

Wenn sich die Browser-Tabs nicht automatisch öffnen, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

## Erste Pulser-Prüfungen

Sobald die Beispiel-Jobs abgeschlossen sind, öffnen Sie:

- `http://127.0.0.1:9062/`

Testen Sie dann:

1. `security_master_lookup` mit `{"symbol":"AAPL","limit":1}`
2. `daily_price_history` mit `{"symbol":"AAPL","limit":5}`
3. `company_profile` mit `{"symbol":"AAPL"}`
4. `news_article` mit `{"symbol":"AAPL","number_of_articles":3}`

## Warum ADS anders ist

Die anderen Pulser-Demos lesen meist direkt von einem Live-Anbieter oder einem lokalen Speicher-Backend.

`ADSPulser` liest stattdessen aus den normalisierten Tabellen, die von der ADS-Pipeline geschrieben werden:

- Workers sammeln oder transformieren Quelldaten
- Der Dispatcher persistiert normalisierte Zeilen
- `ADSPulser` stellt diese Zeilen als abfragbare Pulses bereit

Dies macht es zum idealen Demo, um zu erklären, wie man eigene Quell-Adapter hinzufügt.

## Fügen Sie Ihre eigene Quelle hinzu

Die detaillierte Anleitung befindet sich unter:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Verwenden Sie die benutzerdefinierten Beispiele hier:

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

Diese Beispiele zeigen, wie ein benutzerdefinierter Collector in Folgendes schreiben kann:

- `ads_news`, das über `news_article` verfügbar ist
- `ads_daily_price`, das über `daily_price_history` verfügbar ist
