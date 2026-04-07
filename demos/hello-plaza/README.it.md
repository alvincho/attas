# Hello Plaza

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

## Cosa mostra questa demo

- un registro Plaza in esecuzione localmente
- un agente che si registra automaticamente con Plaza
- un'interfaccia utente lato browser collegata a quel Plaza
- un set di configurazione minimo che gli sviluppatori possono copiare nel proprio progetto

## File in questa cartella

- `plaza.agent`: configurazione demo Plaza
- `worker.agent`: configurazione demo worker
- `user.agent`: configurazione demo user-agent
- `start-plaza.sh`: avvia Plaza
- `start-worker.sh`: avvia il worker
- `start-user.sh`: avvia l'user agent rivolto al browser

Tutti gli stati di runtime sono scritti in `demos/hello-plaza/storage/`.

## Prerequisiti

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/hello-plaza/run-demo.sh
```

Questo avvia Plaza, il worker e l'interfaccia utente da un unico terminale, apre una pagina di guida nel browser e apre automaticamente l'interfaccia utente.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio rapido

Apri tre terminali dalla radice del repository.

### Terminale 1: avvia Plaza
```bash
./demos/hello-plaza/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` restituisce uno stato di salute

### Terminale 2: avvia il worker
```bash
./demos/hello-plaza/start-worker.sh
```

Risultato atteso:

- il worker si avvia su `127.0.0.1:8212`
- it si registra automaticamente con Plaza da Terminal 1

### Terminale 3: avvia l'interfaccia utente

```bash
./demos/hello-plaza/start-user.sh
```

Risultato previsto:

- l'user agent rivolto al browser si avvia su `http://127.0.0.1:8214/`

## Verifica lo stack

In un quarto terminale, o dopo che i servizi sono attivi:
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

Cosa dovresti vedere:

- il primo comando restituisce una risposta Plaza corretta
- il secondo comando mostra il Plaza locale e il `demo-worker` registrato

Quindi apri:

- `http://127.0.0.1:8214/`

Questo è l'URL della demo pubblica da condividere in una presentazione locale o in una registrazione dello schermo.

## Cosa evidenziare durante una demo call

- Plaza è lo strato di scoperta.
- Il worker può essere avviato indipendentemente e apparirà comunque nella directory condivisa.
- L'interfaccia utente non necessita di una conoscenza predefinita del worker. Lo scopre tramite Plaza.

## Crea la tua istanza personalizzata

Il modo più semplice per trasformare questo nella tua istanza personale è:

1. Copia `plaza.agent`, `worker.agent` e `user.agent` in una nuova cartella.
2. Rinomina gli agent.
3. Cambia le porte se necessario.
4. Punta ogni `root_path` alla tua posizione di archiviazione.
5. Se modifichi l'URL o la porta di Plaza, aggiorna `plaza_url` in `agent` e `user.agent`.

I tre campi più importanti da personalizzare sono:

- `name`: ciò che l'agente annuncia come propria identità
- `port`: dove ascolta il servizio HTTP
- `root_path`: dove viene memorizzato lo stato locale

Una volta che i file sono corretti, esegui:
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## Risoluzione dei problemi

### Porta già in uso

Modifica il file `.agent` pertinente e scegli una porta libera. Se sposti Plaza su una nuova porta, aggiorna il `plaza_url` in entrambe le configurazioni dipendenti.

### L'interfaccia utente mostra una directory di Plaza vuota

Controlla queste tre cose:

- Plaza è in esecuzione su `http://127.0.0.1:8211`
- il terminale del worker è ancora in esecuzione
- `worker.agent` punta ancora a `http://127.0.0.1:8211`

### Desideri uno stato demo nuovo

Il reset più sicuro consiste nel puntare i valori `root_path` a un nuovo nome di cartella invece di eliminare i dati esistenti.

## Interrompere la Demo

Premi `Ctrl-C` in ogni finestra del terminale.
