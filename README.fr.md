# Retis Financial Intelligence Workspace

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

## État

Ce dépôt est en cours de développement actif et continue d'évoluer. Les API, les formats de configuration et les flux d'exemples peuvent changer à mesure que les projets sont divisés, stabilisés ou emballés de manière plus formelle.

Deux domaines sont particulièrement précoces et susceptibles de changer rapidement pendant leur développement actif :

- `prompits.teamwork`
- `phemacast` `BossPulser`

Le dépôt public est destiné à :

- le développement local
- l'évaluation
- les flux de travail de prototype
- l'exploration de l'architecture

Il ne s'agit pas encore d'un produit fini prêt à l'emploi ou d'un déploiement de production en une seule commande.

## Démarrage rapide d'un nouveau clone

À partir d'un tout nouveau checkout :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

Le script smoke clone l'état du dépôt validé dans un répertoire temporaire, crée son propre virtualenv, installe les dépendances et exécute une suite de tests orientée vers le public. C'est l'approximation la plus proche de ce qu'un utilisateur GitHub téléchargera réellement.

Si vous souhaitez plutôt tester vos derniers changements locaux non validés, utilisez :
```bash
attas_smoke --worktree
```

Ce mode copie l'arbre de travail actuel, y compris les modifications non validées et les fichiers non suivis non ignorés, dans le répertoire de test temporaire.

Depuis la racine du dépôt, vous pouvez également exécuter :
```bash
bash attas_smoke
```

Depuis n'importe quel sous-répertoire à l'intérieur de l'arborescence du dépôt, vous pouvez exécuter :
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

Ce lanceur trouve la racine du dépôt et démarre le même flux de smoke test. Si vous créez un lien symbolique vers `attas_smoke` dans un répertoire de votre `PATH`, vous pouvez également l'appeler comme une commande réutilisable de n'importe où et, en option, définir `FINMAS_REPO_ROOT` lorsque vous travaillez en dehors de l'arborescence du dépôt.

## Démarrage rapide Local-First

Le chemin local le plus sûr aujourd'hui est la pile d'exemple Prompits. Elle ne nécessite pas Supabase ou d'autres infrastructures privées, et dispose désormais d'un flux de bootstrap local en une seule commande pour la pile de bureau de base. Le lanceur Python fonctionne nativement sur Windows, Linux et macOS. Utilisez `python3` sur macOS/Linux et `py -3` sur Windows :
```bash
python3 -m prompits.cli up desk
```

Ceci démarre :

- Plaza sur `http://127.0.0.1:8211`
- le worker de base sur `http://127.0.0.1:8212`
- l'interface utilisateur côté navigateur sur `http://127.0.0.1:8214/`

Vous pouvez également utiliser le script wrapper :
```bash
bash run_plaza_local.sh
```

Commandes de suivi utiles :
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

Si vous avez besoin de l'ancien flux manuel pour déboguer un seul service à la fois :
```bash
python3 -m prompits.create_agent --config prompits/examples/plaza.agent
python3 -m prompits.create_agent --config prompits/examples/worker.agent
python3 -m prompits.create_agent --config prompits/examples/user.agent
```

Si vous souhaitez l'ancienne configuration Plaza basée sur Supabase, pointez `PROMPIT_AGENT_CONFIG` vers
`attas/configs/plaza.agent` et fournissez les variables d'environnement requises.

## Politique et audit de pratique à distance

Prompits prend désormais en charge une couche légère de politique et d'audit multi-agents pour les appels distants `UsePractice(...)`. Le contrat réside dans le JSON de configuration de l'agent au niveau supérieur et n'est consommé qu'à l'intérieur de `prompits` :
```json
{
  "remote_use_practice_policy": {
    "outbound_default": "allow",
    "inbound_default": "allow",
    "outbound": {
      "deny": [
        { "practice_id": "get_pulse_data", "target_address": "http://127.0.0.1:9999" }
      ]
    },
    "inbound": {
      "allow": [
        { "practice_id": "get_pulse_data", "caller_agent_id": "plaza" }
      ]
    }
  },
  "remote_use_practice_audit": {
    "enabled": true,
    "persist": true,
    "emit_logs": true,
    "table_name": "cross_agent_practice_audit"
  }
}
```

Notes sur la politique :

