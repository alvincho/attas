# Attas Data Services

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

## Couverture

Les tables actuelles de l'ensemble de données normalisées sont :

- `ads_security_master`
- `ads_daily_price`
- `ads_fundamentals`
- `ads_financial_statements`
- `ads_news`
- `ads_sec_companyfacts`
- `ads_sec_submissions`
- `ads_raw_data

Le dispatcher gère également :

- `ads_jobs`
- `ads_worker_capabilities`

L'implémentation utilise des préfixes de table `ads_` plutôt que des noms littéraux `ads-*`, afin que les mêmes identifiants fonctionnent proprement sur SQLite, Postgres et SQL basé sur Supabase.

## Forme d'exécution

Dispatcher :

- est un agent `prompits`
- possède la file d'attente partagée et les tables de stockage normalisées
- expose `ads-submit-job`, `arg-get-job`, `ads-register-worker` et `ads-post-job-result`
- remet aux workers une charge utile `JobDetail` typée lorsqu'ils réclament du travail
- accepte une charge utile `JobResult` typée pour finaliser les tâches et persister les lignes collectées ainsi que les charges utiles brutes

Worker :

- est un agent `prompits`
- annonce ses capacités via les métadonnées de l'agent et la table des capacités du dispatcher
- charge les `job_capabilities` depuis la configuration et enregistre ces noms de capacité dans les métadonnées Plaza
- utilise des objets `JobCap` comme chemin d'exécution par défaut pour les tâches réclamées
- peut s'exécuter une seule fois ou dans une boucle de polling, avec un intervalle par défaut de 10 secondes
- accepte soit un `process_job()` surchargé, soit un callback de gestion externe

Pulser :

- est un pulser `phemacast`
- lit les tables ADS normalisées depuis le pool partagé
- expose des pulses pour le security master, les prix quotidiens, les fondamentaux, les états financiers, les actualités et la recherche de charge utile brute

## Fichiers

- `ads/agents.py`: agents de répartition et agents travailleurs
- `ads/jobcap.py`: abstraction `JobCap` et chargeur de capacités basé sur des callables
- `ads/models.py`: `JobDetail` et `JobResult`
- `ads/pulser.py`: implémentation du pulser ADS
- `ads/boss.py`: agent d'interface utilisateur boss operator
- `ads/practices.py`: pratiques de répartition
- `ads/schema.py`: schémas de tables partagés
- `ads/iex.py`: capacité de tâche de fin de journée IEX
- `ads/twse.py`: capacité de tâche de fin de journée de la Bourse de Taïwan
- `ads/rss_news.py`: capacité de collecte de flux RSS multi-sources
- `capacité de importation massive de données brutes SEC EDGAR et mappage par entreprise : `ads/sec.py`
- `ads/us_listed.py`: capacité de master des titres cotés aux États-Unis de Nasdaq Trader
- `ads/yfinance.py`: capacité de tâche de fin de journée Yahoo Finance
- `ads/runtime.py`: utilitaires de normalisation
- `ads/configs/*.agent`: exemples de configurations ADS
- `ads/sql/ads_tables.sql`: DDL Postgres/Supabase

## Exemples locaux

Les configurations ADS fournies supposent désormais une base de données PostgreSQL partagée. Définissez
`POSTGRES_DSN` ou `DATABASE_URL` avant de démarrer les agents. Vous pouvez optionnellement
définir `ADS_POSTGRES_SCHEMA` pour utiliser un schéma autre que `public`, et
`ADS_POSTGRES_SSLMODE` pour remplacer le comportement `disable` par défaut (adapté au local)
lorsque vous avez besoin de SSL pour un PostgreSQL managé.

Démarrez le dispatcher :
```bash
python3 prompits/create_agent.py --config ads/configs/dispatcher.agent
```

Démarrer un worker :
```bash
python3 prompits/create_agent.py --config ads/configs/worker.agent
```

