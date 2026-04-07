# Guides de démonstration publique

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

## Commencer ici

Si vous choisissez un démo à essayer en premier, utilisez-les dans cet ordre :

1. [`hello-plaza`](./hello-plaza/README.md) : le démo de découverte multi-agents le plus léger.
2. [`pulsers`](./pulsers/README.md) : des démos axées sur le stockage de fichiers, YFinance, LLM et les ADS pulsers.
3. [`personal-research-workbench`](./personal-research-workbench/README.md) : la présentation de produit la plus visuelle.
4. [`data-pipeline`](./data-pipeline/README.md) : un pipeline ADS avec support SQLite local avec boss UI et pulser.

## Lanceurs en une seule commande

Chaque dossier de démo exécutable inclut désormais un wrapper `run-demo.sh` qui démarre les services requis à partir d'un seul terminal, ouvre une page de guide dans le navigateur avec sélection de la langue, et ouvre automatiquement les pages principales de l'interface utilisateur de la démo.

Définissez `DEMO_OPEN_BROWSER=0` si vous souhaitez que le wrapper reste dans le terminal sans ouvrir d'onglets de navigateur.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt, créez l'environnement virtuel une seule fois, installez les dépendances, puis exécutez n'importe quel wrapper de démo tel que `./demos/hello-plaza/run-demo.sh` :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Utilisez un environnement Python natif Windows. Depuis la racine du dépôt dans PowerShell :
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher hello-plaza
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Sur macOS et Linux, les wrappers `run-demo.sh` inclus fonctionnent toujours comme des wrappers de commodité autour du même lanceur Python.

## Configuration partagée

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Vous aurez généralement besoin de 2 à 4 fenêtres de terminal ouvertes, car la plupart des démos lancent quelques processus de longue durée.

Ces dossiers de démo écrivent leur état d'exécution sous `demos/.../storage/`. Cet état est ignoré par git afin que chacun puisse expérimenter librement.

## Catalogue de démos

### [`hello-plaza`](./hello-plaza/README.md)

- Public : premiers développeurs
- Environnement d'exécution : Plaza + worker + agent utilisateur orienté navigateur
- Services externes : aucun
- Ce qu'il prouve : enregistrement d'agent, découverte et une interface utilisateur simple dans le navigateur

### [`pulsers`](./pulsers/README.md)

- Public : développeurs souhaitant des exemples de pulsers petits et directs
- Environnement d'exécution : petites piles Plaza + pulser, ainsi qu'un guide ADS pulser qui réutilise le pipeline SQLite
- Services externes : aucun pour le stockage de fichiers, internet sortant pour YFinance et OpenAI, démon local Ollama pour Ollama
- Ce qu'il prouvant : packaging pulser autonome, tests, comportement de pulse spécifique au fournisseur, comment les analystes peuvent publier leurs propres pulses d'insights structurés ou pilotés par prompt, et comment ces pulses apparaissent dans un agent personnel du point de vue du consommateur

### [`personal-research-workbench`](./personal-research-workbench/README.md)

- Public : personnes souhaitant une démonstration de produit plus robuste
- Environnement d'exécution : workbench React/FastAPI + Plaza local + pulser de stockage de fichiers local + pulser YFinance optionnel + pulser d'analyse technique optionnel + stockage de diagrammes avec graines
- Services externes : aucun pour le flux de stockage, internet sortant pour le flux de graphiques YFinance et le flux de diagrammes OHLC-vers-RSI en direct
- Ce qu'il prouve : espaces de travail, mises en page, navigation Plaza, rendu de graphiques et exécution de pulser pilotée par diagrammes à partir d'une interface utilisateur plus riche

### [`data-pipeline`](./data-pipeline/README.md)

- Public : développeurs évaluant l'orchestration et les flux de données normalisés
- Environnement d'exécution : ADS dispatcher + worker + pulser + interface boss
- Services externes : aucun dans la configuration de la démo
- Ce qu'il prouve : tâches en file d'attente, exécution de worker, stockage normalisé, réexposition via un pulser et le chemin pour intégrer vos propres sources de données

## Pour l'hébergement public

Ces démos sont conçues pour être faciles à auto-héberger après la réussite d'une exécution locale. Si vous les publiez publiquement, les paramètres par défaut les plus sûrs sont :

- rendre les démos hébergées en lecture seule ou les réinitialiser selon un programme
- désactivez les intégrations basées sur API ou payantes dans la première version publique
- orientez les utilisateurs vers les fichiers de configuration utilisés par la démo afin qu'ils puissent les fork directement
- inclure les commandes locales exactes du README de la démo à côté de l'URL en direct
