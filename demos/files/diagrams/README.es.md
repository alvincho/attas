# Biblioteca de diagramas de demostración

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

## Notas de la plataforma

Esta carpeta contiene activos JSON, no un lanzador independiente.

### macOS y Linux

Inicie primero uno de los demos emparejados y luego cargue estos archivos en MapPhemar o Personal Agent:
```bash
./demos/personal-research-workbench/run-demo.sh
```

También puede iniciar:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows para los lanzadores de demo emparejados, por ejemplo `py -3 -m scripts.demo_launcher analyst-insights` y `py -3 -m scripts.demo_launcher finance-briefings`. Una vez que el stack esté en funcionamiento, abra la URL `guide=` impresa en un navegador de Windows si las pestañas no se abren automáticamente.

## Qué hay en esta carpeta

Hay dos grupos de ejemplos:

- diagramas de análisis técnico que convierten los datos de mercado OHLC en series de indicadores
- diagramas de analistas orientados a LLM que convierten las noticias de mercado sin procesar en notas de investigación estructuradas
- diagramas de flujo de trabajo financiero que convierten las entradas de investigación normalizadas en paquetes de informes, publicaciones y exportaciones de NotebookLM

## Archivos en esta carpeta

### Análisis técnico

- `ohlc-to-sma-20-diagram.json`: `Entrada -> Barras OHLC -> SMA 20 -> Salida`
- `ohlca-to-ema-50-diagram.json`: `Entrada -> Barras OHLC -> EMA 50 -> Salida`
- `ohlc-to-macd-histogram-diagram.json`: `Entrada -> Barras OHLC -> Histograma MACD -> Salida`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `Entrada -> Barras OHLC -> Ancho de banda de Bollinger -> Salida`
- `ohlc-to-adx-14-diagram.json`: `Entrada -> Barras OHLC -> ADX 14 -> Salida`
- `ohlc-to-obv-diagram.json`: `Entrada -> Barras OHLC -> OBV -> Salida`

### Investigación de LLM / Analista

- `analyst-news-desk-brief-diagram.json`: `Entrada -> Resumen de la mesa de noticias -> Salida`
- `analyst-news-monitoring-points-diagram.json`: `Entrada -> Puntos de monitoreo -> Salida`
- `analyst-news-client-note-diagram.json`: `Entrada -> Nota del cliente -> Salida`

### Paquete de flujo de trabajo financiero

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `Entrada -> Preparar contexto matutino -> Pulsos de pasos financieros -> Ensamblar informe -> Reportar paquete Phema + NotebookLM -> Salida`
- `finance-watchlist-check-nombre-notebooklm-diagram.json`: `Entrada -> Preparar contexto de lista de seguimiento -> Pulsos de pasos financieros -> Ensamblar informe -> Reportar paquete Phema + NotebookLM -> Salida`
- `finance-research-roundup-notebooklm-diagram.json`: `Entrada -> Preparar contexto de investigación -> Pulsos de pasos financieros -> Ensamblar informe -> Reportar paquete Phema + NotebookLM -> Salida`

Estos tres Phemas guardados permanecen separados para su edición, pero comparten el mismo pulso de entrada de flujo de trabajo y distinguen el flujo de trabajo con el nodo `paramsText.workflow_name`.

## Suposiciones de tiempo de ejecución

Estos diagramas se guardan con direcciones locales concretas para que puedan ejecutarse sin edición adicional cuando el stack de demostración esperado esté disponible.

### Diagramas de análisis técnico

Los diagramas de indicadores asumen:

- Plaza en `http://127.0.0.1:8011`
- `YFinancePulser` en `http://127.0.0.1:8020`
- `TechnicalAnalysisPulser` en `http://127.0.0.1:8033`

Las configuraciones de pulser referenciadas por estos diagramas se encuentran en:

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### Diagramas de LLM / Analista

Los diagramas orientados a LLM asumen:

- Plaza en `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser` en `http://127.0.0.1:8270`

Ese pulser de analista con prompts depende a su vez de:

- `news-wire.pulser` en `http://127.0.0.1:8268`
- `ollama.pulser` en `http://127.0.0.1:8269`

