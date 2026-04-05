# Prompits Dispatcher

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

## Piezas incluidas

- `DispatcherAgent`: despachador de trabajos respaldado por cola
- `DispatcherWorkerAgent`: trabajador que consulta trabajos coincidentes e informa resultados
- `DispatcherBossAgent`: interfaz de usuario en el navegador para emitir trabajos e inspeccionar el estado de ejecución
- `JobCap`: abstracción de capacidad para manejadores de trabajos pluggable
- prácticas compartidas, esquemas, ayudantes de tiempo de ejecución y configuraciones de ejemplo

## Tablas internas

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

Si un worker devuelve filas para una `target_table` concreta y proporciona un esquema, el dispatcher también puede crear y persistir esa tabla. Si no se proporciona ningún esquema, las filas se almacenan de forma genérica en `dispatcher_job_results`.

## Prácticas

- `dispatcher-submit-job`
- `arg-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## Ejemplo de uso

Inicia el dispatcher:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

Iniciar un trabajador:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

Inicie la interfaz de usuario de boss:
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

La configuración de ejemplo del worker utiliza una capacidad de ejemplo mínima de
`prompits.dispatcher.examples.job_caps`.

## Notas

- El paquete utiliza por defecto un token directo local compartido, por lo que las llamadas a `UsePractice(...)` funcionan localmente antes de que se configure la autenticación de Plaza.
- Las configuraciones de ejemplo utilizan `PostgresPool`, pero las pruebas también cubren SQLite.
- El worker puede anunciar capacidades basadas en clases o funciones invocables a través de la sección de configuración `dispatcher.job_capabilities`.
