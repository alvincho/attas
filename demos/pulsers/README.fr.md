# Ensemble de démonstration Pulser

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

Utilisez ceux-ci dans cet ordre si vous apprenez le modèle pulser pour la première fois :

1. [`file-storage`](./file-storage/README.md) : la démo pulser locale la plus sûre
2. [`analyst-insights`](./analyst-insights/README.md) : un pulser appartenant à un analyste et exposé sous forme de vues d'aperçu réutilisables
3. [`finance-briefings`](./finance-briefings/README.md) : des pulses de flux de travail financier publiés dans un format que MapPhemar et Personal Agent peuvent exécuter
4. [`yfinance`](./yfinance/README.md) : un pulser de données de marché en direct avec sortie de séries chronologiques
5. [`llm`](./llm/README.md) : pulsers de chat locaux Ollama et cloud OpenAI
6. [`ads`](./cal/ads/README.md) : le pulser ADS en tant que partie de la démo du pipeline SQLite

## Lanceurs en une seule commande

Chaque dossier de démo pulser exécutable inclut désormais un wrapper `run-demo.sh` qui démarre les services locaux requis à partir d'un seul terminal, ouvre une page de guide dans le navigateur avec sélection de la langue, et ouvre automatiquement les pages principales de l'interface utilisateur de la démo.

Définissez `DEMO_OPEN_BROWSER=0` si vous souhaitez que le wrapper reste dans le terminal sans ouvrir d'onglets de navigateur.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt, créez l'environnement virtuel une seule fois, installez les dépendances, puis exécutez n'importe quel wrapper pulser tel que `./demos/pulsers/file-storage/run-demo.sh` :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux. Depuis la racine du dépôt à l'intérieur de WSL, exécutez les mêmes commandes :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement depuis WSL, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, le chemin Windows pris en charge aujourd'hui est donc WSL2.

## Ce que couvre cet ensemble de démonstrations

- comment un pulser s'enregistre auprès de Plaza
- comment tester des impulsions depuis le navigateur ou avec `curl`
- comment packager un pulser en tant que petit service auto-hébergé
- comment se comportent les différentes familles de pulser : stockage, analyse, finance, LLM et services de données

## Configuration partagée

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Chaque dossier de démo écrit l'état d'exécution local sous `demos/pulsers/.../storage/`.

## Catalogue de démos

### [`file-storage`](./file-storage/README.md)

- Runtime : Plaza + `SystemPulser`
- Services externes : aucun
- Ce qu'il prouve : création de buckets, sauvegarde/chargement d'objets, et état du pulser uniquement local

### [`analyst-insights`](./analyst-insights/README.md)

- Runtime : Plaza + `PathPulser`
- Services externes : aucun pour la vue structurée, Ollama local pour le flux d'actualités par prompt
- Ce qu'il prouve : comment un analyste peut publier à la fois des vues de recherche fixes et des sorties Ollama appartenant aux prompts via plusieurs pulses réutilisables, puis les exposer à un autre utilisateur via un agent personnel

### [`finance-briefings`](./finance-briefings/README.md)

- Runtime : Plaza + `FinancialBriefingPulser`
- Services externes : aucun dans le chemin de démo local
- Ce qu'il prouve : comment un pulser appartenant à Attas peut publier des étapes de flux de travail financier comme des blocs de construction adressables par pulse afin que MapPhemar diagrams et Personal Agent puissent stocker, édimenter et exécuter le même graphe de flux de travail

### [`yfinance`](./yfinance/README.md)

- Runtime : Plaza + `YFinancePulser`
- Services externes : accès internet vers Yahoo Finance
- Ce qu'il prouve : pulses d'instantanés, pulses de séries OHLC et payloads de sortie adaptés aux graphiques

### [`llm`](./llm/README.md)

- Runtime : Plaza + `OpenAIPulser` configuré pour OpenAI ou Ollama
- Services externes : API OpenAI pour le mode cloud, daemon Ollama local pour le mode local
- Ce qu'il prouve : `llm_chat`, interface utilisateur d'éditeur de pulser partagée et infrastructure LLM interchangeable de fournisseur

### [`ads`](./ads/README.md)

- Runtime : ADS dispatcher + worker + pulser + boss UI
- Services externes : aucun dans le chemin de démo SQLite
- Ce qu'il prouve : `ADSPulser` sur des tables de données normalisées et comment vos propres collecteurs s'écoulent dans ces pulses
