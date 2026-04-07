# Demo ADS Pulser

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

## Cosa copre questa demo

- come `ADSPulser` si appoggia su tabelle ADS normalizzate
- come l'attività del dispatcher e del worker si trasforma in dati visibili al pulser
- come i propri collector possono inserire dati nelle tabelle ADS e apparire attraverso i pulse esistenti

## Configurazione

Segui la guida rapida in:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Oppure usa il wrapper a comando singolo focalizzato su pulser dalla radice del repository:
```bash
./demos/pulsers/ads/run-demo.sh
```

Quel wrapper avvia lo stesso stack SQLite ADS di `data-pipeline`, ma apre una guida nel browser e delle schede focalizzate sulla procedura guidata pulser-first.

Questo avvia:

1. l'ADS dispatcher
2. l'ADS worker
3. l'ADS pulser
4. la boss UI

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher ads
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Primi controlli di Pulser

Una volta terminati i job di esempio, apri:

- `http://127.0.0.1:9062/`

Quindi testa:

1. `security_master_lookup` con `{"symbol":" AAPL","limit":1}`
2. `daily_price_history` con `{"symbol":"AAPL","limit":5}`
3. `company_profile` con `{"symbol":"AAPL"}`
4. `news_article` con `{"symbol":"AAPL","number_of_articles":3}`

## Perché ADS è diverso

Gli altri demo di pulser leggono principalmente direttamente da un provider live o da un backend di archiviazione locale.

`ADSPulser`, invece, legge dalle tabelle normalizzate scritte dalla pipeline ADS:

- i worker raccolgono o trasformano i dati sorgente
- il dispatcher persiste le righe normalizzate
- `ADSPulser` espone tali righe come pulse interrogabili

Questo lo rende il demo ideale per spiegare come aggiungere i propri adattatori di sorgente.

## Aggiungi la tua sorgente personalizzata

La guida dettagliata si trova in:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Usa gli esempi personalizzati qui:

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

Quegli esempi mostrano come un collettore definito dall'utente può scrivere in:

- `ads_news`, che diventa disponibile tramite `news_article`
- `ads_daily_price`, che diventa disponibile tramite `daily_price_history`
