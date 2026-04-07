# Banco de Trabajo de Investigación Personal

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

## Qué muestra este demo

- la interfaz de usuario del banco de trabajo personal ejecutándose localmente
- un Plaza que el banco de trabajo puede explorar
- pulsers de datos locales y en vivo con pulses reales ejecutables
- un flujo de `Test Run` basado en diagramas que convierte los datos de mercado en una serie de indicadores calculados
- un camino desde una demo pulida hacia una instancia auto-alojada

## Archivos en esta carpeta

- `plaza.agent`: Plaza local utilizado solo para esta demo
- `file-storage.pulser`: pulser local basado en el sistema de archivos
- `yfinance.pulser`: pulser de datos de mercado opcional basado en el módulo Python `yfinance`
- `technical-analysis.pulser`: pulser de ruta opcional que calcula el RSI a partir de datos OHLC
- `map_phemar.phemar`: configuración de MapPhemar local de la demo utilizada por el editor de diagramas embebido
- `map_phemar_pool/`: almacenamiento de diagramas con un mapa OHLC-to-RSI listo para ejecutar
- `start-plaza.sh`: inicia la demo Plaza
- `start-file-storage-pulser.sh`: inicia el pulser
- `start-yfinance-pulser.sh`: inicia el pulser de YFinance
- `start-technical-analysis-pulser.sh`: inicia el pulser de análisis técnico
- `start-workbench.sh`: inicia el workbench de React/FastAPI

Todo el estado de ejecución se escribe en `demos/personal-research-workbench/storage/`. El lanzador también apunta el editor de diagramas embebido a los archivos preconfigurados `map_pheument.phemar` y `map_phemar_pool/` en esta carpeta.

## Requisitos previos

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Lanzamiento con un solo comando

Desde la raíz del repositorio:
```bash
./demos/personal-research-workbench/run-demo.sh
```

Esto inicia el stack del workbench desde una terminal, abre una página de guía en el navegador y luego abre tanto la interfaz principal de workbench como la ruta `MapPhemar` integrada que se utiliza en el recorrido principal.

Establece `DEMO_OPEN_BROWSER=0` si deseas que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows. Desde la raíz del repositorio en PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher personal-research-workbench
```

Si las pestañas del navegador no se abren automáticamente, mantén el lanzador ejecutándose y abre la URL `guide=` impresa en un navegador de Windows.

## Inicio rápido

Abra cinco terminales desde la raíz del repositorio si desea la demostración completa, incluyendo el flujo del gráfico de YFinance y el flujo de ejecución de prueba del diagrama.

### Terminal 1: iniciar el Plaza local

```bash
./demos/personal-research-workbench/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8241`

### Terminal 2: iniciar el pulser de almacenamiento de archivos local
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8242`
- se registra en el Plaza desde la Terminal 1

### Terminal 3: iniciar el pulser de YFinance
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8243`
- se registra en el Plaza desde la Terminal 1

Nota:

- este paso requiere acceso a internet saliente porque el pulser obtiene datos en vivo de Yahoo Finance a través del módulo `yfinance`
- Yahoo puede limitar ocasionalmente la frecuencia de las solicitudes, por lo que este flujo es mejor tratarlo como una demostración en vivo en lugar de una parte fija estricta

### Terminal 4: iniciar el pulser de análisis técnico
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8244`
- se registra en el Plaza desde la Terminal 1

Este pulser calcula `rsi` a partir de un `ohlc_series` entrante, o recupera barras OHLC desde el pulser demo de YFinance cuando solo proporcionas symbol, interval y date range.

### Terminal 5: iniciar el workbench
```bash
./demos/personal-research-workbench/start-workbench.sh
```

Resultado esperado:

- el workbench se inicia en `http://127.0.0.1:8041`

## Guía de la primera ejecución

Esta demostración tiene ahora tres flujos de trabajo:

1. flujo de almacenamiento local con el pulser file-storage
2. flujo de datos de mercado en vivo con el pulser YFinance
3. flujo de prueba de diagrama con los pulsers YFinance y technical-analysis

