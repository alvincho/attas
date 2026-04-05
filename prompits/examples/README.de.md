# Prompits Beispielkonfigurationen

## Uebersetzungen

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Dateien

- `plaza.agent`: Plaza mit einem lokalen `FileSystemPool`
- `worker.agent`: ein grundlegender `StandbyAgent`, der sich automatisch bei Plaza registriert
- `user.agent`: ein `UserAgent`, der die Plaza-Browser-UI exponiert

## Ausführungsreihenfolge

Aus der Repository-Wurzel:
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Besuchen Sie dann `http://127.0.0.1:8214/`.

## Speicher

Die Beispielkonfigurationen schreiben den lokalen Zustand unter:
```text
prompits/examples/storage/
```

Dieses Verzeichnis wird automatisch von `FileSystemPool` erstellt.
