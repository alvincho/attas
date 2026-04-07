# Démo Analyst Insight Pulser

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

- un pulser appartenant à un analyste avec plusieurs pulses d'informations structurées
- un second pulser appartenant à un analyste, reposant sur un agent d'actualités distinct et un agent local Ollama
- une manière propre de séparer les données sources brutes des Prompits rédigés par l'analyste et des sorties finales destinées aux consommateurs
- un parcours de l'agent personnel qui montre la même pile technologique du point de vue d'un autre utilisateur
- les fichiers exacts qu'un analyste ou un PM modifierait pour publier sa propre analyse

## Fichiers dans ce dossier

- `plaza.agent` : Plaza local pour la démo du pulser analyste
- `analyst-insights.pulser` : Configuration `PathPulser` définissant le catalogue public de pulses
- `analyst_insight_step.py` : Logique de transformation partagée plus le paquet de couverture analyste pré-rempli
- `news-wire.pulser` : Agent d'actualités upstream local qui publie des paquets `news_article` pré-remplis
- `news_wire_step.py` : Paquets d'actualités bruts pré-remplis renvoyés par l'agent d'actualités upstream
- `ollama.pulser` : Pulser `llm_chat` local basé sur Ollama pour la démo de prompt analyste
- `analyst-news-ollama.pulser` : Pulser analyste composé qui récupère les actualités, applique les prompts appartenant à l'analyste, appelle Ollama et normalise le résultat en plusieurs pulses
- `analyst_news_ollama_step.py` : Le pack de prompts analyste plus la logique de normalisation JSON
- `start-plaza.sh` : Lancer Plaza
- `start-pulser.sh` : Lancer le pulser analyste structuré fixe
- `start-news-pulser.sh` : Lancer l'agent d'actualités upstream pré-rempli
- `start-ollama-pulser.sh` : Lancer le pulser Ollama local
- `start-analyst-news-pulser.sh` : Lancer le pulser analyste avec prompts
- `start-personal-agent.sh` : Lancer l'interface utilisateur de l'agent personnel pour la démonstration de la vue consommateur
- `run-demo.sh` : Lancer la démo depuis un terminal et ouvrir le guide du navigateur ainsi que les pages principales de l'interface utilisateur

## Lancement en une seule commande

Depuis la racine du dépôt :
```bash
./demos/pulsers/analyst-insights/run-demo.sh
```

Cet wrapper lance le flux structuré léger par défaut.

Pour lancer plutôt le flux avancé actualités + Ollama + agent personnel :
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

Définissez `DEMO_OPEN_BROWSER=0` si vous voulez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/analyst-insights/run-demo.sh
```

Pour le chemin avancé :
```bash
DEMO_ANALYST_MODE=advanced ./demos/pulsers/analyst-insights/run-demo.sh
```

### Windows

Utilisez un environnement Python natif Windows. Depuis la racine du dépôt dans PowerShell :
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

Pour le chemin avancé :
```powershell
$env:DEMO_ANALYST_MODE = "advanced"
.venv\Scripts\python.exe -m scripts.demo_launcher analyst-insights
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

## Démo 1 : Vues structurées des analystes

Il s'agit du chemin local uniquement, sans LLM.

Ouvrez deux terminaux à partir de la racine du dépôt.

### Terminal 1 : démarrer Plaza
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8266`

### Terminal 2 : démarrer le pulser
```bash
./demos/pulsers/analyst-insights/start-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8267`
- il s'enregistre auprès du Plaza sur `http://12:0.0.1:8266`

## Essayez dans le navigateur

Ouvrez :

- `http://127.0.0.1:8267/`

Ensuite, testez ces pulses avec `NVDA` :

1. `rating_summary`
2. `thesis_bullets`
3. `risk_watch`
4. `scenario_grid`

Paramètres suggérés pour les quatre :
```json
{
  "symbol": "NVDA"
}
```

Ce que vous devriez voir :

- `rating_summary` renvoie la conclusion principale, l'objectif, la confiance et un court résumé
- `thesis_bullets` renvoie la thèse positive sous forme de liste à puces
- `risk_watch` renvoie les principaux risques ainsi que les éléments à surveiller
- `scenario_grid` renvoie les scénarios haussier, de base et baissier dans un seul payload structuré

