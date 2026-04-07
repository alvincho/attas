# Demo LLM Pulser

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

- `plaza.agent`: Plaza locale per entrambe le varianti di pulser LLM
- `openai.pulser`: configurazione pulser supportata da OpenAI
- `ollama.pulser`: configurazione del pulser basata su Ollama
- `start-plaza.sh`: avvia Plaza
- `start-openai-pulser.sh`: avvia il pulser demo di OpenAI
- `start-ollama-pulser.sh`: avvia il pulser demo di Ollama
- `run-demo.sh`: avvia la demo completa da un terminale e apre la guida del browser più l'interfaccia utente del pulser selezionato

## Avvio con un singolo comando

Dalla radice del repository:
```bash
./demos/pulsers/llm/run-demo.sh
```

Per impostazione predefinita, il wrapper utilizza OpenAI quando `OPENAI_API_KEY` è presente, altrimenti utilizza Ollama.

Esempi di provider espliciti:
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
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
./demos/pulsers/llm/run-demo.sh
```

### Windows

Utilizza un ambiente Python nativo per Windows. Dalla radice del repository in PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher llm
```

Se le schede del browser non si aprono automaticamente, mantieni il launcher in esecuzione e apri l'URL `guide=` stampata in un browser Windows.

## Avvio rapido

### Avvia Plaza

Apri un terminal dalla radice del repository:
```bash
./demos/pulsers/llm/start-plaza.sh
```

Risultato atteso:

- Plaza si avvia su `http://127.0.0.1:8261`

Quindi scegli un provider.

## Opzione 1: OpenAI

Imposta prima la tua chiave API:
```bash
export OPENAI_API_KEY=your-key-here
```

Quindi avvia il pulser:
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

Risultato previsto:

- il pulser si avvia su `http://127.0.0.1:8262`
- si registra presso il Plaza su `http://127.0.0.1:8261`

Payload di test suggerito:
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Esempio Curl:
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## Opzione 2: Ollama

Assicurati che Ollama sia in esecuzione localmente e che il modello configurato sia disponibile:
```bash
ollama serve
ollama pull qwen3:8b
```

Quindi avvia il pulser:
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

Risultato previsto:

- il pulser si avvia su `http://127.0.0.1:8263`
- si registra presso il Plaza su `http://127.0.0.1:8261`

Esempio curl suggerito:
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## Provalo nel browser

Apri uno dei seguenti:

- `http://127.0.0.1:8262/` per OpenAI
- `http://127.0.0.1:8263/` per Ollama

L'interfaccia utente ti consente di:

- ispezionare la configurazione del pulser
- eseguire `llm_chat`
- caricare elenchi di modelli
- ispezionare le informazioni sul modello Ollama quando si utilizza il provider locale

## Cosa evidenziare

- lo stesso contratto pulse può essere eseguito su inferenza cloud o locale
- passare da OpenAI a Ollama è principalmente una questione di configurazione, non di riprogettazione dell'interfaccia
- questo è il demo più semplice per spiegare gli strumenti LLM basati su pulser nel repository

## Crea il tuo

Per personalizzare la demo:

1. copia `openai.pulser` o `ollama.pulser`
2. modificare `model`, `base_url`, le porte e i percorsi di archiviazione
3. mantieni stabile il pulse `llm_chat` se altri strumenti o interfacce utente ne dipendono
