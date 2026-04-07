# Pipeline de datos

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

- una cola de despacho para trabajos de recolección de datos
- un worker que realiza polling para capacidades coincidentes
- tablas ADS normalizadas almacenadas localmente en SQLite
- una interfaz boss para emitir y monitorear trabajos
- un pulser que vuelve a exponer los datos recolectados
- una ruta para intercambiar los live collectors incluidos por sus propios adaptadores de fuente

## Por qué este demo utiliza SQLite con colectores en vivo

Las configuraciones de ADS de estilo producción en `ads/configs/` están orientadas a un despliegue compartido de PostgreSQL.

Este demo mantiene los colectores en vivo pero simplifica el lado del almacenamiento:

- SQLite mantiene la configuración local y simple
- el worker y el dispatcher comparten un único archivo de base de datos ADS local, lo que mantiene la etapa masiva de SEC en vivo compatible con el mismo almacén del demo que lee el pulser
- la misma arquitectura sigue siendo visible, para que los desarrolladores puedan pasar a las configurando de producción más adelante
- algunos trabajos llaman a fuentes de internet públicas, por lo que los tiempos de la primera ejecución dependen de las condiciones de la red y la capacidad de respuesta de la fuente

## Archivos en esta carpeta

- `dispatcher.agent`: Configuración del dispatcher de ADS con respaldo en SQLite
- `worker.agent`: Configuración del worker de ADS con respaldo en SQLite
- `pulser.agent`: ADS pulser que lee el almacén de datos de la demo
- `boss.agent`: Configuración de la interfaz de usuario de boss para emitir trabajos
- `start-dispatcher.sh`: Iniciar el dispatcher
- `start-worker.sh`: Iniciar el worker
- `start-pulser.sh`: Iniciar el pulser
- `start-boss.sh`: Iniciar la interfaz de usuario de boss

Los adaptadores de fuentes de ejemplo relacionados y los ayudantes de live-demo se encuentran en:

- `ads/examples/custom_sources.py`: límites de trabajos de ejemplo importables para feeds de noticias y precios definidos por el usuario
- `ads/examples/live_data_pipeline.py`: wrappers orientados a demos alrededor del pipeline de ADS de la SEC en vivo

Todo el estado de ejecución se escribe en `demos/data-pipeline/storage/`.

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
./demos/data-pipeline/run-demo.sh
```

Esto inicia el dispatcher, worker, pulser y la interfaz de usuario de boss desde una sola terminal, abre una página de guía en el navegador y abre automáticamente las interfaces de usuario de boss plus pulser.

Establezca `DEMO_OPEN_BROWSER=0` si desea que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows. Desde la raíz del repositorio en PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher data-pipeline
```

Si las pestañas del navegador no se abren automáticamente, mantenga el lanzador ejecutándose y abra la URL `guide=` impresa en un navegador de Windows.

## Primeros pasos

Abre cuatro terminales desde la raíz del repositorio.

### Terminal 1: iniciar el dispatcher
```bash
./demos/data-pipeline/start-dispatcher.sh
```

Resultado esperado:

- dispatcher se inicia en `http://127.0.0.1:9060`

### Terminal 2: iniciar el worker
```bash
./demos/data-pipeline/start-worker.sh
```

Resultado esperado:

- el worker se inicia en `127.0.0.1:9061`
- consulta el dispatcher cada dos segundos

### Terminal 3: iniciar el pulser
```bash
./demos/data-pipeline/start-pulser.sh
```

Resultado esperado:

- ADS pulser se inicia en `http://127.0.0.1:9062`

### Terminal 4: iniciar la interfaz de boss
```bash
./demos/data-pipeline/start-boss.sh
```

Resultado esperado:

- la UI de boss se inicia en `http://127.0.0.1:9063`

## Guía de la primera ejecución

Abra:

- `http://127.0.0.1:9063/`

En la interfaz de boss UI, envíe estos trabajos en orden:

1. `security_master`
   Esto actualiza el universo completo de empresas que cotizan en EE. UU. desde Nasdaq Trader, por lo que no necesita una carga útil de símbolo.
2. `daily_price`
   Use la carga útil predeterminada para `AAPL`.
3. `fundamentals`
   Use la carga útil predeterminada para `AAPL`.
4. `financial_statements`
   Use la carga útil predeterminada para `AAPL`.
5. `news`
   Use la lista predeterminada de feeds RSS de SEC, CFTC y BLS.

Use las plantillas de carga útil predeterminadas cuando aparezcan. `security_master`, `daily_</sub>price` y `news` suelen terminar rápidamente. La primera ejecución de `fundamentals` o `financial_statements` respaldada por la SEC puede tardar más porque actualiza los archivos de la SEC en caché bajo `demos/data-pipeline/storage/sec_edgar/` antes de mapear la empresa solicitada.

Luego abra:

- `http://127.0.0.1:9062/`

Este es el ADS pulser para el mismo almacén de datos de demostración. Expone las tablas ADS normalizadas como pulses, lo que constituye el puente desde la recolección/orquestación hacia el consumo downstream.

Verificaciones sugeridas del primer pulser:

1. Ejecute `security_master_lookup` con `{"symbol":"AAPL","limit":1}`
2. Ejecute `daily_price_history` con `{"symbol":"AAPL","limit":5}`
3. Ejecute `company_profile` con `{"symbol":"AAPL"}`
4. Ejecute `financial_statements` con `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`
5. Ejecute `news_article` con `{"number_of_articles":3}`