## Essayez avec Curl

Évaluation du titre :
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"rating_summary","params":{"symbol":"NVDA"}}'
```

Points clés de la thèse :
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"thesis_bullets","params":{"symbol":"NVDA"}}'
```

Surveillance des risques :
```bash
curl -sS http://127.0.0.1:8267/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"risk_watch","params":{"symbol":"NVDA"}}'
```

## Comment un analyste personnalise cette démo

Il y a deux principaux points de modification.

### 1. Modifier la vue de recherche réelle

Modifier :

- `demos/pulsers/analyst-insights/analyst_insight_step.py`

Ce fichier contient le paquet `ANALYST_COVERAGE` initialisé. C'est là que vous modifiez :

- les symboles couverts
- le nom de l'analyste
- les étiquettes de notation
- les prix cibles
- les points de la thèse
- les risques clés
- les scénarios haussier/de base/baissier

### 2. Modifier le catalogue public de pulses

Modifier :

- `demos/pulsers/analyst-insights/analyst-insights.pulser`

Ce fichier contrôle :

- quels pulses existent
- le nom et la description de chaque pulse
- les schémas d'entrée et de sortie
- les tags et les adresses

Si vous souhaitez ajouter un nouveau pulse d'insight, copiez l'une des entrées existantes et pointez-la vers un nouveau `insight_view`.

## Pourquoi ce modèle est utile

- les outils de portefeuille peuvent demander uniquement le `rating_summary`
- les constructeurs de rapports peuvent demander `thesis_bullets`
- les tableaux de bord de risque peuvent demander `risk_watch`
- les outils d'évaluation peuvent demander `scenario_grid`

Cela signifie que l'analyste publie un seul service, mais différents consommateurs peuvent extraire exactement la partie dont ils ont besoin.

## Prochaines étapes

Une fois que cette forme de pulser local est cohérente, les prochaines étapes sont :

1. ajouter plus de symboles couverts au paquet de couverture des analystes
2. ajouter des étapes de source avant l'étape Python finale si vous souhaitez mélanger votre propre vue avec les sorties de YFinance, ADS ou LLM
3. exposer le pulser via un Plaza partagé au lieu de seulement le Plaza de démo local

## Démo 2 : Analyst Prompt Pack + Ollama + Agent Personnel

Ce deuxième flux montre une configuration d'analyste plus réaliste :

- un agent publie des données brutes `news_article`
- un deuxième agent expose `llm_chat` via Ollama
- le pulser appartenant à l'analyste utilise son propre prompt pack pour transformer ces informations brutes en plusieurs pulses réutilisables
- l'agent personnel consomme les pulses terminés du point de vue d'un autre utilisateur

### Prérequis pour le flux de prompts

Assurez-vous qu'Ollama est en cours d'exécution localement et que le modèle existe :

```bash
ollama serve
ollama pull qwen3:8b
```

Ensuite, ouvrez cinq terminaux à partir de la racine du dépôt.

### Terminal 1 : démarrer Plaza

Si le Demo 1 est toujours en cours d'exécution, continuez à utiliser le même Plaza.
```bash
./demos/pulsers/analyst-insights/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8266`

### Terminal 2 : lancer l'agent d'actualités upstream
```bash
./demos/pulsers/analyst-insights/start-news-pulser.sh
```

Résultat attendu :

- le news pulser démarre sur `http://127.0.0.1:8268`
- il s'enregistre auprès du Plaza sur `http://12:7.0.0.1:8266`

### Terminal 3 : démarrer le pulser Ollama
```bash
./demos/pulsers/analyst-insights/start-ollama-pulser.sh
```

Résultat attendu :

- le pulser Ollama démarre sur `http://127.0.0.1:8269`
- il s'enregistre auprès de Plaza sur `http://127.0.0.1:8266`

### Terminal 4 : démarrer le pulser prompted analyst

Démarrez ceci après que les agents news et Ollama sont déjà en cours d'exécution, car le pulser valide ses chaînes d'échantillonnage lors du démarrage.
```bash
./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh
```

Résultat attendu :

- le pulser de l'analyste demandé démarre sur `http://127.0.0.1:8270`
- il s'enregistre auprès de Plaza sur `http://127.0.0.1:8266`

