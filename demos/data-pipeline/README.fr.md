# Pipeline de données

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

- une file d'attente de dispatch pour les tâches de collecte de données
- un worker effectuant un polling pour les capacités correspondantes
- des tables ADS normalisées stockées localement dans SQLite
- une interface boss pour émettre et surveiller les tâches
- un pulser qui réexpose les données collectées
- un chemin pour remplacer les live collectors fournis par vos propres adaptateurs de source

## Pourquoi ce démo utilise SQLite avec des collecteurs en direct

Les configurations ADS de type production dans `ads/configs/` sont destinées à un déploiement PostgreSQL partagé.

Ce démo conserve les collecteurs en direct mais simplifie la partie stockage :

- SQLite permet de garder la configuration locale et simple
- le worker et le dispatcher partagent un seul fichier de base de données ADS local, ce qui maintient l'étape de masse SEC en direct compatible avec le même magasin de démo que lit le pulser
- la même architecture reste visible, afin que les développeurs puissent passer aux configurations de production plus tard
- certains jobs appellent des sources internet publiques, les temps de la première exécution dépendent donc des conditions du réseau et de la réactivité de la source

## Fichiers dans ce dossier

- `dispatcher.agent` : configuration du dispatcher ADS avec support SQLite
- `worker.agent` : configuration du worker ADS avec support SQLite
- `pulser.agent` : ADS pulser lisant le magasin de données de la démo
- `boss.agent` : configuration de l'interface utilisateur boss pour l'émission de tâches
- `start-dispatcher.sh` : lancer le dispatcher
- `start-worker.sh` : lancer le worker
- `start-pulser.sh` : lancer le pulser
- `start-boss.sh` : lancer l'interface utilisateur boss

Les adaptateurs de sources d'exemple associés et les helpers de live-demo se trouvent dans :

- `ads/examples/custom_sources.py` : limites de tâches d'exemple importables pour les flux de nouvelles et de prix définis par l'utilisateur
- `ads/examples/live_data_pipeline.py` : wrappers orientés démo autour du pipeline ADS SEC en direct

Tout l'état d'exécution est écrit sous `demos/data-pipeline/storage/`.

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
./demos/data-pipeline/run-demo.sh
```

Cela démarre le dispatcher, le worker, le pulser et l'interface utilisateur de boss à partir d'un seul terminal, ouvre une page de guide dans le navigateur et ouvre automatiquement les interfaces utilisateur de boss plus pulser.

Définissez `DEMO_OPEN_BROWSER=0` si vous souhaitez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux. Depuis la racine du dépôt à l'intérieur de WSL :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/data-pipeline/run-demo.sh
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement depuis WSL, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, le chemin Windows pris en charge aujourd'hui est donc WSL2.

## Démarrage rapide

Ouvrez quatre terminaux à partir de la racine du dépôt.

### Terminal 1 : démarrer le dispatcher
```bash
./demos/data-pipeline/start-dispatcher.sh
```

Résultat attendu :

- le dispatcher démarre sur `http://127.0.0.1:9060`

### Terminal 2 : démarrer le worker
```bash
./demos/data-pipeline/start-worker.sh
```

Résultat attendu :

- le worker démarre sur `127.0.0.1:9061`
- il interroge le dispatcher toutes les deux secondes

### Terminal 3 : démarrer le pulser
```bash
./demos/data-pipeline/start-pulser.sh
```

Résultat attendu :

- ADS pulser démarre sur `http://127.0.0.1:9062`

### Terminal 4 : lancer l'interface boss
```bash
./demos/data-pipeline/start-boss.sh
```

Résultat attendu :

- l'interface utilisateur de boss démarre sur `http://127.0.0.1:9063`

## Guide de la première exécution

Ouvrez :

- `http://127.0.0.1:9063/`

Dans l'interface boss UI, soumettez ces tâches dans l'ordre :

1. `security_master`
   Ceci actualise l'univers complet des sociétés cotées aux États-Unis à partir de Nasdaq Trader, il n'a donc pas besoin de payload de symbole.
