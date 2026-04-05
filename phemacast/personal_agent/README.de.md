# Phemacast Personal Agent

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

## Dokumentation

- [Detaillierte Benutzeranleitung](./docs/user_guide.md)
- [Aktuelles Funktionsverzeichnis](./docs/current_features.md)

Das Paket behält die gleiche Local-First-Struktur bei:

- FastAPI stellt das HTML-Shell und die JSON-APIs bereit.
- React übernimmt die interaktive Client-UI.
- Der Plaza-Katalog und die Pulser-Ausführung laufen weiterhin über Backend-Proxy-Routen.
- Mock-Dashboard-Daten stehen für die frühe Produktentwicklung weiterhin zur Verfügung.
- Die aktuelle Live-Runtime wird von `static/personal_agent.jsx` bereitgestellt, sodass der Rebuild in der frühen Entwicklung sofort funktioniert, ohne auf ein Frontend-Bundle warten zu müssen.

## Paketstruktur

- `app.py`: FastAPI-Einstiegspunkt und Routen
- `data.py`: Zugriff auf Dashboard-Snapshots
- `plaza.py`: Plaza-Katalog und Pulser-Proxy-Helfer
- `templates/index.html`: HTML-Shell, die die React-App bootstrappt
- `static/`: Live-JSX-Runtime und CSS, bereitgestellt von FastAPI
- `ui/`: Zukünftiges React + TypeScript + Vite Quellcode-Gerüst
- `docs/current_features.md`: Vollständiges Feature-Inventar, erfasst aus dem Legacy-Prototyp

## Lokal ausführen

Aus der Wurzel des Repositorys:
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

Die Live-App wird direkt aus `static/personal_agent.jsx` ausgeführt.

Das Verzeichnis `ui/` ist absichtlich für eine spätere Beförderung zu einem gebündelten Build vorgesehen. Wenn Sie mit diesem Scaffold experimentieren möchten, ohne die Live-Runtime zu berühren, können Sie von innerhalb von `phemacast/personal_agent/ui` Folgendes ausführen:
```bash
npm install
npm run build
```

Dies gibt in `phemacast/personal_agent/ui/dist` aus.

Öffnen Sie dann `http://127.0.0.1:8041`.
