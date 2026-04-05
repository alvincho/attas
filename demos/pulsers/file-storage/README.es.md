# Demo de System Pulser

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

- `plaza.agent`: Plaza local para esta demo de pulser
- `file-storage.pulser`: pulser de almacenamiento respaldado por el sistema de archivos local
- `start-plaza.sh`: iniciar Plaza
- `start-pulser.sh`: iniciar el pulser
- `run-demo.sh`: inicia la demo completa desde una terminal y abre la guía del navegador más la interfaz de pulser UI

## Lanzamiento con un solo comando

Desde la raíz del repositorio:
```bash
./demos/pulsers/file-storage/run-demo.sh
```

Esto inicia Plaza y `SystemPulser` desde una sola terminal, abre una página de guía en el navegador y abre la interfaz de usuario de pulser automáticamente.

Establece `DEMO_OPEN_BROWSER=0` si quieres que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Utilice WSL2 con Ubuntu u otra distribución de Linux. Desde la raíz del repositorio dentro de WSL:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

Si las pestañas del navegador no se abren automáticamente desde WSL, mantén el lanzador ejecutándose y abre la URL `guide=` impresa en un navegador de Windows.

Los wrappers nativos de PowerShell / Command Prompt aún no se han incluido, por lo que hoy en día la ruta de Windows compatible es WSL2.

## Primeros pasos

Abre dos terminales desde la raíz del repositorio.

### Terminal 1: iniciar Plaza
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8256`

### Terminal 2: iniciar el pulser
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

Resultado esperado:

- el pulser se inicia en `http://127.0.0.1:8257`
- se registra en Plaza en `http://127.0.0.1:8256`

## Pruébalo en el navegador

Abre:

- `http://127.0.0.1:8257/`

Luego prueba estos pulses en orden:

1. `bucket_create`
2. `import_save`
3. `object_load`
4. `list_bucket`

Parámetros sugeridos para `bucket_create`:
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

Parámetros sugeridos para `object_save`:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

Parámetros sugeridos para `object_load`:
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Pruébelo con Curl

Cree un bucket:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

Guardar un objeto:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

Volver a cargarlo:
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## Qué destacar

- este pulser es totalmente local y no necesita credenciales en la nube
- los payloads son lo suficientemente simples como para entenderse sin herramientas adicionales
- el backend de almacenamiento puede cambiarse posteriormente de sistema de archivos a otro proveedor manteniendo estable la interfaz de pulse

## Crea el tuyo propio

Si quieres personalizarlo:

1. copia `file-storage.pulser`
2. cambia los puertos y el `root_path` de almacenamiento
3. mantén la misma pulse surface si deseas compatibilidad con el workbench y los ejemplos existentes
