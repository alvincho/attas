# Agente Personal de Phemacast

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

## Documentación

- [Guía detallada del usuario](./docs/user_guide.md)
- [Inventario de funciones actuales](./docs/current_features.md)

El paquete mantiene la misma estructura local-first:

- FastAPI sirve el shell HTML y las APIs JSON.
- React gestiona la interfaz de usuario interactiva del cliente.
- El catálogo de Plaza y la ejecución de Pulser siguen fluyendo a través de las rutas proxy del backend.
- Los datos simulados del dashboard siguen disponibles para el desarrollo temprano del producto.
- El tiempo de ejecución en vivo actual se sirve desde `static/personal_agent.jsx`, por lo que la reconstrucción funciona inmediatamente en el desarrollo temprano sin esperar a un bundle del frontend.

## Estructura del Paquete

- `app.py`: Punto de entrada y rutas de FastAPI
- `data.py`: Acceso a instantáneas del dashboard
- `plaza.py`: Catálogo de Plaza y ayudantes de proxy de pulser
- `templates/index.html`: Shell HTML que arranca la aplicación React
- `static/`: Runtime de JSX en vivo y CSS servidos por FastAPI
- `ui/`: Estructura de código fuente futura de React + TypeScript + Vite
- `docs/current_features.md`: Inventario completo de funciones capturado del prototipo heredado

## Ejecutar localmente

Desde la raíz del repositorio:
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

La aplicación en vivo se ejecuta directamente desde `static/personal_agent.jsx`.

El directorio `ui/` se ha preparado intencionadamente para una promoción posterior a una compilación empaquetada. Si desea experimentar con ese andamiaje sin tocar el runtime en vivo, desde `phemacast/personal_agent/ui` puede ejecutar:
```bash
npm install
npm run build
```

Eso se genera en `phemacast/personal_agent/ui/dist`.

Luego abre `http://127.0.0.1:8041`.