Abrir:

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### Flujo 1: navegar y guardar datos locales

Luego siga este breve camino:

1. Abra el flujo de configuración en el workbench.
2. Vaya a la sección `Connection`.
3. Establezca la URL predeterminada de Plaza en `http://127.0.0.1:8241`.
4. Actualice el catálogo de Plaza.
5. Abra o cree una ventana de navegador en el workbench.
6. Elija el pulser file-storage registrado.
7. Ejecute uno de los pulses integrados como `list_bucket`, `bucket_create` o `bucket_browse`.

Primera interacción sugerida:

- crear un bucket público llamado `demo-assets`
- navegar por ese bucket
- guardar un pequeño objeto de texto
- cargarlo de nuevo

Eso le da a las personas un ciclo completo: interfaz de usuario rica, descubrimiento en Plaza, ejecución de pulser y estado local persistente.

### Flujo 2: ver datos y dibujar un gráfico desde el pulser YFinance

Use la misma sesión del workbench, luego:

1. Actualice el catálogo de Plaza nuevamente para que aparezca el pulser YFinance.
2. Agregue un nuevo panel de navegador o reconfigure un panel de datos existente.
3. Elija el pulse `ohlc_bar_series`.
4. Elija el pulser `DemoYFinancePulser` si el workbench no lo selecciona automáticamente.
5. Abra `Pane Params JSON` y use un payload como este:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. Haga clic en `Get Data`.
7. En `Display Fields`, active `ohlc_series`. Si ya hay otro campo seleccionado, desactívelo para que la vista previa apunte a la propia serie temporal.
8. Cambie `Format` a `chart`.
9. Establezca `Chart Style` en `candle` para velas OHLC o `line` para una vista de tendencia simple.

Lo que debería ver:

- el panel obtiene los datos de barras para el símbolo y el rango de fechas solicitados
- la vista previa cambia de datos estructurados a un gráfico
- cambiar el símbolo o el rango de fechas le proporciona un nuevo gráfico sin salir del workbench

Variaciones recomendadas:

- cambie `AAPL` por `MSFT` o `NVDA`
- acorte el rango de fechas para una vista reciente más detallada
- compare `line` y `candle` usando la misma respuesta `ohlc_bar_series`

### Flujo 3: cargar un diagrama y usar Test Run para calcular una serie RSI

Abra la ruta del editor de diagramas:

- `http://12</strong>1.0.0.1:8041/map-phemar/`

Luego siga este camino:

1. Confirme que la URL de Plaza en el editor de diagramas sea `http://127.0.0.1:8241`.
2. Haga clic en `Load Phema`.
3. Elija `OHLC To RSI Diagram`.
4. Inspeccione el gráfico inicial. Debe mostrar `Input -> OHLC Bars -> RSI 14 -> Output`.
5. Haga clic en `Test Run`.
6. Use este payload de entrada:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. Ejecuta el mapa y expande las salidas de los pasos.

Lo que deberías ver:

- el paso `OHLC Bars` llama al pulser de demo YFinance y devuelve `ohlc_series`
- el paso `RSI 14` reenvía esas barras al pulser de technical-analysis con `window: 14`
- la carga útil `Output` final contiene un array `values` calculado con entradas `timestamp` y `value`

Si quieres reconstruir el mismo diagrama desde cero en lugar de cargar la semilla:

1. Añade un nodo redondeado llamado `OHLC Bars`.
2. Vincúlalo a `DemoYFinancePulser` y al pulse `ohlc_bar_series`.
3. Añade un nodo redondeado llamado `RSI 14`.
4. Vincúlalo a `DemoTechnicalAnalysisPulser` y al pulse `rsi`.
5. Establece los parámetros del nodo RSI en:
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. Conectar `Input -> OHLC Bars -> RSI 14 -> Output`.
7. Dejar los mapeos de bordes como `{}` para que los nombres de campos coincidentes fluyan automáticamente.

## Qué destacar en una llamada de demostración

