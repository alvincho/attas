# Demo de YFinance Pulser

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

- `plaza.agent`: Plaza local para este demo
- `yfinance.pulser`: configuración de demo local para `YFinancePulser`
- `start-plaza.sh`: lanzar Plaza
- `start-pulser.sh`: lanzar el pulser
- `run-demo.sh`: lanzar el demo completo desde una sola terminal y abrir la guía del navegador más la interfaz de pulser

## Lanzamiento con un solo comando

Desde la raíz del repositorio:
```bash
./demos/pulsers/yfinance/run-demo.sh
```

Esto inicia Plaza y `YFinancePulser` desde una sola terminal, abre una página de guía en el navegador y abre la interfaz de usuario de pulser automáticamente.

Establece `DEMO_OPEN_BROWSER=0` si deseas que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Utilice un entorno de Python nativo de Windows. Desde la raíz del repositorio en PowerShell:
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher yfinance
```

Si las pestañas del navegador no se abren automáticamente, mantenga el lanzador ejecutándose y abra la URL `guide=` impresa en un navegador de Windows.

## Primeros pasos

Abre dos terminales desde la raíz del repositorio.

### Terminal 1: iniciar Plaza
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8251`

### Terminal 2: iniciar el pulser
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8252`
- se registra en Plaza en `http://127.0.0.1:8251`

Nota:

- este demo requiere acceso a internet saliente porque el pulser obtiene datos en vivo a través de `yfinance`
- Yahoo Finance puede limitar la tasa de transferencia o rechazar peticiones intermitentemente

## Pruébalo en el navegador

Abrir:

- `http://127.0.0.1:8252/`

Primeros pulses sugeridos:

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

Parámetros sugeridos para `last_price`:
```json
{
  "symbol": "AAPL"
}
```

Parámetros sugeridos para `ohlc_bar_series`:
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Pruébalo con Curl

Solicitud de cotización:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

Solicitud de serie OHLC:
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## Qué destacar

- el mismo pulser expone tanto pulses de estilo snapshot como de estilo time-series
- `ohlc_bar_series` es compatible con el workbench chart demo y el pulser de la ruta technical-analysis
- el live provider puede cambiar internamente más adelante mientras que el pulse contract permanece igual

## Crea el tuyo propio

Si quieres ampliar esta demo:

1. copia `yfinance.pulser`
2. ajusta los puertos y las rutas de almacenamiento
3. cambia o añade definiciones de pulse compatibles si deseas un catálogo más pequeño o especializado
