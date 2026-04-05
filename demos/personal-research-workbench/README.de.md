# Persönliche Forschungs-Arbeitsstation

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

- die lokal laufende UI des persönlichen Workbenches
- ein Plaza, den das Workbench durchsuchen kann
- lokale und Live-Daten-Pulser mit echten ausführbaren Pulsen
- ein diagrammorientierter `Test Run`-Ablauf, der Marktdaten in eine berechnete Indikatorenserie umwandelt
- ein Weg von einer polierten Demo hin zu einer selbst gehosteten Instanz

## Dateien in diesem Ordner

- `plaza.agent`: lokaler Plaza, der nur für diese Demo verwendet wird
- `file-storage.pulser`: lokaler pulser, der auf dem Dateisystem basiert
- `yfinance.pulser`: optionaler Marktdaten-pulser, der auf dem Python-Modul `yfinance` basiert
- `technical-analysis.lar`: optionaler Pfad-pulser, der den RSI aus OHLC-Daten berechnet
- `map_phemar.phemar`: demo-lokale MapPhemar-Konfiguration, die vom eingebetteten Diagrammeditor verwendet wird
- `map_phemar_pool/`: vorbereitete Diagrammspeicherung mit einer einsatzbereiten OHLC-to-RSI-Map
- `start-plaza.sh`: startet die Demo Plaza
- `start-file-storage-pulser.sh`: startet den pulser
- `start-yfinance-pulser.sh`: startet den YFinance pulser
- `start-technical-analysis-pulser.sh`: startet den technischen Analyse-pulser
- `start-workbench.sh`: startet das React/FastAPI Workbench

Alle Laufzeitzustände werden unter `demos/personal-research-workbench/storage/` gespeichert. Der Launcher verweist zudem den eingebetteten Diagrammeditor auf die vorbereiteten `map_phemar.phemar` und `map_phemar_pool/` Dateien in diesem Ordner.

## Voraussetzungen

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Einzelbefehl-Start

Aus der Wurzel des Repositorys:
```bash
./demos/personal-research-workbench/run-demo.sh
```

Dies startet den Workbench-Stack aus einem Terminal heraus, öffnet eine Browser-Anleitungsseite und öffnet dann sowohl die Haupt-Workbench-UI als auch die eingebettete `MapPhemar`-Route, die im Kern-Walkthrough verwendet wird.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Schnellstart der Plattform

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

Verwenden Sie WSL2 mit Ubuntu oder einer anderen Linux-Distribution. Aus dem Repository-Root innerhalb von WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

Wenn Browser-Tabs nicht automatisch aus WSL heraus geöffnet werden, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

Native PowerShell / Command Prompt-Wrapper sind noch nicht enthalten, daher ist heute WSL2 der unterstützte Windows-Pfad.

## Quickstart

Öffnen Sie fünf Terminals aus dem Repository-Root, wenn Sie die vollständige Demo wünschen, einschließlich des YFinance-Diagrammflusses und des Diagramm-Testlauf-Flusses.

### Terminal 1: Starten des lokalen Plaza

```bash
./demos/personal-research-workbench/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet unter `http://127.0.0.1:8241`

### Terminal 2: den lokalen Datei-Speicher-Pulser starten
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8242`
- er registriert sich beim Plaza von Terminal 1 aus

### Terminal 3: den YFinance pulser starten
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8243`
- er registriert sich selbst beim Plaza von Terminal 1 aus

Hinweis:

- dieser Schritt erfordert einen ausgehenden Internetzugriff, da der pulser Live-Daten von Yahoo Finance über das `yfinance`-Modul abruft
- Yahoo kann gelegentlich Anfragen drosseln (Rate-Limiting), daher sollte dieser Ablauf eher als Live-Demo und weniger als starres Element betrachtet werden

### Terminal 4: technischen Analyse-pulser starten
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8244`
- er registriert sich selbst beim Plaza von Terminal 1 aus

Dieser pulser berechnet `rsi` aus einer eingehenden `ohlc_series` oder ruft OHLC-Bars vom Demo-YFinance-pulser ab, wenn Sie nur Symbol, Intervall und Datumsbereich angeben.

### Terminal 5: den Workbench starten
```bash
./demos/personal-research-workbench/start-workbench.sh
```

Erwartetes Ergebnis:

- die Workbench startet unter `http://127.0.0.1:8041`

## Anleitung zum ersten Durchlauf

Diese Demo verfügt nun über drei Workbench-Workflows:

1. lokaler Speicher-Workflow mit dem file-storage pulser
2. Live-Marktdaten-Workflow mit dem YFinance pulser
3. Diagramm-Testlauf-Workflow mit den YFinance und technical-analysis pulsers

Öffnen:

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### Workflow 1: lokale Daten durchsuchen und speichern

Arbeiten Sie dann diesen kurzen Pfad ab:

