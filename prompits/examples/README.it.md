# Configurazioni di esempio di Prompits

## Traduzioni

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## File

- `plaza.agent`: Plaza con un `FileSystemPool` locale
- `worker.agent`: un `StandbyAgent` di base che si registra automaticamente con Plaza
- `user.agent`: un `UserAgent` che espone l'interfaccia utente del browser Plaza

## Ordine di esecuzione

Dalla radice del repository:
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Quindi visita `http://127.0.0.1:8214/`.

## Archiviazione

Le configurazioni di esempio scrivono lo stato locale in:
```text
prompits/examples/storage/
```

Quella directory viene creata automaticamente da `FileSystemPool`.
