# Exemples de configurations Prompits

## Traductions

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Fichiers

- `plaza.agent`: Plaza avec un `FileSystemPool` local
- `worker.agent` : un `StandbyAgent` de base qui s'enregistre automatiquement auprès de Plaza
- `user.agent` : un `UserAgent` qui expose l'interface utilisateur du navigateur Plaza

## Ordre d'exécution

Depuis la racine du dépôt :
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Ensuite, visitez `http://127.0.0.1:8214/`.

## Stockage

Les configurations d'exemple écrivent l'état local sous :
```text
prompits/examples/storage/
```

Ce répertoire est créé automatiquement par `FileSystemPool`.
