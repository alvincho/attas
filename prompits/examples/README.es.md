# Configuraciones de ejemplo de Prompits

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

## Archivos

- `plaza.agent`: Plaza con un `FileSystemPool` local
- `worker.agent`: un `StandbyAgent` básico que se registra automáticamente con Plaza
- `user.agent`: un `UserAgent` que expone la interfaz de usuario del navegador Plaza

## Orden de ejecución

Desde la raíz del repositorio:
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Luego visita `http://127.0.0.1:8214/`.

## Almacenamiento

Las configuraciones de ejemplo escriben el estado local en:
```text
prompits/examples/storage/
```

Ese directorio se crea automáticamente mediante `FileSystemPool`.