1. Öffnen Sie den Einstellungs-Workflow in der Workbench.
2. Gehen Sie zum Abschnitt `Connection`.
3. Setzen Sie die Standard-Plaza-URL auf `http://127.0.0.1:8241`.
4. Aktualisieren Sie den Plaza-Katalog.
5. Öffnen oder erstellen Sie ein Browserfenster in der Workbench.
6. Wählen Sie den registrierten file-storage pulser aus.
7. Führen Sie einen der integrierten Pulses aus, wie z. B. `list_bucket`, `bucket_create` oder `bucket_browse`.

Empfohlene erste Interaktion:

- Erstellen Sie einen öffentlichen Bucket namens `demo-assets`
- Durchsuchen Sie diesen Bucket
- Speichern Sie ein kleines Textobjekt
- Laden Sie es erneut wieder

Dies bietet einen vollständigen Kreislauf: reichhaltige UI, Plaza-Entdeckung, Pulser-Ausführung und persistenter lokaler Zustand.

### Workflow 2: Daten anzeigen und ein Diagramm vom YFinance pulser zeichnen

Verwenden Sie dieselbe Workbench-Sitzung, dann:

1. Aktualisieren Sie den Plaza-Katalog erneut, damit der YFinance pulser erscheint.
2. Fügen Sie ein neues Browser-Pane hinzu oder konfigurieren Sie ein vorhandenes Daten-Pane neu.
3. Wählen Sie den `ohlc_bar_series` Pulse aus.
4. Wählen Sie den `DemoYFinancePulser` pulser, falls die Workbench diesen nicht automatisch auswählt.
5. Öffnen Sie `Pane Params JSON` und verwenden Sie ein Payload wie dieses:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. Klicken Sie auf `Get Data`.
7. Aktivieren Sie in `Display Fields` `ohlc_series`. Wenn bereits ein anderes Feld ausgewählt ist, schalten Sie es aus, damit die Vorschau direkt auf die Zeitreihe zeigt.
8. Ändern Sie `Format` in `chart`.
9. Stellen Sie `Chart Style` auf `candle` für OHLC-Kerzen oder `line` für eine einfache Trendansicht ein.

Was Sie sehen sollten:

- das Fenster ruft Bar-Daten für das angeforderte Symbol und den Datumsbereich ab
- die Vorschau ändert sich von strukturierten Daten zu einem Diagramm
- das Ändern des Symbols oder des Datumsbereichs liefert ein neues Diagramm, ohne die Workbench zu verlassen

Empfohlene Variationen:

- wechseln Sie `AAPL` zu `MSFT` oder `NVCA`
- verkürzen Sie den Datumsbereich für eine detailliertere aktuelle Ansicht
- vergleichen Sie `line` und `candle` mit derselben `ohlc_bar_series` Antwort

### Flow 3: ein Diagramm laden und Test Run verwenden, um eine RSI-Serie zu berechnen

Öffnen Sie die Route des Diagrammeditors:

- `http://127.0.0.1:8041/map-phemar/`

Arbeiten Sie dann diesen Pfad ab:

1. Bestätigen Sie, dass die Plaza-URL im Diagrammeditor `http://127.0.0.1:8241` lautet.
2. Klicken Sie auf `Load Phema`.
3. Wählen Sie `OHLC To RSI Diagram`.
4. Überprüfen Sie den initialen Graphen. Er sollte `Input -> OHLC Bars -> RSI 14 -> Output` zeigen.
5. Klicken Sie auf `Test Run`.
6. Verwenden Sie diesen Input-Payload:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. Führen Sie die Map aus und erweitern Sie die Schritt-Ausgaben.

Was Sie sehen sollten:

- der Schritt `OHLC Bars` ruft den Demo-YFinance-Pulser auf und gibt `ohlc_series` zurück
- der Schritt `RSI 14` leitet diese Bars an den technical-analysis-Pulser mit `window: 14` weiter
- die endgültige `Output`-Payload enthält ein berechnetes `values`-Array mit `timestamp`- und `value`-Einträgen

Wenn Sie dasselbe Diagramm von Grund auf neu erstellen möchten, anstatt den Seed zu laden:

1. Fügen Sie einen abgerundeten Knoten namens `OHLC Bars` hinzu.
2. Binden Sie ihn an `DemoYFinancePulser` und den `ohlc_bar_series`-Pulse.
3. Fügen Sie einen abgerundeten Knoten namens `RSI 14` hinzu.
4. Binden Sie ihn an `DemoTechnicalAnalysisPulser` und den `rsi`-Pulse.
5. Setzen Sie die RSI-Knotenparameter auf:
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. Verbinden Sie `Input -> OHLC Bars -> RSI 14 -> Output`.
7. Lassen Sie die Randzuordnungen als `{}` stehen, damit übereinstimmende Feldnamen automatisch durchfließen.