- Les règles `outbound` correspondent à la destination en utilisant `practice_id`, `target_agent_id`, `target_name`, `target_address`, `target_role` et `target_pit_type`.
- Les règles `inbound` correspondent à l'appelant en utilisant `practice`, `caller_agent_id`, `caller_name`, `caller_address`, `auth_mode` et `plaza_url`.
- Les règles de refus sont prioritaires ; si une liste d'autorisation existe, un appel distant doit correspondre à celle-ci, sinon il est rejeté avec une erreur `403`.
- Les lignes d'audit sont journalisées et, lorsque l'agent dispose d'un pool, elles sont ajoutées à la table d'audit configurée avec un `request_id` partagé pour la corrélation entre les événements de requête et de résultat.

## Structure du dépôt
```text
attas/       Finance-oriented agent, pulse, and personal-agent work
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## Orientation

- Commencez par `prompts/README.md` pour le modèle d'exécution principal.
- Lisez `phemacast/README.md` pour la couche de pipeline de contenu.
- Lisez `attas/README.md` pour le cadrage du réseau financier et les concepts de haut niveau.
- Lisez `ads/README.md` pour les composants du service de données.

## État des Composants

| Zone | État Public Actuel | Notes |
| --- | --- | --- |
| `prompits` | Meilleur point de départ | Les exemples "local-first" et le runtime de base sont le point d'entrée public le plus simple. Le package `prompits.teamwork` est encore en phase précoce et peut changer rapidement. |
| `attas` | Public précoce | Les concepts de base et le travail sur l'user-agent sont publics, mais certains composants inachevés sont intentionnellement cachés du flux par défaut. |
| `phemacast` | Public précoce | Le code du pipeline principal est public ; certains composants de reporting/rendu sont encore en cours d'ajustement et de stabilisation. `BossPulser` est toujours en développement actif. |
| `ads` | Avancé | Utile pour le développement et la recherche, mais certains flux de données nécessitent une configuration supplémentaire et ne constituent pas un chemin de premier lancement. |
| `deploy/` | Exemple uniquement | Les assistants de déploiement sont spécifiques à l'environnement et ne doivent pas être considérés comme une solution de déploiement public aboutie. |
| `mcp_servers/` | Source publique | Les implémentations locales de serveurs MCP font partie de l'arborescence du code source public. |

## Limitations connues

- Certains flux de travail supposent encore des variables d'environnement optionnelles ou des services tiers.
- `tests/storage/` contient des fixtures utiles, mais mélange encore des données de test déterministes avec un état de style local plus mutable qu'un ensemble de fixtures publics idéal.
- Les scripts de déploiement sont des exemples, et non une plateforme de production prise en charge.
- Le dépôt évolue rapidement, donc certaines configurations et limites de modules peuvent changer.

## Feuille de route

La feuille de route publique à court terme est suivie dans `docs/ROADMAP.md`.

Les capacités prévues de `prompits` incluent des appels `UsePractice(...)` authentifiés et autorisés entre agents, avec négociation des coûts et gestion des paiements avant l'exécution.

Les capacités prévues de `phemacast` incluent des représentations de l'intelligence humaine `Phemar` plus riches, des formats de sortie `Castr` plus larges et un raffinement de `Pulse` généré par l'IA basé sur les retours, l'efficacité et le coût, ainsi qu'une prise en charge plus large des diagrammes dans `MapPhemar`.

Les capacités prévues de `attas` incluent des flux de travail d'investissement et de trésorerie plus collaboratifs, des modèles d'agents ajustés pour les professionnels de la finance, et un mappage automatique des points de terminaison API vers `Pulse` pour les fournisseurs et prestataires de services.

## Notes du Repo Public

- Les secrets doivent provenir des variables d'environnement et de la configuration locale, et non de fichiers commités.
- Les bases de données locales, les artefacts du navigateur et les instantanés temporaires sont intentionnellement exclus du contrôle de version.
- La base de code cible actuellement davantage les flux de travail de développement local, d'évaluation et de prototypage que l'empaquetage fini pour l'utilisateur final.

## Contribuer

Il s'agit actuellement d'un dépôt public avec un seul mainteneur principal. Les issues et les pull requests sont les bienvenues, mais la feuille de route et les décisions de fusion restent dirigées par le mainteneur pour le moment. Consultez `CONTRIBUTING.md` pour connaître le flux de travail actuel.

## Licence

Ce dépôt est sous licence Apache License 2.0. Voir le fichier `LICENSE` pour le texte complet.
