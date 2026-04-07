# Demo de LLM Pulser

## Traducciones

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Archivos en esta carpeta

- `plaza.agent`: Plaza local para ambas variantes de pulser LLM
- `openai.pulser`: configuración de pulser respaldada por OpenAI
- `ollama.pulser`: configuración de pulser con soporte de Ollama
- `start-plaza.sh`: iniciar Plaza
- `start-openai-pulser.sh`: inicia el pulser de demostración de OpenAI
- `start-ollama-pulser.sh`: inicia el pulser de demostración de Ollama
- `run-demo.sh`: inicia la demostración completa desde una terminal y abre la guía del navegador más la interfaz de usuario del pulser seleccionado

## Lanzamiento con un solo comando

Desde la raíz del repositorio:
```bash
./demos/pulsers/llm/run-demo.sh
```

Por defecto, el wrapper utiliza OpenAI cuando `OPENAI_API_KEY` está presente y recurre a Ollama en caso contrario.

Ejemplos de proveedores explícitos:
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
```

Establezca `DEMO_OPEN_BROWSER=0` si desea que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows. Desde la raíz del repositorio en PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher llm
```

Si las pestañas del navegador no se abren automáticamente, mantenga el lanzador ejecutándose y abra la URL `guide=` impresa en un navegador de Windows.

## Inicio rápido

### Iniciar Plaza

Abre una terminal desde la raíz del repositorio:
```bash
./demos/pulsers/llm/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8261`

Luego elige un proveedor.

## Opción 1: OpenAI

Configure primero su clave API:
```bash
export OPENAI_API_KEY=your-key-here
```

Luego inicia el pulser:
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8262`
- se registra en el Plaza en `http://127.0.0.1:8261`

Payload de prueba sugerido:
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Ejemplo de Curl:
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## Opción 2: Ollama

Asegúrate de que Ollama se esté ejecutando localmente y que el modelo configurado esté disponible:
```bash
ollama serve
ollama pull qwen3:8b
```

Luego inicia el pulser:
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8263`
- se registra en el Plaza en `http://127.0.0.1:8261`

Ejemplo de curl sugerido:
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## Pruébalo en el navegador

Abre cualquiera de:

- `http://127.0.0.1:8262/` para OpenAI
- `http://127.0.0.1:8263/` para Ollama

La interfaz de usuario te permite:

- inspeccionar la configuración del pulser
- ejecutar `llm_chat`
- cargar listas de modelos
- inspeccionar la información del modelo de Ollama cuando se utiliza el proveedor local

## Qué señalar

- el mismo contrato pulse puede ejecutarse sobre inferencia en la nube o local
- cambiar entre OpenAI y Ollama es principalmente una cuestión de configuración, no de rediseño de la interfaz
- este es el demo más sencillo para explicar las herramientas LLM respaldadas por pulser en el repositorio

## Crea el tuyo propio

Para personalizar la demostración:

1. copia `openai.pulser` o `ollama.pulser`
2. cambiar `model`, `base_url`, puertos y rutas de almacenamiento
3. mantén estable el pulse `llm_chat` si otras herramientas o interfaces de usuario dependen de él