## Was in einem Demo-Call hervorgehoben werden sollte

- Die Workbench lädt auch vor dem Hinzufügen von Live-Verbindungen nützliche Mock-Dashboard-Daten.
- Die Plaza-Integration ist optional und kann auf eine lokale oder remote Umgebung verweisen.
- Der File-Storage-Pulser ist nur lokal verfügbar, was die öffentliche Demo sicher und reproduzierbar macht.
- Der YFinance-Pulser fügt eine zweite Geschichte hinzu: Dieselbe Workbench kann Live-Marktdaten durchsuchen und als Diagramm darstellen.
- Der Diagramm-Editor fügt eine dritte Geschichte hinzu: Derselbe Backend kann Multi-Step-Flows orchestrieren und jeden Schritt über `Test Run` offenlegen.

## Erstellen Sie Ihre eigene Instanz

Es gibt drei gängige Anpassungspfade:

### Ändern der Seed-Daten für Dashboard und Workspace

Das Workbench liest seinen Dashboard-Snapshot aus:

- `attas/personal_agent/data.py`

Dies ist der schnellste Weg, um eigene Watchlists, Metriken oder Workspace-Standardwerte einzufügen.

### Ändern des visuellen Shells

Die aktuelle Live-Workbench-Runtime wird bereitgestellt von:

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

Wenn Sie das Design der Demo ändern oder die Benutzeroberfläche für Ihr Publikum vereinfachen möchten, fangen Sie hier an.

### Ändern der verbundenen Plaza und Pulsers

Wenn Sie ein anderes Backend wünschen:

1. Kopieren Sie `plaza.agent`, `file-storage.pulser`, `yfinance.pulser` und `technical-analysis.pulser`
2. Benennen Sie die Dienste um
3. Aktualisieren Sie Ports und Speicherpfade
4. Bearbeiten Sie das Seed-Diagramm in `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` oder erstellen Sie ein eigenes über das Workbench
5. Ersetzen Sie die Demo-Pulsers durch Ihre eigenen Agents, sobald Sie bereit sind

## Optionale Workbench-Einstellungen

Das Launcher-Skript unterstützt einige nützliche Umgebungsvariablen:
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

Verwenden Sie `PHEMACAST_PERSONAL_AGENT_RELOAD=1`, wenn Sie die FastAPI-App während der Entwicklung aktiv bearbeiten.

## Fehlerbehebung

### Die Workbench wird geladen, aber die Plaza-Ergebnisse sind leer

Überprüfen Sie diese drei Dinge:

- `http://127.0.0.1:8241/health` ist erreichbar
- die file-storage, YFinance und technical-analysis pulser Terminals laufen noch, wenn Sie diese Flows benötigen
- die `Connection`-Einstellungen der Workbench zeigen auf `http://127.0.0.1:8241`

### Der pulser zeigt noch keine Objekte an

Das ist beim ersten Start normal. Das Demo-Storage-Backend startet leer.

### Das YFinance-Fenster zeichnet kein Diagramm

Überprüfen Sie diese Dinge:

- das YFinance pulser Terminal läuft
- der ausgewählte pulse ist `ohlc_bar_series`
- `Display Fields` enthält `ohlc_series`
- `Format` ist auf `chart` eingestellt
- `Chart Style` ist `line` oder `candle`

Wenn die Anfrage selbst fehlschlägt, versuchen Sie ein anderes Symbol oder führen Sie sie nach einer kurzen Wartezeit erneut aus, da Yahoo Anfragen zeitweise begrenzen oder ablehnen kann.

### Das Diagramm `Test Run` schlägt fehl

Überprüfen Sie diese Dinge:

- `http://127.0.0.1:8241/health` ist erreichbar
- der YFinance pulser läuft auf `http://127.0.0.1:8243`
- der technical-analysis pulser läuft auf `http://127.0.0.1:8244`
- das geladene Diagramm ist `OHLC To RSI Diagram`
- die Eingabe-Payload enthält `symbol`, `interval`, `start_date` und `end_date`

Wenn der Schritt `OHLC Bars` zuerst fehlschlägt, liegt das Problem meist am Live-Zugriff auf Yahoo oder an der Ratenbegrenzung. Wenn der Schritt `RSI 14` fehlschlägt, ist die häufigste Ursache, dass der technical-analysis pulser nicht läuft oder die vorgeschaltete OHLC-Antwort `ohlc_series` nicht enthielt.

### Sie möchten die Demo zurücksetzen

Der sicherste Weg zum Zurücksetzen besteht darin, die `root_path`-Werte auf einen neuen Ordnernamen zu setzen oder den Ordner `demos/personal-</strong>research-workbench/storage/` zu entfernen, wenn keine Demo-Prozesse laufen.

## Demo beenden

Drücken Sie `Ctrl-C` in jedem Terminalfenster.
