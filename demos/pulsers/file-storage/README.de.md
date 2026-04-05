# System Pulser Demo

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

- `plaza.agent`: lokaler Plaza für diese Pulser-Demo
- `file-storage.pulser`: lokales dateisystem-basiertes Storage-Pulser
- `start-plaza.sh`: Plaza starten
- `start-pulser.sh`: den pulser starten
- `run-demo.sh`: startet die vollständige Demo aus einem Terminal heraus und öffnet den Browser-Leitfaden sowie die pulser UI

## Start mit einem einzigen Befehl

Aus der Wurzel des Repositorys:
```bash
./demos/pulsers/file-storage/run-demo.sh
```

Dies startet Plaza und `SystemPulser` aus einem einzigen Terminal, öffnet eine Browser-Anleitungsseite und öffnet automatisch das Pulser-UI.

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Plattform Quick Start

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Verwenden Sie WSL2 mit Ubuntu oder einer anderen Linux-Distribution. Aus dem Repository-Root innerhalb von WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

Wenn Browser-Tabs nicht automatisch aus WSL heraus geöffnet werden, lassen Sie den Launcher weiter laufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

Native PowerShell / Command Prompt-Wrapper sind noch nicht enthalten, daher ist WSL2 heute der unterstützte Windows-Pfad.

## Quickstart

Öffnen Sie zwei Terminals aus der Wurzel des Repositorys.

### Terminal 1: Plaza starten
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet unter `http://127.0.0.1:8256`

### Terminal 2: den pulser starten
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8257`
- er registriert sich selbst bei Plaza unter `http://127.0.0.1:8256`

## Im Browser ausprobieren

Öffnen Sie:

- `http://127.0.0.1:8257/`

Testen Sie dann diese Pulses nacheinander:

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

Empfohlene Parameter für `bucket_create`:
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

Empfohlene Parameter für `object_save`:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

Empfohlene Parameter für `object_load`:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Testen Sie es mit Curl

Erstellen Sie einen Bucket:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

Ein Objekt speichern:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

Wieder laden:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## Was hervorzuheben ist

- dieser pulser ist vollständig lokal und benötigt keine Cloud-Anmeldedaten
- die Payloads sind einfach genug, um sie ohne zusätzliche Werkzeuge zu verstehen
- das Storage-Backend kann später vom Dateisystem auf einen anderen Anbieter umgestellt werden, während die Pulse-Schnittstelle stabil bleibt

## Bauen Sie Ihr eigenes

Wenn Sie es anpassen möchten:

1. kopieren Sie `file-storage.pulser`
2. ändern Sie die Ports und den Speicher-`root_path`
3. behalten Sie dieselbe pulse surface bei, wenn Sie Kompatibilität mit der Workbench und bestehenden Beispielen wünschen
