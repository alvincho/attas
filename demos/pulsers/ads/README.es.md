# Demo de ADS Pulser

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

## Qué cubre esta demostración

- cómo `ADSPulser` se asienta sobre tablas ADS normalizadas
- cómo la actividad del dispatcher y del worker se convierte en datos visibles para el pulser
- cómo sus propios collectors pueden depositar datos en las tablas ADS y aparecer a través de los pulses existentes

## Configuración

Siga la guía de inicio rápido en:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

O utilice el envoltorio de un solo comando centrado en pulser desde la raíz del repositorio:
```bash
./demos/pulsers/ads/run-demo.sh
```

Ese wrapper lanza la misma pila SQLite ADS que `data-pipeline`, pero abre una guía en el navegador y pestañas que se centran en el recorrido pulser-first.

Eso inicia:

1. el ADS dispatcher
2. el ADS worker
3. el ADS pulser
4. la boss UI

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Utilice WSL2 con Ubuntu u otra distribución de Linux. Desde la raíz del repositorio dentro de WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

Si las pestañas del navegador no se abren automáticamente desde WSL, mantén el lanzador ejecutándose y abre la URL `guide=` impresa en un navegador de Windows.

Los wrappers nativos de PowerShell / Command Prompt aún no se han incluido, por lo que hoy en día la ruta de Windows compatible es WSL2.

## Primeras comprobaciones de Pulser

Una vez que terminen los trabajos de muestra, abre:

- `http://127.0.0.1:9062/`

Luego prueba:

1. `security_master_lookup` con `{"symbol":"AAPL","limit":1}`
2. `daily_price_history` con `{"symbol":"AAPL","limit":5}`
3. `company_profile` con `{"symbol":"AAPL"}`
4. `news_article` con `{"symbol":"AAPL","number_of_articles":3}`

## Por qué ADS es diferente

Los otros demos de pulser generalmente leen directamente de un proveedor en vivo o de un backend de almacenamiento local.

`ADSPulser`, en cambio, lee de las tablas normalizadas escritas por el pipeline de ADS:

- los workers recopilan o transforman los datos de origen
- el dispatcher persiste las filas normalizadas
- `ADSPulser` expone esas filas como pulses consultables

Esto lo convierte en la demo ideal para explicar cómo añadir tus propios adaptadores de origen.

## Añade tu propia fuente

El tutorial detallado se encuentra en:

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Utiliza los ejemplos personalizados aquí:

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

Esos ejemplos muestran cómo un colector definido por el usuario puede escribir en:

- `ads_news`, que estará disponible a través de `news_article`
- `ads_daily_price`, que estará disponible a través de `daily_price_history`
