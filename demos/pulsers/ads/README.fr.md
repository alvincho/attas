# Démo ADS Pulser

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

## Ce que cette démo couvre

- comment `ADSPulser` s'appuie sur des tables ADS normalisées
- comment l'activité du dispatcher et du worker se transforme en données visibles par le pulser
- comment vos propres collectors peuvent déposer des données dans les tables ADS et apparaître via les pulses existants

## Configuration

Suivez le guide de démarrage rapide dans :

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Ou utilisez l'enveloppe à commande unique axée sur pulser depuis la racine du dépôt :
```bash
./demos/pulsers/ads/run-demo.sh
```

Cet wrapper lance la même pile SQLite ADS que `data-pipeline`, mais ouvre un guide dans le navigateur et des onglets axés sur la procédure pas à pas pulser-first.

Cela démarre :

1. l'ADS dispatcher
2. l'ADS worker
3. l'ADS pulser
4. l'interface boss UI

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/ads/run-demo.sh
```

### Windows

Utilisez un environnement Python natif Windows. Depuis la racine du dépôt dans PowerShell :
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher ads
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

## Premières vérifications de Pulser

Une fois les tâches d'exemple terminées, ouvrez :

- `http://127.0.0.1:9062/`

Ensuite, testez :

1. `security_master_lookup` avec `{"symbol":"AAPL","limit":1}`
2. `daily_price_history` avec `{"symbol":"AAPL","limit":5}`
3. `company_profile` avec `{"symbol":"AAPL"}`
4. `news_article` avec `{"symbol":"AAPL","number_of_articles":3}`

## Pourquoi ADS est différent

Les autres démos de pulser lisent principalement directement depuis un fournisseur en direct ou un backend de stockage local.

`ADSPulser` lit plutôt à partir des tables normalisées écrites par le pipeline ADS :

- les workers collectent ou transforment les données sources
- le dispatcher persiste les lignes normalisées
- `ADSPulser` expose ces lignes en tant que pulses consultables

Cela en fait la démo idéale pour expliquer comment ajouter vos propres adaptateurs de source.

## Ajoutez votre propre source

Le guide détaillé se trouve ici :

- [`../../data-pipeline/README.md`](../../data-pipeline/README.md)

Utilisez les exemples personnalisés ici :

- [`../../../ads/examples/custom_sources.py`](../../../ads/examples/custom_sources.py)

Ces exemples montrent comment un collecteur défini par l'utilisateur peut écrire dans :

- `ads_news`, qui devient disponible via `news_article`
- `ads_daily_price`, qui devient disponible via `daily_price_history`
