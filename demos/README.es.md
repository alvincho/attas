# Guías de demostración pública

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

Si vas a elegir un demo para probar primero, utilízalos en este orden:

1. [`hello-plaza`](./hello-plaza/README.md): el demo de descubrimiento multi-agente más ligero.
2. [`pulsers`](./pulsers/README.md): demos enfocados en almacenamiento de archivos, YFinance, LLM y ADS pulsers.
3. [`personal-research-workbench`](./personal-research-workbench/README.md): el recorrido de producto más visual.
4. [`data-pipeline`](./data-pipeline/README.md): un pipeline de ADS con respaldo local de SQLite con boss UI y pulser.

## Lanzadores de un solo comando

Cada carpeta de demo ejecutable incluye ahora un envoltorio `run-demo.sh` que inicia los servicios necesarios desde una sola terminal, abre una página de guía en el navegador con selección de idioma y abre automáticamente las páginas principales de la interfaz de usuario del demo.

Establezca `DEMO_OPEN_BROWSER=0` si desea que el envoltorio permanezca en la terminal sin abrir pestañas del navegador.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio, cree el entorno virtual una sola vez, instale los requisitos y luego ejecute cualquier wrapper de demo como `./demos/hello-plaza/run-demo.sh`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows. Desde la raíz del repositorio en PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

Si las pestañas del navegador no se abren automáticamente, mantenga el lanzador ejecutándose y abra la URL `guide=` impresa en un navegador de Windows.

En macOS y Linux, los wrappers `run-demo.sh` incluidos siguen funcionando como wrappers de conveniencia alrededor del mismo lanzador de Python.

## Configuración compartida

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Normalmente querrás tener abiertas entre 2 y 4 ventanas de la terminal, ya que la mayoría de los demos inician algunos procesos de larga duración.

Estas carpetas de demo escriben su estado de ejecución en `demos/.../storage/`. Ese estado es ignorado por git para que las personas puedan experimentar libremente.

## Catálogo de demos

### [`hello-plaza`](./hello-plaza/README.md)

- Audiencia: desarrolladores principiantes
- Entorno de ejecución: Plaza + worker + agente de usuario orientado al navegador
- Servicios externos: ninguno
- Qué demuestra: registro de agentes, descubrimiento y una interfaz de usuario sencilla en el navegador

### [`pulsers`](./pulsers/README.md)

- Audiencia: desarrolladores que buscan ejemplos de pulsers pequeños y directos
- Entorno de ejecución: pilas pequeñas de Plaza + pulser, además de una guía de ADS pulser que reutiliza el pipeline de SQLite
- Servicios externos: ninguno para el almacenamiento de archivos, internet de salida para YFinance y OpenAI, demonio local de Ollama para Ollema
- Qué demuestra: empaquetado de pulser independiente, pruebas, comportamiento de pulso específico del proveedor, cómo los analistas pueden publicar sus propios pulsos de información estructurados o impulsados por prompts, y cómo se ven esos pulsos dentro de un agente personal desde el punto de vista del consumidor

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- Audiencia: personas que desean una demostración de producto más sólida
- Entorno de ejecución: workbench React/FastAPI + Plaza local + pulser de almacenamiento de archivos local + pulser de YFinance opcional + pulser de análisis técnico opcional + almacenamiento de diagramas con semillas
- Servicios externos: ninguno para el flujo de almacenamiento, internet de salida para el flujo de gráficos de YFinance y el flujo de diagramas de OHLC-a-RSI en vivo
- Qué demuestra: espacios de trabajo, diseños, navegación en Plaza, renderizado de gráficos y ejecución de pulser impulsada por diagramas desde una interfaz de usuario más rica

### [`data-pipeline`](./data-pipeline/README.md)

- Audiencia: desarrolladores que evalúan la orquestación y los flujos de datos normalizados
- Entorno de ejecución: ADS dispatcher + worker + pulser + interfaz de boss
- Servicios externos: ninguno en la configuración de la demo
- Qué demuestra: trabajos en cola, ejecución de worker, almacenamiento normalizado, reexposición a través de un pulser y la ruta para conectar sus propias fuentes de datos

## Para alojamiento público

Estas demostraciones están diseñadas para que sea fácil auto-alojarlas después de que una ejecución local tenga éxito. Si las publicas públicamente, los valores predeterminados más seguros son:

- hacer que las demos alojadas sean de solo lectura o restablecerlas según un programa
- mantén desactivadas las integraciones con API o de pago en la primera versión pública
- indique a las personas los archivos de configuración utilizados por la demo para que puedan hacer un fork directamente
- incluye los comandos locales exactos del README de la demo junto a la URL en vivo
