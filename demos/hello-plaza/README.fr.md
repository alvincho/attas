# Hello Plaza

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

- un registre Plaza s'exécutant localement
- un agent s'enregistrant automatiquement auprès de Plaza
- une interface utilisateur côté navigateur connectée à ce Plaza
- un ensemble de configuration minimal que les développeurs peuvent copier dans leur propre projet

## Fichiers dans ce dossier

- `plaza.agent` : config de démo Plaza
- `worker.agent` : config de déso worker
- `user.agent` : config de démo user-agent
- `start-plaza.sh` : lancer Plaza
- `start-worker.sh` : lancer le worker
- `start-user.sh` : lancer l'user agent orienté navigateur

Tout l'état d'exécution est écrit sous `demos/hello-plaza/storage/`.

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
./demos/hello-plaza/run-demo.sh
```

Ceci lance Plaza, le worker et l'interface utilisateur à partir d'un seul terminal, ouvre une page de guide dans le navigateur et ouvre l'interface utilisateur automatiquement.

Définissez `DEM:OPEN_BROWSER=0` si vous souhaitez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

### Windows

Utilisez WSL2 avec Ubuntu ou une autre distribution Linux. Depuis la racine du dépôt à l'intérieur de WSL :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/hello-plaza/run-demo.sh
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement depuis WSL, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

Les wrappers natifs PowerShell / Command Prompt ne sont pas encore intégrés, le chemin Windows pris en charge aujourd'hui est donc WSL2.

## Démarrage rapide

Ouvrez trois terminaux à partir de la racine du dépôt.

### Terminal 1 : démarrer Plaza
```bash
./demos/hello-plaza/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8211`
- `http://127.0.0.1:8211/health` renvoie un état sain

### Terminal 2 : démarrer le worker
```bash
./demos/hello-plaza/start-worker.sh
```

Résultat attendu :

- le worker démarre sur `127.0.0.1:8212`
- it s'enregistre automatiquement auprès de Plaza depuis Terminal 1

### Terminal 3 : lancer l'interface utilisateur

```bash
./demos/hello-plaza/start-user.sh
```

Résultat attendu :

- l'agent utilisateur côté navigateur démarre sur `http://127.0.0.1:8214/`

## Vérifier la pile

Dans un quatrième terminal, ou après le démarrage des services :
```bash
curl http://127.0.0.1:8211/health
curl http://127.0.0.1:8214/api/plazas_status
```

Ce que vous devriez voir :

- la première commande renvoie une réponse Plaza saine
- la deuxième commande affiche le Plaza local et le `demo-worker` enregistré

Ensuite, ouvrez :

- `http://127.0.0.1:8214/`

Il s'agit de l'URL de la démo publique à partager lors d'une présentation locale ou d'un enregistrement d'écran.

## Ce qu'il faut souligner lors d'une démo

- Plaza est la couche de découverte.
- Le worker peut être démarré indépendamment et apparaît tout de même dans le répertoire partagé.
- L'interface utilisateur ne nécessite pas de connaissance codée en dur du worker. Elle le découvre via Plaza.

## Créez votre propre instance

La manière la plus simple de transformer ceci en votre propre instance est la suivante :

1. Copiez `plaza.agent`, `worker.agent` et `user.agent` dans un nouveau dossier.
2. Renommez les agents.
3. Modifiez les ports si nécessaire.
4. Dirigez chaque `root_path` vers votre propre emplacement de stockage.
5. Si vous modifiez l'URL ou le port de Plaza, mettez à jour `plaza_url` dans `worker.agent` et `user.agent`.

Les trois champs les plus importants à personnaliser sont :

- `name` : ce que l'agent annonce comme son identité
- `port` : l'endroit où le service HTTP écoute
- `root_path` : l'endroit où l'état local est stocké

Une fois que les fichiers sont corrects, exécutez :
```bash
python3 prompits/create_agent.py --config path/to/your/plaza.agent
python3 prompits/create_agent.py --config path/to/your/worker.agent
python3 prompits/create_agent.py --config path/to/your/user.agent
```

## Dépannage

### Port déjà utilisé

Modifiez le fichier `.agent` concerné et choisissez un port libre. Si vous déplacez Plaza vers un nouveau port, mettez à jour le `plaza_url` dans les deux configurations dépendantes.

### L'interface utilisateur affiche un répertoire Plaza vide

Vérifiez ces trois points :

- Plaza est en cours d'exécution sur `http://127.0.0.1:8211`
- le terminal du worker est toujours en cours d'exécution
- `worker.agent` pointe toujours vers `http://127.0.0.1:8211`

### Vous souhaitez un état de démo neuf

La réinitialisation la plus sûre consiste à pointer les valeurs `root_path` vers un nouveau nom de dossier plutôt que de supprimer les données sur place.

## Arrêter la démo

Appuyez sur `Ctrl-C` dans chaque fenêtre du terminal.
