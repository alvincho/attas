# Retis Financial Intelligence Workspace

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

L’obiettivo di `attas` è supportare una rete mondiale di professionisti finanziari connessi. Ogni partecipante può gestire il proprio agente, condividere competenze tramite quell’agente e allo stesso tempo proteggere la propria proprietà intellettuale. In questo modello, prompt privati, logica di workflow, algoritmi e altri metodi interni rimangono all’interno dell’agente del proprietario. Gli altri partecipanti consumano i risultati e i servizi prodotti, invece di ricevere direttamente la logica sottostante.

## Stato

Questo repository è in fase di attivo sviluppo e in continua evoluzione. Le API, i formati di configurazione e i flussi di esempio possono cambiare man mano che i progetti vengono suddivisi, stabilizzati o confezionati in modo più formale.

Due aree sono in una fase particolarmente iniziale e sono probabili cambiamenti rapidi durante lo sviluppo attivo:

- `prompits.teamwork`
- `phemacast` `BossPulser`

Il repository pubblico è destinato a:

- sviluppo locale
- valutazione
- flussi di lavoro prototipali
- esplorazione dell'architettura

Non è ancora un prodotto finito pronto all'uso o un deployment di produzione con un singolo comando.

## Dove si colloca `attas` per gli sviluppatori

Questo repository ha tre livelli di prodotto:

- `prompits` è il runtime multi-agente generico e il livello di coordinamento Plaza.
- `phemacast` è il livello riutilizzabile di collaborazione sui contenuti costruito su `prompits`.
- `attas` è il livello applicativo finanziario costruito sopra entrambi.

Per gli sviluppatori, `attas` è il luogo in cui deve vivere il lavoro specifico della finanza. Include aspetti come:

- definizioni, mapping, cataloghi ed esempi di validazione di `Pulse` finanziari
- configurazioni di agenti orientate alla finanza, flussi di agenti personali e orchestrazione dei workflow
- briefing, modelli di report e comportamento del prodotto per analisti, team di tesoreria e workflow di investimento
- branding specifico della finanza, impostazioni predefinite e concetti rivolti all’utente

Se una modifica è riutilizzabile per la collaborazione sui contenuti in generale, probabilmente appartiene a `phemacast`. Se riguarda infrastruttura multi-agente generica, probabilmente appartiene a `prompits`. Evita di risolvere il riuso importando `attas` in questi livelli inferiori.

![attas-3-layers-diagram-1.png](static/images/attas-3-layers-diagram-1.png)

## Dove si colloca `phemacast` per gli sviluppatori

`phemacast` è il livello riutilizzabile di collaborazione sui contenuti tra `prompits` e `attas`. Trasforma input dinamici in output di contenuto strutturato tramite un piccolo insieme di concetti di pipeline:

- `Pulse`: un payload di input dinamico o uno snapshot di dati usato durante la generazione dei contenuti. In `phemacast`, un pulse è il dato che riempie un binding, una sezione o uno slot di template.
- `Pulser`: un agente che recupera, calcola o espone dati di pulse. Un pulser annuncia i pulses che può servire ed espone endpoint di practice come `get_pulse_data`.
- `Phema`: un blueprint di contenuto strutturato. Descrive cosa deve essere prodotto, come è organizzato l’output e quali binding di pulse sono necessari.
- `Phemar`: un agente che risolve un `Phema` in un payload statico raccogliendo dati di pulse dai pulsers e inserendo quei dati nella struttura del `Phema`.

Il flusso tipico di `phemacast` è:

1. Un autore definisce o seleziona un `Phema`.
2. Un `Pulser` fornisce gli input di pulse richiesti da quel `Phema`.
3. Un `Phemar` inserisce quei valori di pulse nel blueprint e produce un risultato strutturato.
4. Un `Castr` o un renderer a valle converte quel risultato in markdown, JSON, testo, pagine, slide o altri formati rivolti al pubblico.

Per gli sviluppatori, `phemacast` è il livello giusto per workflow di contenuto riutilizzabili guidati da pulse, logica di rendering condivisa, mappatura dei contenuti basata su diagrammi e agenti di contenuto non specifici della finanza. Se un concetto è specifico di contratti di dati finanziari, cataloghi finanziari o comportamento di prodotto finanziario, dovrebbe restare in `attas`.

