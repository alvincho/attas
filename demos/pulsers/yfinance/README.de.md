# YFinance Pulser Demo

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

## Dateien in diesem Ordner

- `plaza.agent`: lokales Plaza für diese Demo
- `yfinance.pulser`: lokale Demo-Konfiguration für `YFinancePulser`
- `start-plaza.sh`: Plaza starten
- `start-pulser.sh`: den pulser starten
- `run-demo.sh`: die vollständige Demo von einem Terminal aus starten und den Browser-Guide sowie die Pulser-UI öffnen

## Einzelbefehl-Start

Aus der Repository-Wurzel:
```bash
./demos/pulsers/yfinance/run-demo.sh
```

Dies startet Plaza und `YFinancePulser` aus einem einzigen Terminal heraus, öffnet eine Browser-Anleitungsseite und öffnet automatisch das Pulser-UI.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Schnellstart der Plattform

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Verwenden Sie WSL2 mit Ubuntu oder einer anderen Linux-Distribution. Aus dem Repository-Root innerhalb von WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

Falls Browser-Tabs nicht automatisch aus WSL heraus geöffnet werden, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

Native PowerShell / Command Prompt-Wrapper sind noch nicht enthalten, daher ist WSL2 heute der unterstützte Windows-Pfad.

## Quickstart

Öffnen Sie zwei Terminals aus der Wurzel des Repositorys.

### Terminal 1: Plaza starten
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet unter `http://127.0.0.1:8251`

### Terminal 2: den pulser starten
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8252`
- er registriert sich bei Plaza unter `http://127.0.0.1:8251`

Hinweis:

- diese Demo erfordert einen ausgehenden Internetzugriff, da der pulser Live-Daten über `yfinance` abruft
- Yahoo Finance kann Anfragen drosseln oder zeitweise ablehnen

## Im Browser ausprobieren

Öffnen:

- `http://127.0.0.1:8252/`

Empfohlene erste Pulses:

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

Empfohlene Parameter für `last_price`:
```json
{
  "symbol": "AAPL"
}
```

Empfohlene Parameter für `ohlc_bar_series`:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Testen Sie es mit Curl

Angebotsanfrage:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

OHLC-Serienanfrage:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## Was hervorzuheben ist

- derselbe pulser bietet sowohl Snapshot-Style- als auch Time-Series-Style-Pulses an
- `ohlc_bar_series` ist kompatibel mit dem workbench chart demo und dem pulser des technical-analysis-Pfads
- der live provider kann später im Hintergrund geändert werden, während der pulse contract gleich bleibt

## Erstellen Sie Ihr eigenes

Wenn Sie diese Demo erweitern möchten:

1. kopieren Sie `yfinance.pulser`
2. passen Sie Ports und Speicherpfade an
3. ändern oder fügen Sie unterstützte Pulse-Definitionen hinzu, wenn Sie einen kleineren oder spezialisierteren Katalog wünschen
