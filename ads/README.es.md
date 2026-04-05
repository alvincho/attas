# Attas Data Services

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

## Cobertura

Las tablas actuales del conjunto de datos normalizado son:

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data_collected`

El dispatcher también gestiona:

- `ads_jobs`
- `ads_worker_capabilities`

La implementación utiliza prefijos de tabla `ads_` en lugar de nombres literales `ads-*`, por lo que los mismos identificadores funcionan correctamente en SQLite, Postgres y SQL respaldado por Supabase.

## Forma de ejecución

Dispatcher:

- es un agente `prompits`
- posee la cola compartida y las tablas de almacenamiento normalizadas
- expone `ads-submit-job`, `ads-get-job`, `ads-register-worker` y `ads-post-job-result`
- entrega a los workers una carga útil `JobDetail` tipada cuando reclaman trabajo
- acepta una carga útil `JobResult` tipada para finalizar trabajos y persistir las filas recolectadas más las cargas útiles originales

Worker:

- es un agente `prompits`
- anuncia sus capacidades a través de los metadatos del agente y la tabla de capacidades del dispatcher
- carga `job_capabilities` desde la configuración y registra esos nombres de capacidad en los metadatos de Plaza
- utiliza objetos `JobCap` como la ruta de ejecución predeterminada para los trabajos reclamados
- puede ejecutarse una vez o en un bucle de sondeo, con un intervalo predeterminado de 10 segundos
- acepta un `process_job()` sobrescrito o un callback de manejador externo

Pulser:

- es un pulser de `phemacast`
- lee tablas ADS normalizadas desde el pool compartido
- expone pulsos para security master, precios diarios, fundamentales, estados financieros, noticias y búsqueda de carga útil original

## Archivos

- `ads/agents.py`: agentes de despacho y trabajadores
- `ads/jobcap.py`: abstracción `JobCap` y cargador de capacidades basado en callables
- `ads/models.py`: `JobDetail` y `JobResult`
- `cd/pulser.py`: implementación de ADS pulser
- `ads/boss.py`: agente de interfaz de usuario boss operator
- `ads/practices.py`: prácticas de despacho
- `ads/schema.py`: esquemas de tablas compartidos
- `ads/iex.py`: capacidad de trabajo de fin de día de IEX
- `ads/twse.py`: capacidad de trabajo de fin de día de la Bolsa de Valores de Taiwán
- `ads/rss_news.py`: capacidad de recolección de noticias RSS de múltiples fuentes
- `ads/sec.py`: capacidades de importación masiva de datos brutos de SEC EDGAR y mapeo por empresa
- `ads/us_listed.py`: capacidad de maestro de valores listados en EE. UU. de Nasdaq Trader
- `ads/yfinance.py`: capacidad de trabajo de fin de día de Yahoo Finance
- `ads/runtime.py`: ayudantes de normalización
- `ads/configs/*.agent`: ejemplos de configuraciones de ADS
- `ads/sql/ads_tables.sql`: DDL de Postgres/Supabase

## Ejemplos locales

Las configuraciones de ADS incluidas ahora asumen una base de datos PostgreSQL compartida. Establezca
`POSTGRES_DSN` o `DATABASE_URL` antes de iniciar los agentes. Opcionalmente, puede
establecer `ADS_POSTGRES_SCHEMA` para usar un esquema distinto de `public`, y
`ADS_POSTGRES_SSLMODE` para sobrescribir el comportamiento predeterminado `disable` (compatible con entornos locales)
cuando necesite SSL para PostgreSQL gestionado.

Inicie el dispatcher:
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

Iniciar un worker:
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

La configuración de ejemplo del worker incluye una capacidad en vivo de `US Listed Sec to security master` respaldada por `ads.us_listed:USListedSecJobCap`, manejadores simulados para `fundamentals`, `financial_statements` y `news`, y utiliza `ads.sec:USFilingBulkJobCap` llamado `US Filing Bulk`, `ads.sec:USFilingMappingJob	JobCap` llamado `US Filing Mapping`, `ads.yfinance:YFinanceEODJobCap` llamado `YFinance EOD`, `ads.yfinance:YFinanceUSMarketEODJobCap` llamado `YFinance US Market EOD`, además de `ads.twse:TWSEMarketEODJobCap` llamado `TWSE Market EOD` para la recolección diaria de cierre, y `ads.rss_news:RSSNewsJobCap` llamado `RSS News` para la recolección de noticias de múltiples fuentes. `YFinance EOD` utiliza el módulo `yfinance` instalado y no requiere una clave API separada. `YFinance US Market EOD` escanea `ads_security_master` en busca de símbolos `USD` activos, los ordena por `metadata.yfinance.eod_at`, actualiza ese timestamp símbolo por símbolo, y encola trabajos de `YFinance EOD` de un solo símbolo para que los nombres más desactualizados se refresquen primero. `TWSE Market EOD` lee el informe diario de cotizaciones `MI_INDEX` oficial de la TWSE y almacena la tabla de cotizaciones de todo el mercado en filas normalizadas de `ads_daily_price`. Cuando `ads_daily_price` está vacío, realiza un arranque en frío de una ventana reciente corta por defecto en lugar de intentar un rellenado de todo el mercado de varios años; use un `start_date` explícito si desea cobertura histórica de TWSE. `USListedSecJobCap` lee los archivos de directorio de símbolos de Nasdaq Trader `nasdaqlisted.txt` y `otherlisted.txt`, prefiere las copias alojadas en la web `https://www.nasdaqtrader.com/dynamic/SymDir/` con respaldo FTP, filtra los símbolos de prueba y actualiza el universo actual de listados en EE. UU. en `ads_security_master`. `RSS News` extrae los feeds configurados de SEC, CFTC y BLS en un solo trabajo y almacena las entradas de feeds normalizadas en `ads_news`. `US Filing Bulk` descarga el EDGAR de la SEC cada noche
los archivos `companyfacts.zip` y `submissions.zip`, escribe las filas JSON sin procesar por empresa en `ads_sec_companyfacts` y `ads_sec_submissions`, y envía un encabezado `User-Agent` de la SEC declarado. `US Filing Mapping` lee una empresa de esas tablas SEC sin procesar y la mapea en `ads_fundamentals` más `ads_financial_statements` cuando un símbolo está disponible en los metadatos de submissions.
Inicia el pulser:
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

Inicie la interfaz de usuario de boss:
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

La interfaz de usuario de boss ahora incluye una barra de conexión en vivo de Plaza en la parte superior de la página,
una página de `Issue Job`, una vista `/monitor` para navegar por los trabajos de ADS en cola, reclamados,
completados y fallidos, además de sus registros de carga útil sin procesar, y una
página de `Settings` para los valores predeterminados del despachador del lado de boss y las preferencias de actualización del monitor.

## Notas
- Las configuraciones de ejemplo incluidas utilizan `PostgresPool`, por lo que el dispatcher, los workers, el pulser y el boss apuntan a la misma base de datos ADS en lugar de archivos SQLite por agente.
- `PostgresPool` resuelve la configuración de conexión a partir de `POSTGRES_DSN`, `DATABASE_URL`, `SUPABASE_DB_URL` o las variables de entorno estándar de libpq `PG*`.
- `ads/configs/boss.agent`, `ads/configs/dispatcher.agent` y `ads/configs/worker.agent` deben mantenerse alineados cuando se introduzcan nuevos JobCaps; las configuraciones incluidas exponen `US Listed Sec to security master`, `US Filing Bulk`, `US Filing Mapping`, `YFinance EOD`, `YFinance US Market EOD`, `TWSE Market EOD` y `RSS News`.
- Las configuraciones de los workers pueden declarar entradas de `ads.job_capabilities` con un nombre de capacidad y una ruta ejecutable como `ads.examples.job_caps:mock_daily_price_cap`.
- Las configuraciones de los workers también pueden declarar capacidades basadas en clases con `type`, por ejemplo `ads.iex:IEXEODJobCap`, `ads.rss_news:RSSNewsJobCap`, `ads.sec:USFilingBulkJobCap`, `ads.sec:USFilingMappingJobCap`, `ads.twse:TWSEMarketEODJobCap`, `ads.us_listed:USListedSecJobCap` o `ads.yfinance:YFinanceEODJobCap`, que devuelven filas normalizadas más payloads brutos para la persistencia del dispatcher.
- Las entradas de `ads.job_capabilities` del worker admiten `disabled: true` para desactivar temporalmente un job cap configurado sin eliminar su entrada de configuración.
- Las configuraciones de los workers pueden establecer `ads.yfinance_request_cooldown_sec` (predeterminado `120`) para que un worker deje de anunciar temporalmente las capacidades relacionadas con YFinance tras una respuesta de límite de velocidad de Yahoo.
- `ads/sql/ads_tables.sql` se incluye para despliegues en Postgres o Supabase.
- El dispatcher y el worker utilizan por defecto un token directo local compartido, por lo que las llamadas remotas a `UsePractice(...)` funcionan en una sola máquina incluso antes de que se configure la autenticación de Plaza.
- Los tres componentes se ajustan a las convenciones existentes del repositorio, por lo que aún pueden participar en el registro de Plaza y en las llamadas remotas a `UsePractice(...)` cuando se configuren para ello.
