# Démo System Pulser

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

- `plaza.agent` : Plaza local pour cette démo de pulser
- `file-storage.pulser` : pulser de stockage basé sur le système de fichiers local
- `start-plaza.sh`: lancer Plaza
- `start-pulser.sh`: lancer le pulser
- `run-demo.sh` : lance la démo complète depuis un terminal et ouvrez le guide du navigateur ainsi que l'interface utilisateur de pulser UI

## Lancement en une seule commande

Depuis la racine du dépôt :
```bash
./demos/pulsers/file-storage/run-demo.sh
```

Ceci lance Plaza et `SystemPulser` à partir d'un seul terminal, ouvre une page de guide dans le navigateur et ouvre automatiquement l'interface utilisateur de pulser.

Définissez `DEMO_OPEN_BROWSER=0` si vous voulez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/file-storage/run-demo.sh
```

### Windows

Utilisez un environnement Python natif Windows. Depuis la racine du dépôt dans PowerShell :
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher file-storage
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

## Démarrage rapide

Ouvrez deux terminaux à partir de la racine du dépôt.

### Terminal 1 : démarrer Plaza
```bash
./demos/pulsers/file-storage/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8256`

### Terminal 2 : lancer le pulser
```bash
./demos/pulsers/file-storage/start-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8257`
- il s'enregistre auprès de Plaza sur `http://127.0.0.1:8256`

## Essayez dans le navigateur

Ouvrez :

- `http://127.0.0.1:8257/`

Ensuite, testez ces pulses dans l'ordre :

1. `bucket_create`
2. `object_save`
3. `object_load`
4. `list_bucket`

Paramètres suggérés pour `bucket_create` :
```json
{
  "bucket_name": "demo-assets",
  "visibility": "public"
}
```

Paramètres suggérés pour `object_save` :
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt",
  "text": "hello from the system pulser demo"
}
```

Paramètres suggérés pour `object_load` :
```json
{
  "bucket_name": "demo-assets",
  "object_key": "notes/hello.txt"
}
```

## Essayez avec Curl

Créez un bucket :
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"bucket_create","params":{"bucket_name":"demo-assets","visibility":"public"}}'
```

Enregistrer un objet :
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_save","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt","text":"hello from curl"}}'
```

Le recharger :
```bash
curl -sS http://127.0.0.1:8257/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"object_load","params":{"bucket_name":"demo-assets","object_key":"notes/hello.txt"}}'
```

## Points à retenir

- ce pulser est entièrement local et n'a pas besoin d'identifiants cloud
- les payloads sont suffisamment simples pour être compris sans outils supplémentaires
- le backend de stockage peut être ultérieurement remplacé du système de fichiers vers un autre fournisseur tout en maintenant l'interface de pulse stable

## Créez le vôtre

Si vous souhaitez le personnaliser :

1. copiez `file-storage.pulser`
2. modifiez les ports et le `root_path` de stockage
3. conservez la même pulse surface si vous souhaitez une compatibilité avec le workbench et les exemples existants
