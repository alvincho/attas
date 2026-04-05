# Démo du flux de travail des briefings financiers

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

## Ce que montre cette démo

- un `FinancialBriefingPulser` appartenant à Attas exposant des workflow-seed pulses et des finance briefing step pulses
- un pulse de contexte d'entrée de workflow :
  - `prepare_finance_briefing_context`
  - distingue le workflow avec `workflow_name` : `morning_desk_briefing`, `watchlist_check` ou `research_roundup`
- pulses d'étapes financières partagés :
  - `build_finance_source_bundle`
  - `build_finance_citations`
  - `build_finance_facts`
  - `build_finance_risks`
  - `build_finance_catalysts`
  - `build_finance_conflicting_evidence`
  - `build_finance_takeaways`
  - `build_finance_open_questions`
  - `build_finance_summary`
  - `assemble_finance_briefing_payload`
- pulses de publication/exportation en aval :
  - `briefing_to_phema`
  - `notebooklm_export_pack`

## Pourquoi cela existe

MapPhemar exécute des diagrammes en appelant des pulsers et des pulses. Les flux de travail de finance briefing ont commencé comme de simples fonctions Python dans `attas`, mais les diagrammes actuels décomposent ces flux de travail en nœuds d'étape modifiables, le runtime utilise donc désormais un pulser natif d'Attas au lieu d'un wrapper MCP générique.

La surface d'exécution est :

- [finance-briefings.pulser](./finance-briefings.pulser) : configuration démo pour `attas.pulsers.financial_briefing_pulser.FinancialBriefingPulser`
- [financial_briefing_pulser.py](../../../attas/pulsers/financial_briefing_pulser.py) : classe pulser appartenant à Attas hébergeant la graine du workflow et les pulses d'étape
- [briefings.py](../../../attas/workflows/briefings.py) : helpers d'étape de finance briefing publics consommés par le pulser

## Hypothèses d'exécution

- Plaza à `http://127.0.0.1:8272`
- `DemoFinancialBriefingPulser` à `http://127.0.0.1:8271`

## Lancement en une seule commande

Depuis la racine du dépôt :
```bash
./demos/pulsers/finance-briefings/run-demo.sh
```

Ceci lance le Plaza local ainsi que le pulser de briefing financier à partir d'un seul terminal, ouvre une page de guide dans le navigateur et ouvre automatiquement l'interface utilisateur de pulser.

Définissez `DEMO_OPEN_BROWSER=0` si vous souhaitez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux. Depuis la racine du dépôt à l'intérieur de WSL :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/finance-briefings/run-demo.sh
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement depuis WSL, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, le chemin Windows pris en charge aujourd'hui est donc WSL2.

## Lancement manuel

Depuis la racine du dépôt :
```bash
./demos/pulsers/finance-briefings/start-plaza.sh
./demos/pulsers/finance-briefings/start-pulser.sh
```

## Fichiers de diagrammes associés

Ces diagrammes se trouvent dans `demos/files/diagrams/` :

- `finance-morning-desk-briefing-notebooklm-diagram.json`
- `finance-watchlist-check-notebooklm-diagram.json`
- `finance-research-roundup-notebooklm-diagram.json`

Chaque diagramme suit la même structure modifiable :

`Input -> Workflow Context -> Finance Step Pulses -> Assemble Briefing -> Report Phema + NotebookLM Pack -> Output`

## Adéquation actuelle de MapPhemar

Ces flux de travail s'intègrent dans le modèle MapPhemar actuel sans ajouter de nouveau type de nœud ou de schéma :

- les étapes exécutables sont des nœuds `rectangle` réguliers
- les limites utilisent `pill`
- la ramification reste disponible via `branch`
- la diffusion (fan-out) des artefacts est gérée par plusieurs arêtes sortantes du nœud de flux de travail

Limite actuelle d'exécution :

- `Input` peut se connecter à exactement un nœud en aval, la diffusion doit donc se produire après le premier nœud de flux de travail exécutable plutôt que directement depuis `un `Input`

Aucun nouveau type de nœud MapPhemar ni aucune extension de schéma n'a été nécessaire pour ces flux de travail financiers étape par étape. Les nœuds exécutables réguliers ainsi que la surface Attas pulser sont suffisants pour le stockage, l'édition et l'exécution actuels.
