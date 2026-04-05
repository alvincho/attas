# Workspace Retis per l'intelligenza finanziaria

## Traduzioni

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

Questo repository è un workspace multi-agente per sistemi di intelligenza finanziaria.

Per saperne di più visita [retis.ai](https://retis.ai) e la pagina prodotto di Attas su [retis.ai/products/attas](https://retis.ai/products/attas).

Il repository riunisce attualmente diverse codebase correlate:

- `prompits`: infrastruttura Python per agenti nativi HTTP, discovery di Plaza, pool ed esecuzione remota di practices
- `phemacast`: una pipeline collaborativa di contenuti costruita su Prompits
- `attas`: pattern di agenti orientati alla finanza e definizioni di Pulse di livello superiore
- `ads`: componenti di servizio e raccolta dati che alimentano dataset finanziari normalizzati nel sistema più ampio

## Stato

Questo repository è in fase di attivo sviluppo e in continua evoluzione. Le API, i formati di configurazione e i flussi di esempio possono cambiare man mano che i progetti vengono suddivisi, stabilizzati o confezionati in modo più formale.

Due aree sono in una fase particolarmente iniziale e probabilmente cambieranno rapidamente durante lo sviluppo attivo:

- `prompits.teamwork`
- `phemacast` `BossPulser`

Il repository pubblico è destinato a:

- sviluppo locale
- valutazione
- flussi di lavoro prototipali
- esplorazione dell'architettura

Non è ancora un prodotto rifinito pronto all'uso o un deployment di produzione con un singolo comando.

## Avvio rapido di un nuovo clone

Da un checkout completamente nuovo:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

Lo script smoke clona lo stato del repo confermato in una directory temporanea, crea il proprio virtualenv, installa le dipendenze ed esegue una suite di test focalizzata sul pubblico. Questa è l'approssimazione più vicina a ciò che un utente di GitHub scaricherà effettivamente.

Se invece desideri testare le tue ultime modifiche locali non confermate, usa:
```bash
attas_smoke --worktree
```

Quella modalità copia l'albero di lavoro corrente, incluse le modifiche non confermate e i file non tracciati non ignorati, nella directory di test temporanea.

Dalla radice del repository, è possibile eseguire anche:
```bash
bash attas_smoke
```

Da qualsiasi sottodirectory all'interno dell'albero del repository, è possibile eseguire:
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

Quel launcher trova la radice del repository e avvia lo stesso flusso di smoke test. Se crei un symlink di `attas_smoke` in una directory del tuo `PATH`, puoi anche chiamarlo come comando riutilizzabile da qualsiasi luogo e, opzionalmente, impostare `FINMAS_REPO_ROOT` quando lavori al di fuori dell'albero del repository.

## Avvio rapido Local-First

La strada locale più sicura oggi è lo stack di esempio Prompits. Non richiede Supabase o altre infrastrutture private, e ora dispone di un flusso di bootstrap locale con un singolo comando per lo stack desktop di base:
```bash
python3 -m prompits.cli up desk
```

Questo avvia:

- Plaza su `http://127.0.0.1:8212`
- il worker di base su `http://127.0.0.1:8212`
- l'interfaccia utente per il browser su `http://127.0.0.1:8214/`

È possibile utilizzare anche lo script wrapper:
```bash
bash run_plaza_local.sh
```

Comandi di follow-up utili:
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

Se hai bisogno del vecchio flusso manuale per il debug di un singolo servizio alla volta:
```bash
python3 prompits/create_agent.py --config prompits/examples/plaza.agent
python3 prompits/create_agent.py --config prompits/examples/worker.agent
python3 prompits/create_agent.py --config prompits/examples/user.agent
```

Se desideri la vecchia configurazione di Plaza basata su Supabase, punta `PROMPITS_AGENT_CONFIG` a
`attas/configs/plaza.agent` e fornisci le variabili d'ambiente richieste.

## Politica e audit della pratica remota

Prompits ora supporta un sottile livello di policy e audit cross-agent per le chiamate remote `UsePractice(...)`. Il contratto risiede nel JSON di configurazione dell'agente al livello superiore e viene consumato solo all'interno di `prompits`:
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

Note sulla policy:

- Le regole `outbound` corrispondono alla destinazione utilizzando `practice_id`, `target_agent_id`, `target_name`, `target_address`, `target_role` e `target_pit_type`.
- Le regole `inbound` corrispondono al chiamante utilizzando `practice_id`, `caller_agent_id`, `caller_name`, `caller_address`, `auth_mode` e `plaza_url`.
- Le regole di diniego hanno la precedenza; se esiste una whitelist, una chiamata remota deve corrispondere ad essa o verrà rifiutata con un errore `403`.
- Le righe di audit vengono registrate e, quando l'agent dispone di un pool, vengono aggiunte alla tabella di audit configurata con un `request_id` condiviso per la correlazione tra gli eventi di richiesta e di risultato.

## Struttura del repository
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

## Orientamento

- Inizia con `prompits/README.md` per il modello di runtime principale.
- Leggi `phemacast/README.md` per lo strato della pipeline dei contenuti.
- Leggi `attas/README.md` per l'inquadramento della rete finanziaria e i concetti di alto livello.
- Leggi `ads/README.md` per i componenti del servizio dati.

## Stato dei Componenti

| Area | Stato Pubblico Attuale | Note |
| --- | --- | --- |
| `prompits` | Miglior punto di partenza | Gli esempi "local-first" e il runtime principale sono il punto di ingresso pubblico più semplice. Il pacchetto `prompits.teamwork` è ancora in una fase iniziale e potrebbe cambiare rapidamente. |
| `attas` | Pubblico iniziale | I concetti fondamentali e il lavoro sull'agente utente sono pubblici, ma alcuni componenti non terminati sono intenzionalmente nascosti dal flusso predefinito. |
| `phemacast` | Pubblico iniziale | Il codice della pipeline principale è pubblico; alcuni componenti di reporting/rendering sono ancora in fase di rifinitura e stabilizzazione. `BossPulser` è ancora in fase di attivo sviluppo. |
| `ads` | Avanzato | Utile per lo sviluppo e la ricerca, ma alcuni workflow di dati richiedono una configurazione extra e non sono un percorso di prima esecuzione. |
| `deploy/` | Solo esempi | Gli helper di deployment sono specifici dell'ambiente e non devono essere considerati come una soluzione di deployment pubblico rifinita. |
| `mcp_servers/` | Codice sorgente pubblico | Le implementazioni locali dei server MCP fanno parte dell'albero del codice sorgente pubblico. |

## Limitazioni note

- Alcuni workflow presuppongono ancora variabili d'ambiente opzionali o servizi di terze parti.
- `tests/storage/` contiene fixture utili, ma mescola ancora dati di test deterministici con uno stato di tipo locale più mutabile rispetto a un set di fixture pubblici ideale.
- Gli script di deployment sono esempi, non una piattaforma di produzione supportata.
- Il repository si sta evolvendo rapidamente, quindi alcune configurazione e i confini dei moduli potrebbero cambiare.

## Roadmap

La roadmap pubblica a breve termine è tracciata in `docs/ROADMAP.md`.

Le funzionalità pianificate di `prompits` includono chiamate `UsePractice(...)` autenticate e autorizzate tra agenti, con negoziazione dei costi e gestione dei pagamenti prima dell'esecuzione.

Le funzionalità pianificate di `phemacast` includono rappresentazioni dell'intelligenza umana `Phemar` più ricche, formati di output `Castr` più ampi e il raffinamento di `Pulse` generato dall'IA basato su feedback, efficienza e costi, oltre a un supporto più ampio per i diagrammi in `MapPhemar`.

Le funzionalità pianificate di `attas` includono workflow di investimento e tesoreria più collaborativi, modelli di agenti ottimizzati per i professionisti finanziari e il mappaggio automatico degli endpoint API a `Pulse` per fornitori e prestatori di servizi.

## Note del Repository Pubblico

- Si prevede che i segreti provengano da variabili d'ambiente e configurazioni locali, non da file commitati.
- Database locali, artefatti del browser e snapshot temporanei sono intenzionalmente esclusi dal controllo di versione.
- Il codebase attualmente punta alla valutazione, allo sviluppo locale e ai flussi di lavoro di prototipazione, più che a un packaging rifinito per l'utente finale.

## Contribuire

Questo è attualmente un repository pubblico con un unico manutentore principale. Issue e pull request sono benvenuti, ma la roadmap e le decisioni di merge rimangono guidate dal manutentore per ora. Consulta `CONTRIBUTING.md` per l'attuale workflow.

## Licenza

Questo repository è rilasciato sotto la licenza Apache License 2.0. Consulta `LICENSE` per il testo completo.
