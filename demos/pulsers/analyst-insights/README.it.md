# Demo Analyst Insight Pulser

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

- un pulser di proprietà di un analista con molteplici pulse di approfondimento strutturate
- un secondo pulser di proprietà di un analista che si appoggia a un agente news separato e a un agente locale Ollama
- un modo pulito per separare i dati grezzi della fonte dai Prompits scritti dall'analista e dagli output finali rivolti al consumatore
- una panoramica dell'agente personale che mostra lo stesso stack dal punto di vista di un altro utente
- i file esatti che un analista o un PM modificherebbe per pubblicare la propria visione

## File in questa cartella

- `plaza.agent`: Plaza locale per la demo dell'analyst pulser
- `analyst-insights.pulser`: Configurazione `PathPulser` che definisce il catalogo pubblico dei pulse
- `analyst_insight_step.py`: Logica di trasformazione condivisa più il pacchetto di copertura analista predefinito
- `news-wire.pulser`: Agente news upstream locale che pubblica pacchetti `news_article` predefiniti
- `news_wire_step.py`: Pacchetti news grezzi predefiniti restituiti dall'agente news upstream
- `ollama.pulser`: Pulser `llm_chat` locale basato su Ollama per la demo dei prompt dell'analista
- `analyst-news-ollama.pulser`: Pulser analista composto che recupera le news, applica i prompt di proprietà dell'analista, chiama Ollama e normalizza il risultato in più pulse
- `analyst_news_ollama_step.py`: Il pacchetto di prompt dell'analista più la logica di normalizzazione JSON
- `start-plaza.sh`: Avvia Plaza
- `start-pulser.sh`: Avvia il pulser analista strutturato fisso
- `start-news-pulser.sh`: Avvia l'agente news upstream predefinito
- `start-ollama-lar.sh`: Avvia il pulser Ollama locale
- `start-analyst-news-pulser.sh`: Avvia il pulser analista con prompt
- `start-personal-agent.sh`: Avvia l'interfaccia utente dell'agente personale per la demo della vista consumatore
- `run-demo.sh`: Avvia la demo da un terminale e apre la guida del browser più le pagine principali dell'interfaccia utente

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

Quel wrapper avvia il flusso strutturato leggero per impostazione predefinita.

Per avviare invece il flusso avanzato news + Ollama + agente personale:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

Imposta `DEMO_OPEN_BROWSER=0` se desideri che il launcher rimanga solo nel terminale.

## Avvio rapido della piattaforma

### macOS e Linux

Dalla radice del repository:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

Per il percorso avanzato:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

Usa WSL2 con Ubuntu o un'altra distribuzione Linux. Dalla radice del repository all'interno di WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

Per il percorso avanzato all'interno di WSL:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

Se le schede del browser non si aprono automaticamente da WSL, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

I wrapper nativi di PowerShell / Command Prompt non sono ancora stati inclusi, quindi oggi la strada Windows supportata è WSL2.

## Demo 1: Visualizzazioni strutturate degli analisti

Questo è il percorso solo locale, senza LLM.

Apri due terminali dalla radice del repository.

### Terminale 1: avvia Plaza
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8266`

### Terminal 2: avvia il pulser
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

Risultato atteso:

- il pulser si avvia su `http://127.0.0.1:8267`
- si registra presso il Plaza su `http://127.0.0.1:8266`

## Provalo nel browser

Apri:

- `http://127.0.0.1:8267/`

Quindi testa questi pulse con `NVDA`:

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

Parametri suggeriti per tutti e quattro:
```json
{
  "symbol": "NVDA"
}
```

Cosa dovresti vedere:

- `rating_summary` restituisce la valutazione principale, l'obiettivo, la fiducia e un breve riepilogo
- `thesis_bullets` restituisce la tesi positiva in formato elenco
- `risk_watch` restituisce i rischi principali più cosa monitorare
- `scenario_grid` restituisce i casi bull, base e bear in un unico payload strutturato

## Provalo con Curl

Valutazione del titolo:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

Punti chiave della tesi:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

Monitoraggio dei rischi:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## Come un analista personalizza questa demo

Ci sono due punti di modifica principali.

### 1. Cambiare la visualizzazione della ricerca effettiva

Modificare:

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

Questo file contiene il pacchetto `ANALYST_COVERAGE` inizializzato. È lì che si modificano:

- i simboli coperti
- il nome dell'analista
- le etichette di valutazione
- i prezzi target
- i punti della tesi
- i rischi chiave
- gli scenari rialzista/base/ribassista

### 2. Cambiare il catalogo pubblico dei pulse

Modificare:

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

Quel file controlla:

- quali pulse esistono
- il nome e la descrizione di ogni pulse
- gli schemi di input e output
- tag e indirizzi

Se desideri aggiungere un nuovo pulse di insight, copia una delle voci esistenti e puntala a un nuovo `insight_view`.

## Perché questo pattern è utile

- gli strumenti di portafoglio possono richiedere solo il `rating_summary`
- i generatori di report possono richiedere `thesis_bullets`
- le dashboard di rischio possono richiedere `risk_watch`
- gli strumenti di valutazione possono richiedere `scenario_grid`

Ciò significa che l'analista pubblica un unico servizio, ma diversi consumatori possono estrarre esattamente la porzione di cui hanno bisogno.

## Cosa fare successivamente

Una volta che questa forma di pulser locale ha senso, i passaggi successivi sono:

