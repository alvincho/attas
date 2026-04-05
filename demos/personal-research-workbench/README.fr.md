# Poste de Travail de Recherche Personnel

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

## Ce que cette démo montre

- l'interface utilisateur du banc de travail personnel s'exécutant localement
- un Plaza que le banc de travail peut parcourir
- des pulsers de données locales et en direct avec des pulses réels exécutables
- un flux `Test Run` axé sur les diagrammes qui transforme les données de marché en une série d'indicateurs calculés
- un chemin allant d'une démo soignée vers une instance auto-hébergée

## Fichiers dans ce dossier

- `plaza.agent` : Plaza local utilisé uniquement pour cette démo
- `file-storage.pulser` : pulser local s'appuyant sur le système de fichiers
- `yfinance.pulser` : pulser de données de marché optionnel s'appuyant sur le module Python `yfinance`
- `technical-analysis.pulser` : pulser de chemin optionnel qui calcule le RSI à partir des données OHLC
- `map_phemar.phemar` : configuration MapPhemar locale de la démo utilisée par l'éditeur de diagrammes intégré
- `map_phemar_pool/` : stockage de diagrammes avec une carte OHLC-to-RSI prête à l'emploi
- `start-plaza.sh` : lance la démo Plaza
- `start-file-storage-pulser.sh` : lance le pulser
- `start-yfinance-pulser.sh` : lance le pulser YFinance
- `start-technical-analysis-pulser.sh` : lance le pulser d'analyse technique
- `start-workbench.sh` : lance le workbench React/FastAPI

Tout l'état d'exécution est écrit sous `demos/personal-research-workbench/storage/`. Le lanceur pointe également l'éditeur de diagrammes intégré vers les fichiers pré-remplis `map_phemar.phemar` et `map_phemar_pool/` dans ce dossier.

## Prérequis

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Lancement en une seule commande

Depuis la racine du dépôt :
```bash
./demos/personal-research-workbench/run-demo.sh
```

Ceci démarre la pile workbench à partir d'un terminal, ouvre une page de guide dans le navigateur, puis ouvre à la fois l'interface utilisateur principale de workbench et la route `MapPhemar` intégrée utilisée dans le guide principal.

Définissez `DEMO_OPEN_BROWSER=0` si vous voulez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux. Depuis la racine du dépôt à l'intérieur de WSL :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/personal-research-workbench/run-demo.sh
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement depuis WSL, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, le chemin Windows pris en charge aujourd'hui est donc WSL2.

## Démarrage rapide

Ouvrez cinq terminaux à partir de la racine du dépôt si vous souhaitez la démonstration complète, y compris le flux du graphique YFinance et le flux d'exécution de test du diagramme.

### Terminal 1 : démarrer le Plaza local

```bash
./demos/personal-research-workbench/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8241`

### Terminal 2 : démarrer le pulser de stockage de fichiers local
```bash
./demos/personal-research-workbench/start-file-storage-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8242`
- il s'enregistre auprès du Plaza depuis le Terminal 1

### Terminal 3 : démarrer le pulser YFinance
```bash
./demos/personal-research-workbench/start-yfinance-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8243`
- il s'enregistre auprès du Plaza depuis le Terminal 1

Remarque :

- cette étape nécessite un accès Internet sortant car le pulser récupère des données en direct depuis Yahoo Finance via le module `yfinance`
- Yahoo peut occasionnellement limiter le débit des requêtes, ce flux doit donc être considéré comme une démo en direct plutôt que comme une étape fixe stricte

### Terminal 4 : démarrer le pulser d'analyse technique
```bash
./demos/personal-research-workbench/start-technical-analysis-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8244`
- il s'enregistre auprès du Plaza depuis le Terminal 1

Ce pulser calcule le `rsi` à partir d'un `ohlc_series` entrant, ou récupère les barres OHLC depuis le pulser demo YFinance lorsque vous ne fournissez que le symbol, l'interval et la plage de dates.

### Terminal 5 : démarrer le workbench
```bash
./demos/personal-research-workbench/start-workbench.sh
```

Résultat attendu :

- le workbench démarre sur `http://127.0.0.1:8041`

## Guide de la première exécution

Cette démo dispose désormais de trois flux de travail (workbench) :

1. flux de stockage local avec le pulser file-storage
2. flux de données de marché en direct avec le pulser YFinance
3. flux de test de diagramme avec les pulsers YFinance et technical-analysis

Ouvrir :