Esto le da a las personas el ciclo completo de ADS: la interfaz de boss UI emite trabajos, el worker recolecta filas, SQLite almacena datos normalizados y `ADSPulser` expone el resultado a través de pulses consultables.

## Añade tu propia fuente de datos a ADSPulser

El modelo mental importante es:

- tu fuente se conecta al worker como una `job_capability`
- el worker escribe filas normalizadas en las tablas de ADS
- `ADSPulser` lee esas tablas y las expone a través de pulses

Si tu fuente se ajusta a una de las formas de tabla de ADS existentes, normalmente no necesitas cambiar `ADSPulser` en absoluto.

### El camino más fácil: escribir en una tabla de ADS existente

Utiliza una de estas combinaciones de tabla a pulse:

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### Ejemplo: añadir un feed de comunicados de prensa personalizado

El repositorio ahora incluye un ejemplo ejecutable aquí:

- `ads/examples/custom_sources.py`

Para conectarlo al worker de demostración, añade un nombre de capacidad y un job cap basado en un ejecutable en `demos/data-pipeline/worker.agent`.

Añade este nombre de capacidad:
```json
"press_release_feed"
```

Añada esta entrada de job-capability:
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

Luego, reinicie el worker y envíe un trabajo desde la interfaz de boss con un payload como:
```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

Una vez finalizado ese trabajo, abra la interfaz de usuario de Pulser en `http://127.0.0.1:9062/` y ejecute:
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

contra el pulse `news_article`.

Lo que debería ver:

- el colector definido por el usuario escribe una fila normalizada en `ads_news`
- la entrada sin procesar aún se conserva en el payload raw del trabajo
- `ADSPulser` devuelve el nuevo artículo a través del pulse `news_article` existente

### Segundo ejemplo: añadir un feed de precios personalizado

Si su fuente está más cerca de los precios que de las noticias, el mismo patrón funciona con:
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

Ese ejemplo escribe filas en `ads_daily_price`, lo que significa que el resultado se puede consultar a través de `daily_price_history` de inmediato.

### Cuándo debería cambiar el propio ADSPulser

Cambie `ads/pulser.py` solo cuando su fuente no se mapee claramente en una de las tablas ADS normalizadas existentes o cuando necesite una forma de pulso (pulse shape) completamente nueva.

En ese caso, el camino habitual es:

1. añadir o elegir una tabla de almacenamiento para las nuevas filas normalizadas
2. añadir una nueva entrada de pulso compatible en la configuración del pulser
3. extender `ADSPulence.fetch_pulse_payload()` para que el pulso sepa cómo leer y dar forma a las filas almacenadas

Si aún está diseñando el esquema, comience almacenando el payload sin procesar e inspecciónelo a través de `raw_collection_payload` primero. Eso mantiene la integración de la fuente en movimiento mientras decide cómo debería ser la tabla normalizada final.

## Qué destacar en una llamada de demo

- Los trabajos se encolan y completan de forma asíncrona.
- El worker está desacoplado de la interfaz de usuario de Boss.
- Las filas almacenadas se depositan en tablas ADS normalizadas en lugar de un único almacén de blobs genérico.
- El pulser es una segunda capa de interfaz sobre los datos recopilados.
- Incorporar una nueva fuente suele significar añadir un límite de trabajo de worker, no reconstruir todo el stack de ADS.

## Crea tu propia instancia

Hay dos rutas de actualización naturales a partir de esta demo.

### Mantén la arquitectura local pero sustituye tus propios colectores

Edita `worker.agent` y reemplaza los job caps de la demo en vivo incluidos con tus propios job caps u otros tipos de ADS job-cap.

Por ejemplo:

- `ads.examples.custom_sources:demo_press_release_cap` muestra cómo integrar un feed de artículos personalizado en `ads_news`
- `ads.essentials.custom_sources:demo_alt_price_cap` muestra cómo integrar una fuente de precios personalizada en `ads_daily_price`
- las configuraciones de producción en `ads/configs/worker.agent` muestran cómo se conectan las capacidades en vivo para SEC, YFinance, TWSE y RSS

### Pasa de SQLite a PostgreSQL compartido

Una vez que la demo local demuestre el flujo de trabajo, compara estas configuraciones de la demo con las configuraciones de estilo de producción en:

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

La principal diferencia es la definición del pool:

- esta demo utiliza `SQLitePool`
- las configuraciones de estilo de producción utilizan `PostgresPool`

## Resolución de problemas

### Los trabajos permanecen en cola

Comprueba estas tres cosas:

- la terminal del despachador sigue en ejecución
- la terminal del trabajador aún se está ejecutando
- el nombre de la capacidad del trabajo en la interfaz de Boss coincide con uno anunciado por el worker

### La interfaz de Boss se carga pero se ve vacía

Asegúrate de que la configuración de boss todavía apunte a:

- `dispatcher_address = http://127.0.0.1:9060`

### Desea una ejecución limpia o necesita eliminar las filas de simulación antiguas

Detén los procesos de demostración y elimina `demos/data-pipeline/storage/` antes de volver a empezar.

## Detener la Demo

Presiona `Ctrl-C` en cada ventana de la terminal.
