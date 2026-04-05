# Bibliothèque de diagrammes de démonstration

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

## Notes sur la plateforme

Ce dossier contient des ressources JSON, et non un lanceur autonome.

### macOS et Linux

Lancez d'abord l'un des démos appairés, puis chargez ces fichiers dans MapPhelar ou Personal Agent :
```bash
./demos/personal-research-workbench/run-demo.sh
```

Vous pouvez également lancer :
```bash
./demos/pulsers/analyst-insights/run-demo.sh
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux pour les lanceurs de démo appairés. Une fois la pile (stack) en cours d'exécution, ouvrez l'URL `guide=` imprimée dans un navigateur Windows si les onglets ne s'ouvrent pas automatiquement.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, WSL2 est donc la méthode Windows prise en charge aujourd'hui.

## Que contient ce dossier

Il y a deux groupes d'exemples :

- diagrammes d'analyse technique qui transforment les données de marché OHLC en séries d'indicateurs
- diagrammes d'analystes orientés LLM qui transforment les actualités brutes du marché en notes de recherche structurées
- diagrammes de flux de travail financier qui transforment les entrées de recherche normalisées en ensembles de briefings, de publications et d'exportation NotebookLM

## Fichiers dans ce dossier

### Analyse technique

- `ohlc-to-sma-20-diagram.json`: `Entrée -> Barres OHLC -> SMA 20 -> Sortie`
- `ohlc-to-ema-50-diagram.json`: `Entrée -> Barres OHLC -> EMA 50 -> Sortie`
- `ohlc-to-macd-histogram-diagram.json`: `Entrée -> Histogramme MACD -> Sortie`
- `ohlc-to-bollinger-bandwidth-diagram.json`: `Entrée -> Bande de Bollinger -> Sortie`
- `cal-to-adx-14-diagram.json`: `Entrée -> Barres OHLC -> ADX 14 -> Sortie`
- `ohlc-to-obv-diagram.json`: `Entrée -> Barres OHLC -> OBV -> Sortie`

### Recherche LLM / Analyste

- `analyst-news-desk-brief-diagram.json`: `Entrée -> Briefing de la rédaction -> Sortie`
- `analyst-news-monitoring-points-diagram.json`: `Entrée -> Points de surveillance -> Sortie`
- `analyst-news-client-note-diagram.json`: `Entrée -> Note client -> Sortie`

### Pack de workflow financier

- `finance-morning-desk-briefing-notebooklm-diagram.json`: `Entrée -> Préparer le contexte matinal -> Pulsations des étapes financières -> Assembler le briefing -> Rapport pack Phema + NotebookLM -> Sortie`
- `finance-watchlist-check-notebooklm-diagram.json`: `Entrée -> Préparer le contexte de la liste de surveillance -> Pulsations des étapes financières -> Assembler le briefing -> Rapport pack Phema + NotebookLM -> Sortie`
- `finance-research-roundup-notebooklm-diagram.json`: `Entrée -> Préparer le contexte de recherche -> Pulsations des étapes financières -> Assembler le briefing -> Rapport pack Phema + NotebookLM -> Sortie`

Ces trois Phemas enregistrés restent séparés pour l'édition, mais ils partagent le même pulso d'entrée de workflow et distinguent le workflow avec le nœud `paramsText.workflow_name`.

## Hypothèses d'exécution

Ces diagrammes sont enregistrés avec des adresses locales concrètes afin qu'ils puissent être exécutés sans édition supplémentaire lorsque la pile de démonstration attendue est disponible.

### Diagrammes d'analyse technique

Les diagrammes d'indicateurs supposent :

- Plaza à `http://127.0.0.1:8011`
- `YFinancePulser` à `http://127.0.0.1:8020`
- `TechnicalAnalysisPulser` à `http://127.0.0.1:8033`

Les configurations pulser référencées par ces diagrammes se trouvent dans :

- `attas/configs/yfinance.pulser`
- `attas/configs/ta.pulser`

### Diagrammes LLM / Analyste

Les diagrammes orientés LLM supposent :

- Plaza à `http://127.0.0.1:8266`
- `DemoAnalystPromptedNewsPulser` à `http://127.0.0.1:8270`

Ce pulser d'analyste avec prompt dépend lui-même de :

- `news-wire.pulser` à `http://127.0.0.1:8268`
- `ollama.pulser` à `http://127.0.0.1:8269`

Ces fichiers de démonstration se trouvent dans :

- `demos/pulsers/analyst-insights/`

### Diagrammes de flux de travail financier

Les diagrammes de flux de travail financier supposent :

- Plaza à `http://127.0.0.1:8266`
- `DemoFinancialBriefingPulser` à `http://127.0.0.1:8271`

