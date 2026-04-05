# Demo de Analyst Insight Pulser

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

## Qué muestra esta demo

- un pulser propiedad de un analista con múltiples pulses de información estructurada
- un segundo pulser propiedad de un analista que se basa en un agente de noticias independiente y un agente local de Ollama
- una forma limpia de separar los datos brutos de la fuente de los Prompits redactados por el analista y los resultados finales orientados al consumidor
- un recorrido por el agente personal que muestra el mismo stack desde el punto de vista de otro usuario
- los archivos exactos que un analista o PM editaría para publicar su propia visión

## Archivos en esta carpeta

- `plaza.agent`: Plaza local para la demo del pulser de analista
- `analyst-insights.pulser`: Configuración de `PathPulser` que define el catálogo público de pulses
- `analyst_insight_step.py`: Lógica de transformación compartida más el paquete de cobertura de analista predefinido
- `news-wire.pulser`: Agente de noticias upstream local que publica paquetes `news_article` predefinidos
- `news_wire_step.py`: Paquetes de noticias sin procesar predefinidos devueltos por el agente de noticias upstream
- `ollama.pulser`: Pulser `llm_chat` local basado en Ollama para la demo de prompts de analista
- `analyst-news-ollama.pulser`: Pulser de analista compuesto que obtiene noticias, aplica prompts propiedad del analista, llama a Ollama y normaliza el resultado en múltiples pulses
- `analyst_news_ollama_step.py`: El paquete de prompts del analista más la lógica de normalización JSON
- `start-plaza.sh`: Iniciar Plaza
- `start-pulser.sh`: Iniciar el pulser de analista estructurado fijo
- `start-news-pulser.sh`: Iniciar el agente de noticias upstream predefinido
- `start-ollama-pulser.sh`: Iniciar el pulser de Ollama local
- `start-analyst-news-pulser.sh`: Iniciar el pulser de analista con prompts
- `start-personal-agent.sh`: Iniciar la interfaz de usuario del agente personal para el recorrido de la vista del consumidor
- `run-demo.sh`: Iniciar la demo desde una terminal y abrir la guía del navegador más las páginas principales de la interfaz de usuario

## Lanzamiento con un solo comando

Desde la raíz del repositorio:
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

Ese wrapper inicia el flujo estructurado ligero por defecto.

Para iniciar en su lugar el flujo avanzado de noticias + Ollama + agente personal:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
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
./demos/pulsers/analyst-insights/run-demo.sh
```

Para la ruta avanzada:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

Utilice WSL2 con Ubuntu u otra distribución de Linux. Desde la raíz del repositorio dentro de WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

Para la ruta avanzada dentro de WSL:
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

Si las pestañas del navegador no se abren automáticamente desde WSL, mantén el lanzador ejecutándose y abre la URL `guide=` impresa en un navegador de Windows.

Los wrappers nativos de PowerShell / Command Prompt aún no se han incluido, por lo que hoy en día la ruta de Windows compatible es WSL2.

## Demo 1: Vistas estructuradas de analistas

Esta es la ruta solo local, sin LLM.

Abre dos terminales desde la raíz del repositorio.

### Terminal 1: iniciar Plaza
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8266`

### Terminal 2: iniciar el pulser
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8267`
- se registra en el Plaza en `http://127.0.0.1:8266`

## Pruébalo en el navegador

Abre:

- `http://127.0.0.1:8267/`

Luego prueba estos pulses con `NVDA`:

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

Parámetros sugeridos para los cuatro:
```json
{
  "symbol": "NVDA"
}
```

Lo que debería ver:

- `rating_summary` devuelve la conclusión principal, el objetivo, la confianza y un breve resumen
- `thesis_bullets` devuelve la tesis positiva en formato de lista
- `risk_watch` devuelve los principales riesgos más qué monitorear
- `scenario_grid` devuelve los casos alcista, base y bajista en un único payload estructurado

## Pruébelo con Curl

Calificación del titular:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

Puntos clave de la tesis:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

Vigilancia de riesgos:
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## Cómo personaliza un analista esta demostración

Hay dos puntos de edición principales.

### 1. Cambiar la vista de investigación real

Editar:

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

Este archivo contiene el paquete `ANALYST_COVERAGE` inicializado. Ahí es donde cambias:

- símbolos cubiertos
- nombre del analista
- etiquetas de calificación
- precios objetivo
- puntos de la tesis
- riesgos clave
- escenarios alcista/base/bajista

### 2. Cambiar el catálogo público de pulses

Editar:

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

Ese archivo controla:

- qué pulses existen
- el nombre y la descripción de cada pulse
- los esquemas de entrada y salida
- etiquetas y direcciones

Si desea agregar un nuevo pulse de insights, copie una de las entradas existentes y apúntela a un nuevo `insight_view`.

## Por qué este patrón es útil

- las herramientas de cartera pueden solicitar solo el `rating_summary`
- los constructores de informes pueden solicitar `thesis_bullets`
- los paneles de riesgo pueden solicitar `risk_watch`
- las herramientas de valoración pueden solicitar `scenario_grid`

Eso significa que el analista publica un solo servicio, pero diferentes consumidores pueden extraer exactamente la parte que necesitan.

## Qué hacer a continuación

Una vez que esta forma de pulser local tenga sentido, los siguientes pasos son:

