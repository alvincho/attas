# LLM Pulser Demo

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

- `plaza.agent`: lokales Plaza für beide LLM-Pulser-Varianten
- `openai.pulser`: von OpenAI unterstützte pulser-Konfiguration
- `ollama.pulser`: Ollama-gestützte pulser-Konfiguration
- `start-plaza.sh`: Plaza starten
- `start-openai-pulser.sh`: startet den OpenAI Demo-Pulser
- `start-ollama-pulser.sh`: startet den Ollama Demo-Pulser
- `run-demo.sh`: startet die vollständige Demo aus einem Terminal heraus und öffnet den Browser-Leitfaden sowie das ausgewählte pulser UI

## Einzelbefehl-Start

Aus der Wurzel des Repositorys:
```bash
./demos/pulsers/llm/run-demo.sh
```

Standardmäßig verwendet der Wrapper OpenAI, wenn `OPENAI_API_KEY` vorhanden ist, andernfalls wird auf Ollama zurückgegriffen.

Beispiele für explizite Provider:
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
```

Setzen Sie `DEMO_OPEN_BROWSER=0`, wenn der Launcher nur im Terminal verbleiben soll.

## Schnellstart der Plattform

### macOS und Linux

Aus der Wurzel des Repositorys:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

### Windows

Verwenden Sie eine native Windows-Python-Umgebung. Aus der Wurzel des Repositorys in der PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher llm
```

Falls sich die Browser-Tabs nicht automatisch öffnen, lassen Sie den Launcher weiterlaufen und öffnen Sie die gedruckte `guide=` URL in einem Windows-Browser.

## Quickstart

### Plaza starten

Öffne ein Terminal aus dem Repository-Root:
```bash
./demos/pulsers/llm/start-plaza.sh
```

Erwartetes Ergebnis:

- Plaza startet auf `http://127.0.0.1:8261`

Wählen Sie dann einen Anbieter aus.

## Option 1: OpenAI

Legen Sie zuerst Ihren API-Schlüssel fest:
```bash
export OPENAI_API_KEY=your-key-here
```

Starten Sie dann den pulser:
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8262`
- er registriert sich beim Plaza unter `http://127.0.0.1:8261`

Empfohlene Test-Payload:
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Curl-Beispiel:
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## Option 2: Ollama

Stelle sicher, dass Ollama lokal läuft und das konfigurierte Modell verfügbar ist:
```bash
ollama serve
ollama pull qwen3:8b
```

Starten Sie dann den pulser:
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

Erwartetes Ergebnis:

- der pulser startet auf `http://127.0.0.1:8263`
- er registriert sich beim Plaza unter `http://127.0.0.1:8261`

Empfohlenes curl-Beispiel:
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## Im Browser ausprobieren

Öffnen Sie eines der folgenden:

- `http://127.0.0.1:8262/` für OpenAI
- `http://127.0.0.1:8263/` für Ollama

Die Benutzeroberfläche ermöglicht es Ihnen:

- die pulser-Konfiguration zu überprüfen
- `llm_chat` auszuführen
- Modelllisten zu laden
- Ollama-Modellinformationen zu überprüfen, wenn der lokale Anbieter verwendet wird

## Was hervorzuheben ist

- derselbe pulse-Vertrag kann auf Cloud- oder lokaler Inferenz basieren
- Der Wechsel zwischen OpenAI und Ollama ist hauptsächlich eine Frage der Konfiguration, nicht einer Neugestaltung der Benutzeroberfläche
- dies ist die einfachste Demo zur Erläuterung der pulser-gestützten LLM-Tools im Repository

## Erstellen Sie Ihr eigenes

Um die Demo anzupassen:

1. kopiere `openai.pulser` oder `ollama.pulser`
2. `model`, `base_url`, Ports und Speicherpfade ändern
3. halten Sie den `llm_chat` Pulse stabil, falls andere Tools oder UIs davon abhängen
