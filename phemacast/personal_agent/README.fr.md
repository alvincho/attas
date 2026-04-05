# Agent Personnel Phemacast

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

## Documentation

- [Guide détaillée de l'utilisateur](./docs/user_guide.md)
- [Inventaire des fonctionnalités actuelles](./docs/current_features.md)

Le package conserve la même structure local-first :

- FastAPI sert le shell HTML et les API JSON.
- React gère l'interface utilisateur client interactive.
- Le catalogue Plaza et l'exécution de Pulser passent toujours par les routes proxy du backend.
- Les données fictives du tableau de bord restent disponibles pour le développement précoce du produit.
- L'environnement d'exécution live actuel est servi depuis `static/personal_agent.jsx`, de sorte que la reconstruction fonctionne immédiatement lors du développement précoce sans attendre un bundle frontend.

## Structure du Package

- `app.py`: Point d'entrée et routes FastAPI
- `data.py`: Accès aux instantanés du tableau de bord
- `plaza.py`: Catalogue Plaza et helpers proxy pulser
- `templates/index.html`: Shell HTML qui initialise l'application React
- `static/`: Runtime JSX en direct et CSS servis par FastAPI
- `ui/`: Échafaudage source futur en React + TypeScript + Vite
- `docs/current_features.md`: Inventaire complet des fonctionnalités capturé à partir du prototype hérité

## Exécuter localement

Depuis la racine du dépôt :
```bash
uvicorn phemacast.personal_agent.app:app --reload --port 8041
```

L'application en direct s'exécute directement à partir de `static/personal_agent.jsx`.

Le répertoire `ui/` est intentionnellement préparé pour une promotion ultérieure vers un build packagé. Si vous souhaitez expérimenter cet échafaudage sans toucher au runtime en direct, vous pouvez exécuter depuis `phemacast/personal_agent/ui` :
```bash
npm install
npm run build
```

Cela produit un résultat dans `phemacast/personal_agent/ui/dist`.

Ensuite, ouvrez `http://127.0.0.1:8041`.