Ce pulser de démonstration est un `FinancialBriefingPulser` appartenant à Attas, s'appuyant sur :

- `demos/pulsers/finance-briefings/finance-briefings.pulser`
- `attas/pulsers/financial_briefing_pulser.py`
- `attas/workflows/briefings.py`

Ces diagrammes sont modifiables à la fois dans MapPhemar et dans les routes intégrées de Personal Agent MapPhemar car ce sont des fichiers JSON Phema ordinaires basés sur des diagrammes.

## Démarrage rapide

### Option 1 : Charger les fichiers dans MapPhemar

1. Ouvrez une instance de l'éditeur MapPhemar.
2. Chargez l'un des fichiers JSON de ce dossier.
3. Confirmez que le `plazaUrl` enregistré et les adresses pulser correspondent à votre environnement local.
4. Exécutez `Test Run` avec l'un des payloads d'exemple ci-dessous.

Si vos services utilisent des ports ou des noms différents, modifiez :

- `meta.map_phemar.diagram.plazaUrl`
- le `pulserName` de chaque nœud
- la `pulserAddress` de chaque nœud

### Option 2 : Les utiliser comme fichiers de semence

Vous pouvez également copier ces fichiers JSON dans n'importe quel pool MapPhemar sous un répertoire `phemas/` et les charger via l'interface utilisateur de l'agent de la même manière que le démo personal-research-workbench.

## Exemples d'entrées

### Diagrammes d'analyse technique

Utilisez une charge utile comme :
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

Résultat attendu :

- l'étape `OHLC Bars` récupère une série de barres historiques
- le nœud de l'indicateur calcule un tableau `values`
- la sortie finale renvoie des paires timestamp/valeur

### Diagrammes LLM / Analyste

Utilisez une charge utile comme :
```json
{
  "symbol": "NVDA",
  "number_of_articles": 2,
  "model": "qwen3:8b"
}
```

Résultat attendu :

- l'analyst pulser piloté par prompt récupère les actualités brutes
- le prompt pack transforme ces actualités en une vue analyste structurée
- la sortie renvoie des champs prêts pour la recherche tels que `desk_note`, `monitor_now` ou `client_note`

### Diagrammes de flux de travail financier

Utilisez une charge utile comme :
```json
{
  "subject": "NVDA",
  "search_results": {
    "query": "NVDA sovereign AI demand",
    "sources": []
  },
  "fetched_documents": [],
  "watchlist": [],
  "as_of": "2026-04-04T08:00:00Z",
  "output_dir": "/tmp/notebooklm-pack",
  "include_pdf": false
}
```

Résultat attendu :

- le nœud de contexte du workflow initialise le workflow financier choisi
- les nœuds financiers intermédiaires construisent des sources, des citations, des faits, des risques, des catalyseurs, des conflits, des points clés, des questions et des blocs de résumé
- le nœud d'assemblage construit une charge utile `attas.finance_briefing`
- le nœud de rapport convertit cette charge utile en un Phema statique
- le nœud NotebookLM génère des artefacts d'exportation à partir de la même charge utile
- la sortie finale fusionne les trois résultats pour inspection dans MapPhemar ou Personal Agent

## Limites actuels de l'éditeur

Ces flux de travail financiers s'adaptent au modèle MapPhemar actuel sans ajouter de nouveau type de nœud.

Deux règles d'exécution importantes s'appliquent toujours :

- `Input` doit être connecté à exactement une forme en aval
- chaque nœud exécutable non ramifié doit référencer un pulse plus un pulser accessible

Cela signifie que l'expansion (fan-out) du flux de travail doit se produire après le premier nœud exécutable, et les étapes du flux de travail doivent toujours être exposées en tant que pulses hébergés par un pulser si vous voulez que le diagramme s'exécute de bout en bout.

## Démos Associées

Si vous souhaitez exécuter les services de support plutôt que de simplement inspecter les diagrammes :

- `demos/personal-research-workbench/README.md` : flux de travail de diagramme visuel avec l'exemple RSI initialisé
- `demos/pulsers/analyst-insights/README.md` : pile d'actualités d'analyste avec prompts utilisée par les diagrammes orientés LLM
- `demos/pulsers/llm/README.md` : démo pulser `llm_chat` autonome pour OpenAI et Ollama

## Vérification

Ces fichiers sont couverts par les tests du dépôt :
```bash
pytest phemacast/tests/test_demo_file_diagrams.py phemacast/tests/test_demo_llm_file_diagrams.py attas/tests/test_finance_briefing_demo_diagram.py
```

Cette suite de tests vérifie que les diagrammes enregistrés s'exécutent de bout en bout par rapport à des flux pulser simulés ou de référence.
