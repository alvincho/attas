# Prompits Dispatcher

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

## Pièces incluses

- `DispatcherAgent` : répartiteur de tâches basé sur une file d'attente
- `DispatcherWorkerAgent` : travailleur qui interroge les tâches correspondantes et rapporte les résultats
- `DispatcherBossAgent` : interface utilisateur de navigateur pour émettre des tâches et inspecter l'état d'exécution
- `JobCap` : abstraction de capacité pour des gestionnaires de tâches pluggables
- pratiques partagées, schémas, helpers d'exécution et exemples de configurations

## Tables internes

- `dispatcher_jobs`
- `dispatcher_worker_capabilities`
- `dispatcher_worker_history`
- `dispatcher_job_results`
- `dispatcher_raw_payloads`

Si un worker renvoie des lignes pour une `target_table` concrète et fournit un schéma, le dispatcher peut également créer et persister cette table. Si aucun schéma n'est fourni, les lignes sont stockées de manière générique dans `dispatcher_job_results`.

## Pratiques

- `dispatcher-submit-job`
- `dispatcher-get-job`
- `dispatcher-register-worker`
- `dispatcher-post-job-result`
- `dispatcher-control-job`

## Exemple d'utilisation

Démarrez le dispatcher :
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/dispatcher.agent
```

Démarrer un worker :
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/worker.agent
```

Démarrez l'interface utilisateur de boss :
```bash
python3 prompits/create_agent.py --config prompits/dispatcher/configs/boss.agent
```

La configuration d'exemple du worker utilise une capacité d'exemple minimale de
`prompits.dispatcher.examples.job_caps`.

## Notes

- Le package utilise par défaut un jeton direct local partagé, de sorte que les appels `UsePractice(...)` fonctionnent localement avant que l'authentification Plaza ne soit configurée.
- Les configurations d'exemple utilisent `PostgresPool`, mais les tests couvrent également SQLite.
- Le worker peut annoncer des capacités basées sur des classes ou des fonctions appelables via la section de configuration `dispatcher.job_capabilities`.