- `http://127.0.0.1:8041/`
- `http://127.0.0.1:8041/map-phemar/`

### Flux 1 : parcourir et sauvegarder des données locales

Suivez ensuite ce court chemin :

1. Ouvrez le flux de paramètres dans le workbench.
2. Allez à la section `Connection`.
3. Définissez l'URL Plaza par défaut sur `http://12rypt.0.0.1:8241`.
4. Actualisez le catalogue Plaza.
5. Ouvrez ou créez une fenêtre de navigateur dans le workbench.
6. Choisissez le pulser file-storage enregistré.
7. Exécutez l'un des pulses intégrés tels que `list_bucket`, `bucket_create` ou `bucket_browse`.

Première interaction suggérée :

- créer un bucket public nommé `demo-assets`
- parcourir ce bucket
- sauvegarder un petit objet texte
- le recharger à nouveau

Cela offre un cycle complet : interface utilisateur riche, découverte Plaza, exécution de pulser et état local persisté.

### Flux 2 : visualiser les données et tracer un graphique à partir du pulser YFinance

Utilisez la même session de workbench, puis :

1. Actualisez à nouveau le catalogue Plaza pour que le pulser YFinance apparaisse.
2. Ajoutez un nouveau volet de navigation ou reconfigurez un volet de données existant.
3. Choisissez le pulse `ohlc_bar_series`.
4. Choisissez le pulser `DemoYFinancePulser` si le workbench ne le sélectionne pas automatiquement.
5. Ouvrez `Pane Params JSON` et utilisez une charge utile (payload) comme celle-ci :
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

6. Cliquez sur `Get Data`.
7. Dans `Display Fields`, activez `ohlc_series`. Si un autre champ est déjà sélectionné, désactivez-le pour que l'aperçu pointe vers la série temporelle elle-même.
8. Changez `Format` en `chart`.
9. Réglez `Chart Style` sur `candle` pour des bougies OHLC ou `line` pour une vue de tendance simple.

Ce que vous devriez voir :

- le volet récupère les données de barres pour le symbole et la plage de dates demandés
- l'aperçu passe de données structurées à un graphique
- changer le symbole ou la plage de dates vous donne un nouveau graphique sans quitter le workbench

Variations recommandées :

- remplacez `AAPL` par `MSFT` ou `NVDA</code>`
- raccourcissez la plage de dates pour une vue récente plus précise
- comparez `line` et `candle` en utilisant la même réponse `ohlc_bar_series`

### Flux 3 : charger un diagramme et utiliser Test Run pour calculer une série RSI

Ouvrez la route de l'éditeur de diagrammes :

- `http://127.0.0.1:8041/map-phemar/`

Ensuite, suivez ce chemin :

1. Confirmez que l'URL Plaza dans l'éditeur de diagrammes est `http://127.0.0.1:8241`.
2. Cliquez sur `Load Phema`.
3. Choisissez `OHLC To RSI Diagram`.
4. Inspectez le graphique initial. Il doit afficher `Input -> OHLC Bars -> RSI 14 -> Output`.
5. Cliquez sur `Test Run`.
6. Utilisez ce payload d'entrée :
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

7. Exécute la carte et développez les sorties des étapes.

Ce que vous devriez voir :

- l'étape `OHLC Bars` appelle le pulser demo YFinance et renvoie `ohlc_series`
- l'étape `RSI 14` transmet ces barres au pulser technical-analysis avec `window: 14`
- la charge utile `Output` finale contient un tableau `values` calculé avec des entrées `timestamp` et `value`

Si vous souhaitez reconstruire le même diagramme à partir de zéro au lieu de charger la graine :

1. Ajoutez un nœud arrondi nommé `OHLC Bars`.
2. Liez-le à `DemoYFinancePulser` et au pulse `ohlc_bar_series`.
3. Ajoutez un nœud arrondi nommé `RSI 14`.
4. Liez-le à `DemoTechnicalAnalysisPulser` et au pulse `rsi`.
5. Définissez les paramètres du nœud RSI sur :
```json
{
  "window": 14,
  "price_field": "close"
}
```

6. Connecter `Input -> OHLC Bars -> RSI 14 -> Output`.
7. Laisser les mappages de bordure tels que `{}` afin que les noms de champs correspondants circulent automatiquement.

## Ce qu'il faut souligner lors d'une démo

