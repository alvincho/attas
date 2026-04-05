# Démo LLM Pulser

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

## Fichiers dans ce dossier

- `plaza.agent` : Plaza local pour les deux variantes de pulser LLM
- `openai.pulser` : configuration pulser prise en charge par OpenAI
- `ollama.pulser` : configuration de pulser basée sur Ollama
- `start-plaza.sh`: lancer Plaza
- `start-openai-pulser.sh`: lance le pulser de démonstration OpenAI
- `start-ollama-pulser.sh`: lance le pulser de démonstration Ollama
- `run-demo.sh` : lance la démo complète à partir d'un terminal et ouvre le guide du navigateur ainsi que l'interface utilisateur du pulser sélectionné

## Lancement en une seule commande

Depuis la racine du dépôt :
```bash
./demos/pulsers/llm/run-demo.sh
```

Par défaut, le wrapper utilise OpenAI lorsque `OPENAI_API_KEY` est présent, sinon il utilise Ollama.

Exemples de fournisseurs explicites :
```bash
DEMO_LLM_PROVIDER=openai ./demos/pulsers/llm/run-demo.sh
DEMO_LLM_PROVIDER=ollama ./demos/pulsers/llm/run-demo.sh
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
./demos/pulsers/llm/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux. Depuis la racine du dépôt à l'intérieur de WSL :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/llm/run-demo.sh
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement depuis WSL, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, le chemin Windows pris en charge aujourd'hui est donc WSL2.

## Démarrage rapide

### Démarrer Plaza

Ouvrez un terminal à partir de la racine du dépôt :
```bash
./demos/pulsers/llm/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8261`

Ensuite, choisissez un fournisseur.

## Option 1 : OpenAI

Configurez d'abord votre clé API :
```bash
export OPENAI_API_KEY=your-key-here
```

Ensuite, lance le pulser :
```bash
./demos/pulsers/llm/start-openai-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8262`
- il s'enregistre auprès du Plaza sur `http://127.0.0.1:8261`

Payload de test suggéré :
```json
{
  "prompt": "Summarize why pulse interfaces are useful in one short paragraph.",
  "model": "gpt-4o-mini"
}
```

Exemple Curl :
```bash
curl -sS http://127.0.0.1:8262/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"gpt-4o-mini"}}'
```

## Option 2 : Ollama

Assurez-vous qu'Ollama est en cours d'exécution localement et que le modèle configuré est disponible :
```bash
ollama serve
ollama pull qwen3:8b
```

Ensuite, lance le pulser :
```bash
./demos/pulsers/llm/start-ollama-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8263`
- il s'enregistre auprès du Plaza sur `http://120.0.0.1:8261`

Exemple curl suggéré :
```bash
curl -sS http://127.0.0.1:8263/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"llm_chat","params":{"prompt":"Say hello in one sentence.","model":"qwen3:8b"}}'
```

## Essayez dans le navigateur

Ouvrez l'un des suivants :

- `http://127.0.0.1:8262/` pour OpenAI
- `http://127.0.0.1:8263/` pour Ollama

L'interface utilisateur vous permet de :

- inspecter la configuration du pulser
- exécuter `llm_chat`
- charger des listes de modèles
- inspecter les informations du modèle Ollama lors de l'utilisation du fournisseur local

## Ce qu'il faut souligner

- le même contrat pulse peut s'appuyer sur une inférence cloud ou locale
- passer d'OpenAI à Ollama est principalement une question de configuration, et non de refonte de l'interface
- ceci est la démo la plus simple pour expliquer les outils LLM basés sur pulser dans le dépôt

## Créez le vôtre

Pour personnaliser la démo :

1. copiez `openai.pulser` ou `ollama.pulser`
2. modifier `model`, `base_url`, les ports et les chemins de stockage
3. maintenez stable le pulse `llm_chat` si d'autres outils ou interfaces utilisateur en dépendent
