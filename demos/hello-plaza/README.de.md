# Hello Plaza

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

- ein lokal laufendes Plaza-Registry
- ein Agent, der sich automatisch bei Plaza registriert
- eine browserbasierte Benutzeroberfläche, die mit diesem Plaza verbunden ist
- ein minimaler Konfigurationssatz, den Entwickler in ihr eigenes Projekt kopieren können

## Dateien in diesem Ordner

- `plaza.agent`: Demo-Plaza-Konfiguration
- `worker.agent`: Demo-Worker-Konfiguration
- `user.agent`: Demo-User-Agent-Konfiguration
- `start-plaza.sh`: Plaza starten
- `start-worker.sh`: den Worker starten
- `start-user.sh`: den browserseitigen User Agent starten

Alle Laufzeitzustände werden unter `demos/hello-plaza/storage/` gespeichert.

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
./demos/hello-plaza/run-demo.sh
```

Dies startet Plaza, den Worker und das Benutzer-UI aus einem einzigen Terminal, öffnet eine Browser-Anleitungsseite und öffnet das Benutzer-UI automatisch.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Plattform-Schnellstart

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Verwenden Sie eine native Windows-Python-Umgebung. Aus der Wurzel des Repositorys in der PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

Wenn sich die Browser-Tabs nicht automatisch öffnen, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

## Quickstart

Öffnen Sie drei Terminals aus der Wurzel des Repositorys.

### Terminal 1: Plaza starten
```bash
./demos/hello-plaza/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet auf `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` gibt einen gesunden Status zurück

### Terminal 2: Worker starten
```bash
./demos/hello-plaza/start-worker.sh
```

Erwartetes Ergebnis:

- der Worker startet auf `127.0.0.1:8212`
- it registriert sich automatisch bei Plaza aus Terminal 1

### Terminal 3: Start der Benutzer-UI

```bash
./demos/hello-plaza/start-user.sh
```

Erwartetes Ergebnis:

- der browserseitige User Agent startet unter `http://127.0.0.1:8214/`

## Den Stack überprüfen

In einem vierten Terminal oder nachdem die Dienste hochgefahren sind:
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

Was Sie sehen sollten:

- der erste Befehl gibt eine gesunde Plaza-Antwort zurück
- der zweite Befehl zeigt das lokale Plaza und den registrierten `demo-worker`

Öffnen Sie dann:

- `http://127.0.0.1:8214/`

Dies ist die öffentliche Demo-URL zum Teilen in einer lokalen Einführung oder Bildschirmaufnahme.

## Was in einem Demo-Call hervorgehoben werden sollte

- Plaza ist die Discovery-Schicht.
- Der Worker kann unabhängig gestartet werden und erscheint dennoch im gemeinsamen Verzeichnis.
- Die Benutzeroberfläche benötigt kein fest codiertes Wissen über den Worker. Sie entdeckt ihn über Plaza.

## Erstellen Sie Ihre eigene Instanz

Der einfachste Weg, dies in Ihre eigene Instanz zu verwandeln, ist:

1. Kopieren Sie `plaza.agent`, `worker.agent` und `user.agent` in einen neuen Ordner.
2. Benennen Sie die Agents um.
3. Ändern Sie die Ports, falls erforderlich.
4. Verweisen Sie jeden `root_path` auf Ihren eigenen Speicherort.
5. Wenn Sie die URL oder den Port von Plaza ändern, aktualisieren Sie `plaza_url` in `worker.agent` und `user.agent`.

Die drei wichtigsten Felder zum Anpassen sind:

- `name`: was der Agent als seine Identität angibt
- `port`: wo der HTTP-Dienst lauscht
- `root_path`: wo der lokale Zustand gespeichert wird

Sobald die Dateien korrekt aussehen, führen Sie aus:
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## Fehlerbehebung

### Port bereits belegt

Bearbeiten Sie die entsprechende `.agent`-Datei und wählen Sie einen freien Port. Wenn Sie Plaza auf einen neuen Port verschieben, aktualisieren Sie die `plaza_url` in beiden abhängigen Konfigurationen.

### Die Benutzeroberfläche zeigt ein leeres Plaza-Verzeichnis an

Überprüfen Sie diese drei Dinge:

- Plaza läuft auf `http://127.0.0.1:8211`
- das Worker-Terminal läuft noch
- `worker.agent` zeigt immer noch auf `http://127.0.0.1:8211`

### Sie möchten einen frischen Demo-Zustand

Der sicherste Reset besteht darin, die `root_path`-Werte auf einen neuen Ordnernamen zu setzen, anstatt die vorhandenen Daten zu löschen.

## Demo stoppen

Drücken Sie `Ctrl-C` in jedem Terminalfenster.