- Le workbench charge toujours des données de tableau de bord fictives utiles même avant l'ajout de connexions en direct.
- L'intégration Plaza est optionnelle et peut pointer vers un environnement local ou distant.
- Le pulser de stockage de fichiers est uniquement local, ce qui rend la démo publique sûre et reproductible.
- Le pulser YFinance ajoute une deuxième histoire : le même workbench peut parcourir les données de marché en direct et les afficher sous forme de graphique.
- L'éditeur de diagrammes ajoute une troisième histoire : le même backend peut orchestrer des flux multi-étapes et exposer chaque étape via `Test Run`.

## Créez votre propre instance

Il existe trois chemins de personnalisation courants :

### Modifier les données initiales du tableau de bord et de l'espace de travail

Le workbench lit l'instantané de son tableau de bord à partir de :

- `attas/personal_agent/data.py`

C'est l'endroit le plus rapide pour remplacer vos propres listes de surveillance, métriques ou paramètres par défaut de l'espace de travail.

### Modifier l'interface visuelle

L'exécution actuelle du workbench en direct est servie depuis :

- `phemacast/personal_agent/static/personal_agent.jsx`
- `phemacast/personal_agent/static/personal_agent.css`

Si vous souhaitez changer le thème de la démo ou simplifier l'interface utilisateur pour votre public, commencez par là.

### Modifier les Plaza et pulsers connectés

Si vous souhaitez un backend différent :

1. copiez `plaza.agent`, `file	storage.pulser`, `yfinance.pulser` et `technical-analysis.pulser`
2. renommez les services
3. mettez à jour les ports et les chemins de stockage
4. modifiez le diagramme initial dans `map_phemar_pool/phemas/demo-ohlc-to-rsi-diagram.json` ou créez le vôtre à partir du workbench
5. remplacez les pulsers de la démo par vos propres agents lorsque vous serez prêt

## Paramètres optionnels du Workbench

Le script de lancement prend en charge quelques variables d'environnement utiles :
```bash
PHEMACAST_PERSONAL_AGENT_PORT=8055 ./demos/personal-research-workbench/start-workbench.sh
PHEMACAST_PERSONAL_AGENT_RELOAD=1 ./demos/personal-research-workbench/start-workbench.sh
```

Utilisez `PHEMACAST_PERSONAL_AGENT_RELOAD=1` lorsque vous modifiez activement l'application FastAPI pendant le développement.

## Dépannage

### Le workbench se charge, mais les résultats de Plaza sont vides

Vérifiez ces trois points :

- `http://127.0.0.1:8241/health` est accessible
- les terminaux file-storage, YFinance et technical-analysis pulser sont toujours en cours d'exécution lorsque vous avez besoin de ces flux
- les paramètres `Connection` du workbench pointent vers `http://127.0.0.1:8241`

### Le pulser n'affiche pas encore d'objets

C'est normal lors du premier démarrage. Le backend de stockage de la démo démarre vide.

### Le volet YFinance ne dessine pas de graphique

Vérifiez ces points :

- le terminal YFinance pulser est en cours d'exécution
- le pulse sélectionné est `ohlc_bar_series`
- `Display Fields` inclut `ohlc_series`
- `Format` est réglé sur `chart`
- `Chart Style` est `line` ou `candle`

Si la requête elle-même échoue, essayez un autre symbole ou relancez-la après une courte attente car Yahoo peut limiter le débit ou rejeter des requêtes par intermittence.

### Le diagramme `Test Run` échoue

Vérifiez ces points :

- `httprypt://127.0.0.1:8241/health` est accessible
- le YFinance pulser est en cours d'exécution sur `http://127.0.0.1:8243`
- le technical-analysis pulser est en cours d'exécution sur `http://127.0.0.1:8244`
- le diagramme chargé est `OHLC To RSI Diagram`
- la charge utile d'entrée inclut `symbol`, `interval`, `start_date` et `end_date`

Si l'étape `OHLC Bars` échoue en premier, le problème est généralement l'accès en direct à Yahoo ou la limitation du débit. Si l'étape `RSI 14` échoue, la cause la plus courante est que le technical-analysis pulser n'est pas en cours d'exécution ou que la réponse OHLC en amont n'incluait pas `ohlc_series`.

### Vous souhaitez réinitialiser la démo

La réinitialisation la plus sûre consiste à pointer les valeurs `root_path` vers un nouveau nom de dossier, ou à supprimer le dossier `demos/personal-research-workbench/storage/` lorsqu'aucun processus de démo n'est en cours.

## Arrêter la démo

Appuyez sur `Ctrl-C` dans chaque fenêtre du terminal.