2. `daily_price`
   Utilisez le payload par défaut pour `AAPL`.
3. `fundamentals`
   Utilisez le payload par défaut pour `AAPL`.
4. `financial_statements`
   Utilisez le payload par défaut pour `AAPL`.
5. `news`
   Utilisez la liste par défaut des flux RSS SEC, CFTC et BLS.

Utilisez les modèles de payload par défaut lorsqu'ils apparaissent. `security_master`, `daily_price` et `news` se terminent généralement rapidement. La première exécution de `fundamentals` ou `financial_statements` basée sur la SEC peut prendre plus de temps car elle actualise les archives SEC en cache sous `demos/data-pipeline/storage/sec_edgar/` avant de mapper la société demandée.

Ensuite, ouvrez :

- `http://127.0.0.1:9062/`

Il s'agit de l'ADS pulser pour le même magasin de données de démonstration. Il expose les tables ADS normalisées sous forme de pulses, ce qui constitue le pont entre la collecte/orchestration et la consommation en aval.

Premières vérifications suggérées du pulser :

1. Exécutez `security_master_lookup` avec `{"symbol":"AAPL","limit":1}`
2. Exécutez `daily_price_history` avec `{"symbol":"AAPL","limit":5}`
3. Exécutez `company_profile` avec `	{"symbol":"AAPL"}`
4. Exécutez `financial_statements` avec `{"symbol":"AAPL","statement_type":"income_statement","limit":3}`
5. Exécutez `news_article` avec `{"number_of_articles":3}`

Cela permet de comprendre toute la boucle ADS : l'interface boss UI émet des tâches, le worker collecte des lignes, SQLite stocke les données normalisées, et `ADSPulser` expose le résultat via des pulses interrogeables.

## Ajoutez votre propre source de données à ADSPulser

Le modèle mental important est le suivant :

- votre source se connecte au worker en tant que `job_capability`
- le worker écrit des lignes normalisées dans les tables ADS
- `ADSPule` lit ces tables et les expose via des pulses

Si votre source correspond à l'une des structures de table ADS existantes, vous n'avez généralement pas besoin de modifier `ADSPulser` du tout.

### La méthode la plus simple : écrire dans une table ADS existante

Utilisez l'une de ces paires table-to-pulse :

- `ads_security_master` -> `security_master_lookup`
- `ads_daily_price` -> `daily_price_history`
- `ads_fundamentals` -> `company_profile`
- `ads_financial_statements` -> `financial_statements`
- `ads_news` -> `news_article`
- `ads_raw_data_collected` -> `raw_collection_payload`

### Exemple : ajouter un flux de communiqué de presse personnalisé

Le dépôt inclut désormais un exemple d'appel ici :

- `ads/examples/custom_sources.py`

Pour le connecter au worker de démo, ajoutez un nom de capacité et un job cap basé sur un callable dans `demos/data-pipeline/worker.agent`.

Ajoutez ce nom de capacité :
```json
"press_release_feed"
```

Ajoutez cette entrée job-capability :
```json
{
  "name": "press_release_feed",
  "callable": "ads.examples.custom_sources:demo_press_release_cap"
}
```

Ensuite, redémarrez le worker et soumettez une tâche depuis l'interface de boss avec un payload comme :
```json
{
  "symbol": "AAPL",
  "headline": "AAPL launches a custom source demo",
  "summary": "This row came from a user-defined ADS job cap.",
  "published_at": "2026-04-02T09:30:00+00:00",
  "source_name": "UserFeed",
  "source_url": "https://example.com/user-feed"
}
```

Une fois ce travail terminé, ouvrez l'interface utilisateur de Pulser sur `http://12:0.0.1:9062/` et exécutez :
```json
{
  "symbol": "AAPL",
  "number_of_articles": 5
}
```

contre le pulse `news_article`.

Ce que vous devriez voir :

