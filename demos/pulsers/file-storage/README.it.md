# Demo System Pulser

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

## File in questa cartella

- `plaza.agent`: Plaza locale per questa demo di pulser
- `file-storage.pulser`: pulser di archiviazione basato sul file system locale
- `start-plaza.sh`: avvia Plaza
- `start-pulser.sh`: avvia il pulser
- `run-demo.sh`: avvia la demo completa da un terminale e apre la guida del browser più l'interfaccia utente di pulser UI

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/pulsers/file-storage/run-demo.sh
```

Questo avvia Plaza e `SystemPulser` da un unico terminale, apre una pagina di guida nel browser e apre automaticamente l'interfaccia utente di pulser.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio rapido

Apri due terminali dalla radice del repository.

### Terminale 1: avvia Plaza
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8256`

### Terminal 2: avvia il pulser
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

Risultato atteso:

- il pulser si avvia su `http://127.0.0.1:8257`
- si registra presso Plaza su `http://120.0.0.1:8256`

## Provalo nel browser

Apri:

- `http://127.0.0.1:8257/`

Quindi testa questi pulse in ordine:

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

Parametri suggeriti per `bucket_create`:
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

Parametri suggeriti per `object_save`:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

Parametri suggeriti per `object_load`:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Provalo con Curl

Crea un bucket:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

Salva un oggetto:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

Ricaricalo:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## Cosa evidenziare

- questo pulser è completamente locale e non richiede credenziali cloud
- i payload sono abbastanza semplici da comprendere senza strumenti aggiuntivi
- il backend di archiviazione può essere successivamente sostituito dal file system a un altro provider mantenendo stabile l'interfaccia di pulse

## Crea il tuo

Se desideri personalizzarlo:

1. copia `file-storage.pulser`
2. modifica le porte e il `root_path` di archiviazione
3. mantieni la stessa pulse surface se desideri la compatibilità con il workbench e gli esempi esistenti
