# Conjunto de demostración de Pulser

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

## Empieza aquí

Utilízalos en este orden si es la primera vez que aprendes el modelo pulser:

1. [`file-storage`](./file-storage/README.md): la demo de pulser local más segura
2. [`analyst-insights`](./analyst-insights/README.md): un pulser propiedad de un analista y expuesto como vistas de información reutilizables
3. [`finance-briefings`](./finance-briefings/README.md): pulses de flujo de trabajo financiero publicados en un formato que MapPhemar y Personal Agent pueden ejecutar
4. [`yfinance`](./yfinance/README.md): un pulser de datos de mercado en vivo con salida de series temporales
5. [`llm`](./llm/README.md): pulsers de chat locales de Ollama y de la nube de OpenAI
6. [`ads`](./ads/README.md): el pulser ADS como parte de la demo del pipeline de SQLite

## Lanzadores de un solo comando

Cada carpeta de demo de pulser ejecutable incluye ahora un envoltorio `run-demo.sh` que inicia los servicios locales necesarios desde una sola terminal, abre una página de guía en el navegador con selección de idioma y abre automáticamente las páginas principales de la interfaz de usuario del demo.

Establezca `DEMO_OPEN_BROWSER=0` si desea que el envoltorio permanezca en la terminal sin abrir pestañas del navegador.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio, cree el entorno virtual una vez, instale los requisitos y luego ejecute cualquier wrapper de pulser como `./demos/pulsers/file-storage/run-demo.sh`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows. Desde la raíz del repositorio en PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

Si las pestañas del navegador no se abren automáticamente, mantenga el lanzador ejecutándose y abra la URL `guide=` impresa en un navegador de Windows.

## Qué cubre este conjunto de demostraciones

- cómo un pulser se registra en Plaza
- cómo probar pulsos desde el navegador o con `curl`
- cómo empaquetar un pulser como un pequeño servicio auto-alojado
- cómo se comportan las diferentes familias de pulser: almacenamiento, información de analistas, finanzas, LLM y servicios de datos

## Configuración compartida

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Cada carpeta de demo escribe el estado de ejecución local en `demos/pulsers/.../storage/`.

## Catálogo de Demos

### [`file-storage`](./file-storage/README.md)

- Runtime: Plaza + `SystemPulser`
- Servicios externos: ninguno
- Lo que demuestra: creación de buckets, guardado/carga de objetos y estado de pulser solo local

### [`analyst-insights`](./analyst-insights/README.md)

- Runtime: Plaza + `PathPulser`
- Servicios externos: ninguno para la vista estructurada, Ollama local para el flujo de noticias basado en prompts
- Lo que demuestra: cómo un analista puede publicar tanto vistas de investigación fijas como salidas de Ollama propiedad de prompts a través de múltiples pulses reutilizables, y luego exponerlas a otro usuario mediante un agente personal

### [`finance-brifings`](./finance-briefings/README.md)

- Runtime: Plaza + `FinancialBriefingPulser`
- Servicios externos: ninguno en la ruta de demo local
- Lo que demuestra: cómo un pulser propiedad de Attas puede publicar pasos de flujo de trabajo financiero como bloques de construcción direccionables por pulse, para que MapPhemar diagrams y Personal Agent puedan almacenar, editar y ejecutar el mismo grafo de flujo de trabajo

### [`yfinance`](./yfinance/README.md)

- Runtime: Plaza + `YFinancePulser`
- Servicios externos: conexión a internet hacia Yahoo Finance
- Lo que demuestra: pulses de instantáneas, pulses de series OHLC y cargas útiles de salida aptas para gráficos

### [`llm`](./llm/README.md)

- Runtime: Plaza + `OpenAIPulser` configurado para OpenAI o Ollama
- Servicios externos: OpenAI API para modo nube, daemon local de Ollama para modo local
- Lo que demuestra: `llm_chat`, interfaz de usuario de editor de pulser compartido y tubería de LLM intercambiable de proveedor

### [`ads`](./ads/README/README.md)

- Runtime: ADS dispatcher + worker + pulser + boss UI
- Servicios externos: ninguno en la ruta de demo de SQLite
- Lo que demuestra: `ADSPulser` sobre tablas de datos normalizadas y cómo sus propios colectores fluyen hacia esos pulses
