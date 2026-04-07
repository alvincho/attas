# Démo YFinance Pulser

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

- `plaza.agent` : Plaza local pour cette démo
- `yfinance.pulser` : configuration de démo locale pour `YFinancePulser`
- `start-plaza.sh` : lancer Plaza
- `start-pulser.sh` : lancer le pulser
- `run-demo.sh` : lancer la démo complète depuis un seul terminal et ouvrir le guide du navigateur ainsi que l'interface utilisateur du pulser

## Lancement en une seule commande

Depuis la racine du dépôt :
```bash
./demos/pulsers/yfinance/run-demo.sh
```

Ceci lance Plaza et `YFinancePulser` à partir d'un seul terminal, ouvre une page de guide dans le navigateur et ouvre automatiquement l'interface utilisateur de pulser.

Définissez `DEMO_OPEN_BROWSER=0` si vous voulez que le lanceur reste uniquement dans le terminal.

## Démarrage rapide de la plateforme

### macOS et Linux

Depuis la racine du dépôt :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
./demos/pulsers/yfinance/run-demo.sh
```

### Windows

Utilisez un environnement Python natif Windows. Depuis la racine du dépôt dans PowerShell :
```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m scripts.demo_launcher yfinance
```

Si les onglets du navigateur ne s'ouvrent pas automatiquement, laissez le lanceur en cours d'exécution et ouvrez l'URL `guide=` imprimée dans un navigateur Windows.

## Démarrage rapide

Ouvrez deux terminaux à partir de la racine du dépôt.

### Terminal 1 : démarrer Plaza
```bash
./demos/pulsers/yfinance/start-plaza.sh
```

Résultat attendu :

- Plaza démarre sur `http://127.0.0.1:8251`

### Terminal 2 : lancer le pulser
```bash
./demos/pulsers/yfinance/start-pulser.sh
```

Résultat attendu :

- le pulser démarre sur `http://127.0.0.1:8252`
- il s'enregistre auprès de Plaza sur `http://127.0.0.1:8251`

Note :

- ce démo nécessite un accès Internet sortant car le pulser récupère des données en direct via `yfinance`
- Yahoo Finance peut limiter le débit ou rejeter par intermittence les requêtes

## Essayez dans le navigateur

Ouvrir :

- `http://12:0.0.1:8252/`

Premiers pulses suggérés :

1. `last_price`
2. `company_profile`
3. `ohlc_bar_series`

Paramètres suggérés pour `last_price` :
```json
{
  "symbol": "AAPL"
}
```

Paramètres suggérés pour `ohlc_bar_series` :
```json
{
  "symbol": "AAPL",
  "interval": "1d",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31"
}
```

## Essayez avec Curl

Demande de cotation :
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"last_price","params":{"symbol":"AAPL"}}'
```

Demande de série OHLC :
```bash
curl -sS http://127.0.0.1:8252/api/test-pulse \
  -H 'Content-Type: application/json' \
  -d '{"pulse_name":"ohlc_bar_series","params":{"symbol":"AAPL","interval":"1d","start_date":"2026-01-01","end_date":"2026-03-31"}}'
```

## Ce qu'il faut retenir

- le même pulser expose à la fois des pulses de type snapshot et de type time-series
- `ohlc_bar_series` est compatible avec le workbench chart demo et le pulser du chemin technical-analysis
- le live provider peut être modifié ultérieurement en arrière-plan tandis que le pulse contract reste le même

## Créez le vôtre

Si vous souhaitez étendre cette démo :

1. copiez `yfinance.pulser`
2. ajustez les ports et les chemins de stockage
3. modifiez ou ajoutez des définitions de pulse prises en charge si vous souhaitez un catalogue plus restreint ou plus spécialisé