### Terminal 5 : démarrer l'agent personnel
```bash
./demos/pulsers/analyst-insights/start-personal-agent.sh
```

Résultat attendu :

- l'agent personnel démarre sur `http://127.0.0.1:8061`

### Essayez directement le Prompted Analyst Pulser

Ouvrez :

- `http://127.0.0.1:8270/`

Ensuite, testez ces pulses avec `NVDA` :

1. `news_desk_brief`
2. `news_monitoring_points`
3. `news_client_note`

Paramètres suggérés :
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Ce que vous devriez voir :

- `news_desk_brief` transforme les articles en amont en une position de style PM et une note courte
- `news_monitoring_points` transforme les mêmes articles bruts en éléments de surveillance et en indicateurs de risque
- `news_client_note` transforme les mêmes articles bruts en une note plus propre destinée aux clients

Le point important est que l'analyste contrôle les Prompits dans un seul fichier, tandis que les utilisateurs en aval ne voient que des interfaces pulse stables.

### Utiliser l'Agent Personnel depuis la Vue d'un Autre Utilisateur

Ouvrir :

- `http://127.0.0.1:8061/`

Ensuite, suivez ce chemin :

1. Ouvrez `Settings`.
2. Allez dans l'onglet `Connection`.
3. Réglez l'URL Plaza sur `http://127.0.0.1:8266`.
4. Cliquez sur `Refresh Plaza Catalog`.
5. Créez une `New Browser Window`.
6. Mettez la fenêtre du navigateur en mode `edit`.
7. Ajoutez un premier pane plain et pointez-le vers `DemoAnalystNewsWirePulser -> news_article`.
8. Utilisez les pane params :
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2
}
```

9. Cliquez sur `Get Data` pour que l'utilisateur puisse voir les articles bruts.
10. Ajoutez un deuxième volet simple et pointez-le vers `DemoAnalystPromptedNewsPulser -> news_desk_brief`.
11. Réutilisez les mêmes paramètres et cliquez sur `Get Data`.
12. Ajoutez un troisième volet avec `news_monitoring_points` ou `news_client_note`.

Ce que vous devriez voir :

- un volet affiche les actualités brutes en amont provenant d'un autre agent
- le volet suivant affiche la vue traitée de l'analyste
- le troisième volet montre comment le même pack de prompts d'analyste peut publier une surface différente pour une audience différente

C'est l'histoire clé du consommateur : un autre utilisateur n'a pas besoin de connaître la chaîne interne. Il lui suffit de parcourir Plaza, de choisir un pulse et de consommer le résultat final de l'analyste.

## Comment un analyste personnalise le flux de prompts

Il y a trois principaux points de modification dans le Demo 2.

### 1. Modifier le paquet de nouvelles en amont (upstream)

Modifier :

- `demos/pulsers/analyst-insights/news_wire_step.py`

C'est là que vous modifiez les articles de base publiés par l'agent de la source upstream.

### 2. Modifier les propres prompts de l'analyste

Modifier :

- `demos/pulsers/analyst-insights/analyst_news_ollama_step.py`

Ce fichier contient le pack de prompts appartenant à l'analyste, comprenant :

- les noms de profils de prompt
- l'audience et l'objectif
- le ton et le style d'écriture
- le contrat de sortie JSON requis

C'est le moyen le plus rapide de faire en sorte que les mêmes informations brutes produisent une voix de recherche différente.

### 3. Modifier le catalogue public de pulses

Modifier :

- `demos/pulsers/analyst-insights/analyst-news-ollama.pulser`

Ce fichier contrôle :

- quels prompted pulses existent
- quel profil de prompt chaque pulse utilise
- quels agents upstream il appelle
- les schémas d'entrée et de sortie affichés aux utilisateurs en aval (downstream)

## Pourquoi le modèle avancé est utile

- l'agent d'actualités upstream peut être remplacé plus tard par YFinance, ADS ou un collecteur interne
- l'analyste conserve la propriété du pack de prompts au lieu de coder en dur des notes ponctuelles dans une interface utilisateur
- différents consommateurs peuvent utiliser différents pulses sans connaître la chaîne complète qui les sous-tend
- l'agent personnel devient une surface de consommation propre plutôt que l'endroit où réside la logique