La configuration d'exemple du worker inclut une capacité en direct `US Listed Sec to security master` basée sur `ads.us_listed:USListedSecJobCap`, des gestionnaires simulés pour `fundamentals`, `financial_statements` et `news`, et utilise `ads.sec:USFilingBulkJobCap` nommé `US Filing Bulk`, `ads.sec:USFilingMappingJobCap` nommé `US Filing Mapping`, `ads.yfinance:YFinanceEODJobCap` nommé `YFinance EOD`, `ads.yfinance:YFinanceUSMarketEODJobCap` nommé `YFinance US Market EOD`, ainsi que `ads.twse:TWSEMarketEODJobCap` nommé `TWSE Market EOD` pour la collecte quotidienne de fin de journée, et `ads.rss_news:RSSNewsJobCap` nommé `RSS News` pour la collecte de nouvelles multi-flux. `YFinance EOD` utilise le module `yfinance` installé et ne nécessite pas de clé API séparée. `YFinance US Market EOD` scanne `ads_security_master` pour les symboles `USD` actifs, les trie par `metadata.yfinance.eod_at`, met à jour cet horodatage symbole par symbole, et met en file d'attente des tâches `YFinance EOD` d'un seul symbole afin que les noms les plus anciens soient rafraîchis en premier. `TWSE Market EOD` lit le rapport quotidien des cotations `MI_INDEX` officiel de la TWSE et stocke la table complète des cotations du marché dans des lignes normalisées `ads_daily_</strong>price`. Lorsque `ads_daily_price` est vide, il initialise par défaut une fenêtre récente courte au lieu de tenter un remplissage complet du marché sur plusieurs années ; utilisez un `start_date` explicite si vous souhaitez une couverture historique TWSE. `USListedSecJobCap` lit les fichiers de répertoire de symboles Nasdaq Trader `nasdaqlisted.txt` et `otherlisted.txt`, préfère les copies hébergées sur le web `https://www.nasdaqtrader.com/dynamic/SymDir/` avec repli FTP, filtre les symboles de test, et met à jour l'univers actuel des cotations américaines dans `ads_security_master`. `RSS News` récupère les flux configurés SEC, CFTC et BLS en une seule tâche et stocke les entrées de flux normalisées dans `ads_news`. `US Filing Bulk` télécharge l'EDGAR de la SEC chaque nuit
les archives `companyfacts.zip` et `submissions.zip`, écrit les lignes JSON brutes par entreprise dans `ads_sec_companyfacts` et `ads_sec_submissions`, et envoie un en-tête `User-Agent` de la SEC déclaré. `US Filing Mapping` lit une entreprise à partir de ces tables SEC brutes et la mappe dans `ads_fundamentals` ainsi que `ads_financial_statements` lorsqu'un symbole est disponible dans les métadonnées de submissions.
Démarrez le pulser :
```bash
python3 prompits/create_agent.py --config ads/configs/pulser.agent
```

Démarrez l'interface utilisateur de boss :
```bash
python3 prompits/create_agent.py --config ads/configs/boss.agent
```

L'interface utilisateur de boss inclut désormais une barre de connexion en direct Plaza en haut de la page,
une page `Issue Job`, une vue `/monitor` pour parcourir les tâches ADS en attente, réclamées,
terminées et échouées, ainsi que leurs enregistrements de charge utile brute, et une
page `Settings` pour les paramètres par défaut du dispatcher côté boss et les préférences de rafraîchissement du moniteur.

## Notes
- Les configurations d'exemple fournies utilisent `PostgresPool`, de sorte que le dispatcher, les workers, le pulser et le boss pointent tous vers la même base de données ADS au lieu de fichiers SQLite par agent.
- `PostgresPool` résout les paramètres de connexion à partir de `POST</strong>GRES_DSN`, `DATABASE_URL`, `SUPABASE_DB_URL` ou des variables d'environnement standard libpq `PG*`.
- `ads/configs/boss.agent`, `ads/configs/dispatcher.agent` et `ads/configs/worker.agent` doivent rester alignés lors de l'introduction de nouveaux JobCaps ; les configurations fournies exposent `US Listed Sec to security master`, `US Filing Bulk`, `US Filing Mapping`, `YFinance EOD`, `YFinance US Market EOD`, `TWSE Market EOD` et `RSS News`.
- Les configurations des workers peuvent déclarer des entrées `ads.job_capabilities` avec un nom de capacité et un chemin appelable tel que `ads.examples.job_caps:mock_daily_price_cap`.
- Les configurations des workers peuvent également déclarer des capacités basées sur des classes avec `type`, par exemple `ads.iex:IEXEODJobCap`, `ads.rss_news:RSSNewsJobCap`, `ads.sec:USFilingBulkJobCap`, `ads.sec:USFilingMappingJobCap`, `ads.twse:TWSEMarketEODJobCap`, `ads.us_listed:USListedSecJobCap` ou `ads.yfinance:YFinanceEODJobCap`, qui renvoient des lignes normalisées ainsi que des payloads bruts pour la persistance du dispatcher.
- Les entrées `ads.job_capabilities` du worker supportent `disabled: true` pour désactiver temporairement un job cap configuré sans supprimer son entrée de configuration.
- Les configurations des workers peuvent définir `ads.yfinance_request_</strong>cooldown_sec` (par défaut `120`) afin qu'un worker arrête temporairement de proposer les capacités liées à YFinance après une réponse de limitation de débit Yahoo.
- `ads/sql/ads_tables.sql` est inclus pour les déploiements Postgres ou Supabase.
- Le dispatcher et le worker utilisent par défaut un jeton direct local partagé afin que les appels `UsePractice(...)` distants fonctionnent sur une seule machine même avant que l'authentification Plaza ne soit configurée.
- Les trois composants respectent les conventions existantes du dépôt, ils peuvent donc toujours participer à l'enregistrement Plaza et aux appels distants `UsePractice(...)` lorsqu'ils sont configurés pour le faire.