1. aggiungere altri simboli coperti al pacchetto di copertura degli analisti
2. aggiungere passaggi di origine prima dell'ultimo passaggio Python se si desidera combinare la propria visione con gli output di YFinance, ADS o LLM
3. esporre il pulser attraverso un Plaza condiviso invece di solo il Plaza demo locale

## Demo 2: Analyst Prompt Pack + Ollama + Agente Personale

Questo secondo flusso mostra una configurazione di analista più realistica:

- un agente pubblica dati grezzi `news_article`
- un secondo agente espone `llm_chat` tramite Ollama
- il pulser di proprietà dell'analista utilizza il proprio prompt pack per trasformare quelle notizie grezze in più pulse riutilizzabili
- l'agente personale consuma i pulse completati dal punto di vista di un utente diverso

### Prerequis per il flusso dei prompt

Assicurati che Ollama sia in esecuzione localmente e che il modello esista:

```bash
ollama serve
ollama pull qwen3:8b
```

Quindi apri cinque terminali dalla radice del repository.

### Terminale 1: avvia Plaza

Se il Demo 1 è ancora in esecuzione, continua a usare lo stesso Plaza.
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8266`

### Terminal 2: avvia l'agente news upstream
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

Risultato atteso:

- il news pulser si avvia su `http://127.0.0.1:8268`
- si registra presso il Plaza su `http://127.0.0.1:8266`

### Terminal 3: avvia il pulser di Ollama
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

Risultato previsto:

- il pulser di Ollama si avvia su `http://127.0.0.1:8269`
- si registra presso Plaza su `http://127.0.0.1:8266`

### Terminal 4: avvia il pulser prompted analyst

Avvia questo dopo che gli agent news e Ollama sono già in esecuzione, poiché il pulser valida le sue catene di campionamento durante l'avvio.
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

Risultato atteso:

- il pulser dell'analista richiesto si avvia su `http://127.0.0.1:8270`
- si registra presso Plaza su `http://127.0.0.1:8266`

### Terminal 5: avvia l'agente personale
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

Risultato previsto:

- l'agente personale si avvia su `http://127.0.0.1:8061`

### Prova direttamente il Prompted Analyst Pulser

Apri:

- `http://127.0.0.1:8270/`

Quindi testa questi pulses con `NVDA`:

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

Parametri suggeriti:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Quello che dovresti vedere:

- `news_desk_brief` trasforma gli articoli upstream in una posizione in stile PM e una breve nota
- `news_monitoring_points` trasforma gli stessi articoli grezzi in elementi di monitoraggio e flag di rischio
- `news_client_note` trasforma gli stessi articoli grezzi in una nota più pulita rivolta al cliente

Il punto importante è che l'analista controlla i Prompits in un unico file, mentre gli utenti downstream vedono solo interfacce pulse stabili.

### Usa l'Agente Personale dalla Vista di un Altro Utente

Apri:

- `http://127.0.0.1:8061/`

Poi segui questo percorso:

1. Apri `Settings`.
2. Vai alla scheda `Connection`.
3. Imposta l'URL di Plaza su `http://127.0.0.1:8266`.
4. Clicca su `Refresh Plaza Catalog`.
5. Crea una `New Browser Window`.
6. Metti la finestra del browser in modalità `edit`.
7. Aggiungi un primo pane plain e puntalo a `DemoAnalystNewsWirePulser -> news_article`.
8. Usa i pane params:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. Fai clic su `Get Data` in modo che l'utente possa vedere gli articoli grezzi.
10. Aggiungi un secondo pannello semplice e puntalo a `DemoAnalystPromptedNewsPulser -> news_desk_brief`.
11. Riutilizza gli stessi parametri e fai clic su `Get</strong>`
12. Aggiungi un terzo pannello con `news_monitoring_points` o `news_client_note`.

Quello che dovresti vedere:

- un pannello mostra le notizie grezze upstream da un altro agente
- il pannello successivo mostra la vista elaborata dall'analista
- il terzo pannello mostra come lo stesso pacchetto di prompt dell'analista possa pubblicare una superficie diversa per un pubblico diverso

Questa è la storia chiave del consumatore: un altro utente non ha bisogno di conoscere la catena interna. Basta sfogliare Plaza, scegliere un pulse e consumare l'output finale dell'analista.

## Come un analista personalizza il flusso di prompt

Ci sono tre punti di modifica principali nel Demo 2.

### 1. Cambiare il pacchetto di notizie upstream

Modificare:

- `demos/pulsers/analyst-insights/news_wire_step.py`

È qui che si cambiano gli articoli seed pubblicati dall'agente della fonte upstream.

### 2. Cambiare i prompt dell'analista

Modificare:

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

Quel file contiene il pacchetto di prompt di proprietà dell'analista, che include:

- nomi dei profili di prompt
- pubblico e obiettivo
- tono e stile di scrittura
- contratto di output JSON richiesto

È il modo più veloce per far sì che le stesse notizie grezze producano una voce di ricerca differente.

### 3. Cambiare il catalogo pubblico dei pulse

Modificare:

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

Quel file controlla:

- quali prompted pulse esistono
- quale profilo di prompt utilizza ogni pulse
- quali agenti upstream chiama
- gli schemi di input e output mostrati agli utenti downstream

## Perché il pattern avanzato è utile

- l'agente di notizie upstream può essere sostituito in seguito da YFinance, ADS o un raccoglitore interno
- l'analista mantiene la proprietà del pacchetto di prompt invece di codificare note singole in un'interfaccia utente
- diversi consumatori possono utilizzare diversi pulses senza conoscere l'intera catena sottostante
- l'agente personale diventa una superficie di consumo pulita invece del luogo in cui risiede la logica