- le collecteur défini par l'utilisateur écrit une ligne normalisée dans `ads_news`
- l'entrée brute est toujours conservée dans le payload raw du job
- `ADSPulser` renvoie le nouvel article via le pulse `news_article` existant

### Deuxième exemple : ajouter un flux de prix personnalisé

Si votre source est plus proche des prix que des actualités, le même modèle fonctionne avec :
```json
{
  "name": "alt_price_feed",
  "callable": "ads.examples.custom_sources:demo_alt_price_cap"
}
```

Cet exemple écrit des lignes dans `ads_daily_price`, ce qui signifie que le résultat devient immédiatement consultable via `daily_price_history`.

### Quand vous devez modifier ADSPulser lui-même

Ne modifiez `ads/pulser.py` que si votre source ne correspond pas clairement à l'une des tables ADS normalisées existantes ou si vous avez besoin d'une toute nouvelle forme d'impulsion (pulse shape).

Dans ce cas, la démarche habituelle est la suivante :

1. ajouter ou choisir une table de stockage pour les nouvelles lignes normalisées
2. ajouter une nouvelle entrée d'impulsion prise en charge dans la configuration du pulser
3. étendre `ADSPulser.fetch_pulse_payload()` afin que l'impulsion sache comment lire et structurer les lignes stockées

Si vous êtes encore en train de concevoir le schéma, commencez par stocker le payload brut et inspectez-le d'abord via `raw_collection_payload`. Cela permet de faire avancer l'intégration de la source pendant que vous décidez de l'apparence finale de la table normalisée.

## Ce qu'il faut souligner lors d'un appel de démo

- Les tâches sont mises en file d'attente et exécutées de manière asynchrone.
- Le worker est découplé de l'interface utilisateur de Boss.
- Les lignes stockées arrivent dans des tables ADS normalisées plutôt que dans un seul magasin de blobs générique.
- Le pulser est une deuxième couche d'interface au-dessus des données collectées.
- L'ajout d'une nouvelle source signifie généralement l'ajout d'une limite de tâche worker, et non la reconstruction de toute la pile ADS.

## Créez votre propre instance

Il existe deux voies de mise à niveau naturelles à partir de cette démo.

### Conservez l'architecture locale mais remplacez par vos propres collecteurs

Modifiez `worker.agent` et remplacez les job caps de la démo live inclus par vos propres job caps ou d'autres types de ADS job-cap.

Par exemple :

- `ads.examples.custom_supplies:demo_press_release_cap` montre comment intégrer un flux d'articles personnalisé dans `ads_news`
- `ads.essentials.custom_sources:demo_alt_price_cap` montre comment intégrer une source de prix personnalisée dans `ads_daily_price`
- les configurations de production dans `ads/configs/worker.agent` montrent comment les capacités live sont connectées pour SEC, YFinance, TWSE et RSS

### Passez de SQLite à PostgreSQL partagé

Une fois que la démo locale a prouvé le flux de travail, comparez ces configurations de démo avec les configurations de style production dans :

- `ads/configs/dispatcher.agent`
- `ads/configs/worker.agent`
- `ads/configs/pulser.agent`
- `ads/configs/boss.agent`

La principale différence réside dans la définition du pool :

- cette démo utilise `SQLitePool`
- les configurations de style production utilisent `PostPostgresPool`

## Dépannage

### Les tâches restent en file d'attente

Vérifiez ces trois choses :

- le terminal du dispatcher est toujours en cours d'exécution
- le terminal du worker est toujours en cours d'exécution
- le nom de la capacité de la tâche dans l'interface de Boss correspond à celui annoncé par le worker

### L'interface de Boss se charge mais semble vide

Assurez-vous que la configuration de boss pointe toujours vers :

- `dispatcher_address = http://127.0.0.1:9060`

### Vous souhaitez un exécution propre ou devez supprimer les anciennes lignes de simulation

Arrêtez les processus de démonstration et supprimez `demos/data-pipeline/storage/` avant de recommencer.

## Arrêter la Démo

Appuyez sur `Ctrl-C` dans chaque fenêtre du terminal.