- El workbench sigue cargando datos útiles de dashboards simulados incluso antes de añadir cualquier conexión en vivo.
- La integración de Plaza es opcional y puede apuntar a un entorno local o remoto.
- El pulser de almacenamiento de archivos es solo local, lo que hace que la demo pública sea segura y reproducible.
- El pulser de YFinance añade una segunda historia: el mismo workbench puede navegar por datos de mercado en vivo y renderizarlos como un gráfico.
- El editor de diagramas añade una tercera historia: el mismo backend puede orquestar flujos de múltiples pasos y exponer cada paso a través de `Test Run`.

## Crea tu propia instancia

Existen tres rutas de personalización comunes:

### Cambiar los datos iniciales del dashboard y del espacio de trabajo

El workbench lee su instantánea del dashboard desde:

- `attas/personal_agent/data.py`

Ese es el lugar más rápido para intercambiar tus propias listas de seguimiento, métricas o valores predeterminados del espacio de trabajo.

### Cambiar la interfaz visual

El tiempo de ejecución actual del workbench en vivo se sirve desde:

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

Si deseas cambiar el tema de la demo o simplificar la interfaz de usuario para tu audiencia, comienza ahí.

### Cambiar los Plaza y pulsers conectados

Si deseas un backend diferente:

1. copia `plaza.agent`, `file-storage.pulser`, `yfinance.pulser` y `technical-analysis.pulser`
2. renombra los servicios
3. actualiza los puertos y las rutas de almacenamiento
4. edita el diagrama inicial en `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` o crea el tuyo propio desde el workbench
5. reemplaza los pulsers de la demo con tus propios agentes cuando estés listo

## Configuración opcional del Workbench

El script de lanzamiento admite un par de variables de entorno útiles:
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

Utilice `PHEMACAST_PERSONAL_AGENT_RELOAD=1` cuando esté editando activamente la aplicación FastAPI durante el desarrollo.

## Resolución de problemas

### El workbench se carga, pero los resultados de Plaza están vacíos

Comprueba estas tres cosas:

- `http://127.0.0.1:8241/health` es accesible
- los terminales de file-storage, YFinance y technical-analysis pulser siguen ejecutándose cuando necesitas esos flujos
- la configuración de `Connection` del workbench apunta a `http://127.0.0.1:8241`

### El pulser aún no muestra ningún objeto

Esto es normal en el primer arranque. El backend de almacenamiento de la demo comienza vacío.

### El panel de YFinance no dibuja un gráfico

Comprueba lo siguiente:

- el terminal de YFinance pulser está en ejecución
- el pulse seleccionado es `ohlc_bar_series`
- `Display Fields` incluye `ohlc_series`
- `Format` está configurado como `chart`
- `Chart Style` es `line` o `candle`

Si la solicitud falla, intenta con otro símbolo o vuelve a ejecutarla tras una breve espera, ya que Yahoo puede limitar la tasa de peticiones o rechazar solicitudes de forma intermitente.

### El diagrama `Test Run` falla

Comprueba lo siguiente:

- `http://127.0.0.1:8241/health` es accesible
- el YFinance pulser se está ejecutando en `http://127.0.0.1:8243`
- el technical-analysis pulser se está ejecutando en `http://127.0.0.1:8244`
- el diagrama cargado es `OHLC To RSI Diagram`
- la carga útil de entrada incluye `symbol`, `interval`, `start_date` y `end_date`

Si el paso `OHLC Bars` falla primero, el problema suele ser el acceso en vivo a Yahoo o la limitación de tasa. Si el paso `RSI 14` falla, la causa más común es que el technical-analysis pulser no se está ejecutando o la respuesta OHLC ascendente no incluyó `ohlc_series`.

### Deseas restablecer la demo

El restablecimiento más seguro es apuntar los valores de `root_path` a un nuevo nombre de carpeta, o eliminar la carpeta `demos/personal-research-workbench/storage/` cuando no haya procesos de la demo en ejecución.

## Detener la demostración

Presiona `Ctrl-C` en cada ventana de la terminal.
