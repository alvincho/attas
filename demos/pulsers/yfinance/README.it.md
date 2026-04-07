# Demo di YFinance Pulser

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

- `plaza.agent`: Plaza locale per questa demo
- `yfinance.pulser`: configurazione demo locale per `YFinancePulser`
- `start-plaza.sh`: avvia Plaza
- `start-pulser.sh`: avvia il pulser
- `run-demo.sh`: avvia la demo completa da un unico terminale e apre la guida del browser più l'interfaccia UI di pulser

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/pulsers/yfinance/run-demo.sh
```

Questo avvia Plaza e `YFinancePulser` da un unico terminale, apre una pagina di guida nel browser e apre automaticamente l'interfaccia utente di pulser.

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher yfinance
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio rapido

Apri due terminali dalla radice del repository.

### Terminale 1: avvia Plaza
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8251`

### Terminal 2: avvia il pulser
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

Risultato previsto:

- il pulser si avvia su `http://127.0.0.1:8252`
- si registra presso Plaza su `http://127.0.0.1:8251`

Nota:

- questa demo richiede l'accesso a Internet in uscita perché il pulser recupera dati in tempo reale tramite `yfinance`
- Yahoo Finance potrebbe limitare la frequenza delle richieste o rifiutarle intermittentemente

## Provalo nel browser

Apri:

- `http://127.0.0.1:8252/`

Primi pulse suggeriti:

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

Parametri suggeriti per `last_price`:
```json
{
  "symbol": "AAPL"
}
```

Parametri suggeriti per `ohlc_bar_series`:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Provalo con Curl

Richiesta di quotazione:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

Richiesta di serie OHLC:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## Cosa evidenziare

- lo stesso pulser espone sia pulse in stile snapshot che in stile time-series
- `ohlc_bar_series` è compatibile con il workbench chart demo e con il pulser del percorso technical-analysis
- il live provider può cambiare internamente in seguito, mentre il pulse contract rimane lo stesso

## Crea il tuo

Se desideri estendere questa demo:

1. copia `yfinance.pulser`
2. regola le porte e i percorsi di archiviazione
3. modifica o aggiungi definizioni di pulse supportate se desideri un catalogo più piccolo o più specializzato