1. añadir más símbolos cubiertos al paquete de cobertura de analistas
2. añadir pasos de origen antes del paso final de Python si desea combinar su propia visión con las salidas de YFinance, ADS o LLM
3. exponer el pulser a través de un Plaza compartido en lugar de solo el Plaza de demo local

## Demo 2: Analyst Prompt Pack + Ollama + Agente Personal

Este segundo flujo muestra una configuración de analista más realista:

- un agente publica datos brutos de `news_article`
- un segundo agente expone `llm_chat` a través de Ollama
- el pulser propiedad del analista utiliza su propio prompt pack para transformar esas noticias sin procesar en múltiples pulses reutilizables
- el agente personal consume los pulses terminados desde el punto de vista de un usuario diferente

### Requisitos previos para el flujo de prompts

Asegúrate de que Ollama se esté ejecutando localmente y que el modelo exista:

```bash
ollama serve
ollama pull qwen3:8b
```

Luego, abre cinco terminales desde la raíz del repositorio.

### Terminal 1: iniciar Plaza

Si el Demo 1 aún se está ejecutando, sigue usando el mismo Plaza.
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8266`

### Terminal 2: iniciar el agente de noticias upstream
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

Resultado esperado:

- el news pulser se inicia en `http://127.0.0.1:8268`
- se registra en el Plaza en `http://127.0.0.1:8266`

### Terminal 3: iniciar el pulser de Ollama
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

Resultado esperado:

- el pulser de Ollama se inicia en `http://127.0.0.1:8269`
- se registra en Plaza en `http://127.0.0.1:8266`

### Terminal 4: iniciar el pulser de prompted analyst

Inicie esto después de que los agentes de noticias y Ollama ya estén en ejecución, porque el pulser valida sus cadenas de muestra durante el inicio.
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

Resultado esperado:

- el pulser del analista solicitado se inicia en `http://127.0.0.1:8270`
- se registra en Plaza en `http://127.0.0.1:8266`

### Terminal 5: iniciar agente personal
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

Resultado esperado:

- el agente personal se inicia en `http://127.0.0.1:8061`

### Prueba directamente el Prompted Analyst Pulser

Abre:

- `http://127.0.0.1:8270/`

Luego prueba estos pulses con `NVDA`:

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

Parámetros sugeridos:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Lo que debería ver:

- `news_desk_brief` convierte los artículos upstream en una postura estilo PM y una nota corta
- `news_monitoring_points` convierte los mismos artículos brutos en elementos de seguimiento y banderas de riesgo
- `news_client_note` convierte los mismos artículos brutos en una nota más limpia orientada al cliente

El punto importante es que el analista controla los Prompits en un solo archivo, mientras que los usuarios downstream solo ven interfaces de pulse estables.

### Usar el Agente Personal desde la Vista de Otro Usuario

Abrir:

- `http://127.0.0.1:8061/`

Luego siga esta ruta:

1. Abra `Settings`.
2. Vaya a la pestaña `Connection`.
3. Establezca la URL de Plaza en `http://127.0.0.1:8266`.
4. Haga clic en `Refresh Plaza Catalog`.
5. Cree una `New Browser Window`.
6. Ponga la ventana del navegador en modo `edit`.
7. Agregue un primer pane plain y apúntelo a `DemoAnalystNewsWirePulser -> news_article`.
8. Use pane params:
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. Haga clic en `Get Data` para que el usuario pueda ver los artículos originales.
10. Añada un segundo panel simple y apúntelo a `DemoAnalystPromptedNewsPulser -> news_desk_brief`.
11. Reutilice los mismos parámetros y haga clic en `Get Data`.
12. Añada un tercer panel con `news_monitoring_points` o `news_client_note`.

Lo que debería ver:

- un panel muestra las noticias originales de upstream de otro agente
- el siguiente panel muestra la vista procesada del analista
- el tercer panel muestra cómo el mismo paquete de prompts del analista puede publicar una superficie diferente para una audiencia diferente

Esa es la historia clave del consumidor: otro usuario no necesita conocer la cadena interna. Simplemente navega por Plaza, elige un pulse y consume el resultado final del analista.

## Cómo personaliza un analista el flujo de prompts

Hay tres puntos de edición principales en el Demo 2.

### 1. Cambiar el paquete de noticias upstream

Editar:

- `demos/pulsers/analyst-insights/news_wire_step.py`

Ahí es donde cambia los artículos semilla que publica el agente de la fuente upstream.

### 2. Cambiar los propios prompts del analista

Editar:

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

Ese archivo contiene el paquete de prompts propiedad del analista, que incluye:

- nombres de perfiles de prompt
- audiencia y objetivo
- tono y estilo de escritura
- contrato de salida JSON requerido

Esa es la forma más rápida de hacer que la misma noticia bruta produzca una voz de investigación diferente.

### 3. Cambiar el catálogo público de pulses

Editar:

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

Ese archivo controla:

- qué prompted pulses existen
- qué perfil de prompt utiliza cada pulse
- qué agentes upstream llama
- los esquemas de entrada y salida que se muestran a los usuarios downstream

## Por qué el patrón avanzado es útil

- el agente de noticias upstream puede sustituirse más adelante por YFinance, ADS o un colector interno
- el analista mantiene la propiedad del pack de prompts en lugar de codificar notas únicas en una interfaz de usuario
- diferentes consumidores pueden utilizar diferentes pulses sin conocer la cadena completa que hay detrás
- el agente personal se convierte en una superficie de consumo limpia en lugar del lugar donde reside la lógica