## Concetti fondamentali del runtime

Il modello multi-agente di livello inferiore vive in `prompits` ed è riutilizzato da `phemacast` e `attas`.

- `Pit`: la più piccola unità di identità. Contiene metadati come nome, descrizione e informazioni di indirizzo. In pratica, gli agenti di runtime condividono questo modello di identità.
- `Practice`: una capacità montata su un agente. Una practice può esporre route HTTP, supportare l’esecuzione locale e pubblicare metadati per la scoperta.
- `Pool`: il confine di persistenza di un agente. I pool memorizzano elementi come credenziali Plaza, metadati di practice scoperte, memoria locale e altri stati persistenti di runtime.
- `Plaza`: il piano di coordinamento. Gli agenti si registrano su Plaza, ricevono e rinnovano credenziali, pubblicano card ricercabili, inviano heartbeat, scoprono peer e inoltrano messaggi.

Le connessioni tra agenti funzionano di solito così:

1. Un agente parte con uno o più pool e monta le proprie practices.
2. Se non è Plaza stesso, si registra su Plaza e riceve un `agent_id` stabile, una `api_key` persistente e un bearer token a breve durata.
3. L’agente memorizza queste credenziali nel proprio pool primario e compare nella directory ricercabile di Plaza.
4. Altri agenti lo trovano tramite la ricerca di Plaza usando campi come nome, ruolo o practice pubblicizzata.
5. Gli agenti comunicano poi inviando messaggi tramite relay Plaza ed endpoint stile mailbox, oppure invocando direttamente una practice remota con verifica del chiamante.

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

La strada locale più sicura oggi è lo stack di esempio Prompits. Non richiede Supabase o altre infrastrutture private e ora dispone di un flusso di bootstrap locale con un singolo comando per lo stack desktop di base. Il launcher Python funziona nativamente su Windows, Linux e macOS. Usa `python3` su macOS/Linux e `py -3` su Windows:
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
python3 -m prompits.create_agent --config prompits/examples/plaza.agent
python3 -m prompits.create_agent --config prompits/examples/worker.agent
python3 -m prompits.create_agent --config prompits/examples/user.agent
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
attas/       Livello applicativo finanziario: cataloghi di Pulse, briefing, flussi di agenti personali e configurazioni orientate alla finanza
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
- Leggi `docs/CONCEPTS_AND_CLASSES.md` per i dettagli su `Pit`, `Practice`, `Pool`, `Plaza` e sul flusso remoto tra agenti.
- Leggi `phemacast/README.md` per lo strato della pipeline dei contenuti.
- Leggi `attas/README.md` per l'inquadramento della rete finanziaria e i concetti di alto livello.
- Leggi `ads/README.md` per i componenti del servizio dati.

## Stato dei Componenti

| Area | Stato Pubblico Attuale | Note |
| --- | --- | --- |
| `prompits` | Miglior punto di partenza | Gli esempi "local-first" e il runtime principale sono il punto di ingresso pubblico più semplice. Il pacchetto `prompits.teamwork` è ancora nelle fasi iniziali e potrebbe cambiare rapidamente. |
| `attas` | Pubblico precoce | I concetti fondamentali e il lavoro sull'user-agent sono pubblici, ma alcuni componenti non terminati sono intenzionalmente nascosti dal flusso predefinito. |
| `phemacast` | Pubblico precoce | Il codice della pipeline principale è pubblico; alcuni componenti di reporting/rendering sono ancora in fase di rifinitura e stabilizzazione. `BossPulser` è ancora in fase di attivo sviluppo. |
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
- Il codebase attualmente punta più ai flussi di lavoro di sviluppo locale, valutazione e prototipazione che a un packaging rifinito per l'utente finale.

## Contribuire

Questo è attualmente un repository pubblico con un unico manutentore principale. Issue e pull request sono benvenuti, ma la roadmap e le decisioni di merge rimangono guidate dal manutentore per ora. Consulta `CONTITRIBUTING.md` per l'attuale workflow.

## Licenza

Questo repository è rilasciato sotto la licenza Apache License 2.0. Consulta `LICENSE` per il testo completo.
