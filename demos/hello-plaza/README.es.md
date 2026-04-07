# Hello Plaza

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

- un registro de Plaza ejecutándose localmente
- un agente registrándose automáticamente en Plaza
- una interfaz de usuario orientada al navegador conectada a ese Plaza
- un conjunto de configuración mínimo que los desarrolladores pueden copiar en su propio proyecto

## Archivos en esta carpeta

- `plaza.agent`: configuración de ejemplo de Plaza
- `worker.agent`: configuración de ejemplo de worker
- `user.agent`: configuración de ejemplo de user-agent
- `start-plaza.sh`: iniciar Plaza
- `start-worker.sh`: iniciar el worker
- `start-user.sh`: iniciar el user agent orientado al navegador

Todo el estado de ejecución se escribe en `demos/hello-plaza/storage/`.

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
./demos/hello-plaza/run-demo.sh
```

Esto inicia Plaza, el worker y la interfaz de usuario desde una sola terminal, abre una página de guía en el navegador y abre la interfaz de usuario automáticamente.

Establezca `DEMO_OPEN_BROWSER=0` si desea que el lanzador permanezca solo en la terminal.

## Inicio rápido de la plataforma

### macOS y Linux

Desde la raíz del repositorio:
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

Si las pestañas del navegador no se abren automáticamente, mantén el lanzador ejecutándose y abre la URL `guide=` impresa en un navegador de Windows.

## Primeros pasos

Abre tres terminales desde la raíz del repositorio.

### Terminal 1: iniciar Plaza
```bash
./demos/hello-plaza/start-plaza.sh
```

Resultado esperado:

- Plaza se inicia en `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` devuelve un estado saludable

### Terminal 2: iniciar el worker
```bash
./demos/hello-plaza/start-worker.sh
```

Resultado esperado:

- el worker se inicia en `127.0.0.1:8212`
- it se registra automáticamente con Plaza desde Terminal 1

### Terminal 3: iniciar la interfaz de usuario

```bash
./demos/hello-plaza/start-user.sh
```

Resultado esperado:

- el agente de usuario orientado al navegador se inicia en `http://127.0.0.1:8214/`

## Verificar el stack

En una cuarta terminal, o después de que los servicios estén activos:
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

Lo que deberías ver:

- el primer comando devuelve una respuesta saludable de Plaza
- el segundo comando muestra el Plaza local y el `demo-worker` registrado

Luego abre:

- `http://127.0.0.1:8214/`

Esta es la URL de la demo pública para compartir en un recorrido local o una grabación de pantalla.

## Qué destacar en una llamada de demostración

- Plaza es la capa de descubrimiento.
- El worker puede iniciarse de forma independiente y aun así aparecer en el directorio compartido.
- La interfaz de usuario orientada al usuario no necesita conocimiento predefinido del worker. Lo descubre a través de Plaza.

## Crea tu propia instancia

La forma más sencilla de convertir esto en tu propia instancia es:

1. Copia `plaza.agent`, `worker.agent` y `user.agent` a una nueva carpeta.
2. Renombra los agentes.
3. Cambia los puertos si es necesario.
4. Apunta cada `root_path` a tu propia ubicación de almacenamiento.
5. Si cambias la URL o el puerto de Plaza, actualiza `plaza_url` en `worker.agent` y `user.agent`.

Los tres campos más importantes para personalizar son:

- `name`: lo que el agente anuncia como su identidad
- `port`: dónde escucha el servicio HTTP
- `root_path`: dónde se almacena el estado local

Una vez que los archivos se vean correctos, ejecuta:
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## Resolución de problemas

### El puerto ya está en uso

Edite el archivo `.agent` correspondiente y elija un puerto libre. Si mueve Plaza a un nuevo puerto, actualice el `plaza_url` en ambas configuraciones dependientes.

### La interfaz de usuario muestra un directorio de Plaza vacío

Verifique estas tres cosas:

- Plaza se está ejecutando en `http://127.0.0.1:8211`
- la terminal del worker todavía se está ejecutando
- `worker.agent` todavía apunta a `http://127.0.0.1:8211`

### Desea un estado de demo limpio

El reinicio más seguro es apuntar los valores de `root_path` a un nuevo nombre de carpeta en lugar de eliminar los datos existentes.

## Detener la Demo

Presiona `Ctrl-C` en cada ventana de la terminal.
