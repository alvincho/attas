# Agente Personale Phemacast

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

## Documentazione

- [Guida dettagliata all'utente](./docs/user_guide.md)
- [Inventario delle funzionalità attuali](./docs/current_features.md)

Il pacchetto mantiene la stessa struttura local-first:

- FastAPI serve l'HTML shell e le API JSON.
- React gestisce l'interfaccia utente interattiva del client.
- Il catalogo Plaza e l'esecuzione di Pulser fluiscono ancora attraverso le rotte proxy del backend.
- I dati mock della dashboard rimangono disponibili per lo sviluppo precoce del prodotto.
- L'attuale runtime live è servito da `static/personal_agent.jsx`, quindi la ricostruzione funziona immediatamente nelle prime fasi di sviluppo senza attendere un bundle frontend.

## Struttura del Pacchetto

- `app.py`: Punto di ingresso e rotte FastAPI
- `data.py`: Accesso agli snapshot della dashboard
- `plaza.py`: Catalogo Plaza e helper proxy pulser
- `templates/index.html`: Shell HTML che avvia l'app React
- `static/`: Runtime JSX live e CSS serviti da FastAPI
- `ui/`: Scaffold sorgente futuro in React + TypeScript + Vite
- `docs/current_features.md`: Inventario completo delle funzionalità catturato dal prototipo legacy

## Esegui localmente

Dalla radice del repository:
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

L'app live viene eseguita direttamente da `static/personal_agent.jsx`.

La directory `ui/` è stata intenzionalmente preparata per una successiva promozione a una build bundle. Se desideri sperimentare con quello scaffold senza toccare il runtime live, dall'interno di `phemacast/personal_agent/ui` puoi eseguire:
```bash
npm install
npm run build
```

Questo genera l'output in `phemacast/personal_agent/ui/dist`.

Quindi apri `http://127.0.0.1:8041`.