Esos archivos de demostración se encuentran en:

- `demos/pulsers/analyst-insights/`

### Diagramas de flujo de trabajo financiero

Los diagramas de flujo de trabajo financiero asumen:

- Plaza en `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser` en `http://127.0.0.1:8271`

Ese pulser de demostración es un `FinancialBriefingPulser` propiedad de Attas, respaldado por:

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

Estos diagramas son editables tanto en MapPhemar como en las rutas integradas de Personal Agent MapPhemar porque son archivos JSON de Phema ordinarios respaldados por diagramas.

## Inicio rápido

### Opción 1: Cargar los archivos en MapPhemar

1. Abre una instancia del editor MapPhemar.
2. Carga uno de los archivos JSON de esta carpeta.
3. Confirma que el `plazaUrl` guardado y las direcciones de pulser coincidan con tu entorno local.
4. Ejecuta `Test Run` con uno de los payloads de ejemplo a continuación.

Si tus servicios utilizan puertos o nombres diferentes, edita:

- `meta.map_pers_phemar.diagram.plazaUrl`
- el `pulserName` de cada nodo
- la `pulserAddress` de cada nodo

### Opción 2: Usarlos como archivos semilla

También puedes copiar estos archivos JSON en cualquier pool de MapPhemar bajo un directorio `phemas/` y cargarlos a través de la interfaz de usuario del agente de la misma manera que lo hace la demostración de personal-research-workbench.

## Entradas de ejemplo

### Diagramas de análisis técnico

Utilice una carga útil como:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

Resultado esperado:

- el paso `OHLC Bars` obtiene una serie de barras históricas
- el nodo del indicador calcula un array de `values`
- la salida final devuelve pares de timestamp/valor

### Diagramas de LLM / Analista

Usa un payload como:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Resultado esperado:

- el analyst pulser basado en prompts obtiene noticias sin procesar
- el prompt pack convierte esas noticias en una vista de analista estructurada
- la salida devuelve campos listos para investigación como `desk_note`, `monitor_now` o `client_note`

### Diagramas de flujo de trabajo financiero

Utilice un payload como:
```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

Resultado esperado:

- el nodo de contexto del flujo de trabajo siembra el flujo de trabajo financiero elegido
- los nodos financieros intermedios construyen fuentes, citas, hechos, riesgos, catalizadores, conflictos, conclusiones, preguntas y bloques de resumen
- el nodo de ensamblaje construye una carga útil `attas.finance_briefing`
- el nodo de informe convierte esa carga útil en un Phema estático
- el nodo NotebookLM genera artefactos de exportación a partir de la misma carga útil
- la salida final combina los tres resultados para su inspección en MapPhemar o Personal Agent

## Límites actuales del editor

Estos flujos de trabajo financieros se ajustan al modelo MapPhemar actual sin añadir un nuevo tipo de nodo.

Todavía se aplican dos reglas importantes en tiempo de ejecución:

- `Input` debe conectarse exactamente a una forma descendente
- cada nodo ejecutable no ramificado debe hacer referencia a un pulse más un pulser alcanzable

Eso significa que la expansión (fan-out) del flujo de trabajo debe ocurrir después del primer nodo ejecutable, y los pasos del flujo de trabajo aún deben exponerse como pulses alojados por un pulser si desea que el diagrama se ejecute de extremo a extremo.

## Demos Relacionados

Si desea ejecutar los servicios de soporte en lugar de solo inspeccionar los diagramas:

- `demos/personal-research-annotated/README.md`: flujo de trabajo de diagrama visual con el ejemplo RSI sembrado
- `demos/pulsers/analyst-insights/README.md`: pila de noticias de analista con prompts utilizada por los diagramas orientados a LLM
- `demos/pulsers/llm/README.md`: demo de pulser `llm_chat` independiente para OpenAI y Ollama

## Verificación

Estos archivos están cubiertos por las pruebas del repositorio:
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

Ese conjunto de pruebas verifica que los diagramas guardados se ejecuten de extremo a extremo contra flujos de pulser simulados o de referencia.
