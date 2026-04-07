# Retis Financial Intelligence Workspace

## Uebersetzungen

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

## Status

Dieses Repository wird aktiv entwickelt und befindet sich noch in der Entwicklung. APIs, Konfigurationsformate und Beispielabläufe können sich ändern, wenn die Projekte aufgeteilt, stabilisiert oder formeller verpackt werden.

Zwei Bereiche befinden sich in einem besonders frühen Stadium und werden sich während der aktiven Entwicklung wahrscheinlich schnell ändern:

- `prompits.teamwork`
- `phemacast` `BossPulser`

Das öffentliche Repository ist gedacht für:

- lokale Entwicklung
- Evaluierung
- Prototyp-Workflows
- Architektur-Exploration

Es ist noch kein fertiges Produkt oder eine Produktionsbereitstellung mit nur einem Befehl.

## Schneller Start mit einem frischen Clone

Von einem brandneuen Checkout aus:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

Das smoke-Skript klont den committeten Repo-Status in ein temporäres Verzeichnis, erstellt seine eigene virtualenv, installiert Abhängigkeiten und führt eine fokussierte, öffentlich ausgerichtete Testsuite aus. Dies ist die genaueste Annäherung an das, was ein GitHub-Nutzer tatsächlich herunterladen wird.

Wenn Sie stattdessen Ihre neuesten nicht committeten lokalen Änderungen testen möchten, verwenden Sie:
```bash
attas_smoke --worktree
```

Dieser Modus kopiert den aktuellen Working Tree, einschließlich nicht committeter Änderungen und nicht verfolgter, nicht ignorierter Dateien, in das temporäre Testverzeichnis.

Vom Repo-Root aus können Sie auch ausführen:
```bash
bash attas_smoke
```

Von jedem Unterverzeichnis innerhalb des Repository-Baums aus können Sie ausführen:
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

Dieser Launcher findet die Root des Repositories und startet denselben Smoke-Test-Ablauf. Wenn Sie `attas_smoke` per Symlink in ein Verzeichnis Ihres `PATH` einbinden, können Sie ihn auch von überall aus als wiederverwendbaren Befehl aufrufen und optional `FINMAS_REPO_ROOT` festlegen, wenn Sie außerhalb des Repository-Baums arbeiten.

## Local-First Quickstart

Der sicherste lokale Pfad ist heute der Prompits-Beispiel-Stack. Er erfordert kein Supabase oder andere private Infrastruktur und verfügt nun über einen Ein-Befehl-Local-Bootstrap-Flow für den Baseline-Desk-Stack. Der Python-Launcher funktioniert nativ auf Windows, Linux und macOS. Verwenden Sie `python3` auf macOS/Linux und `py -3` auf Windows:
```bash
python3 -m prompits.cli up desk
```

Dies startet:

- Plaza auf `http://127.0.0.1:8211`
- den Baseline-Worker auf `http://127.0.0.1:8212`
- das browserbasierte Benutzer-UI auf `http://127.0.0.1:8214/`

Sie können auch das Wrapper-Skript verwenden:
```bash
bash run_plaza_local.sh
```

Nützliche Folgebefehle:
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

Wenn Sie den älteren manuellen Ablauf benötigen, um jeweils einen einzelnen Dienst zu debuggen:
```bash
python3 -m prompits.create_agent --config prompits/examples/plaza.agent
python3 -m prompits.create_agent --config prompits/examples/worker.agent
python3 -m prompits.create_agent --config prompits/examples/user.agent
```

Wenn Sie das ältere, auf Supabase basierende Plaza-Setup verwenden möchten, zeigen Sie `PROMPITS_AGENT_CONFIG` auf
`attas/configs/plaza.agent` und geben Sie die erforderlichen Umgebungsvariablen an.

## Remote-Practice-Richtlinie und Audit

Prompits unterstützt jetzt eine dünne Cross-Agent-Richtlinien- und Audit-Schicht für Remote-`UsePractice(...)`-Aufrufe. Der Vertrag befindet sich in der Agent-Config-JSON auf der obersten Ebene und wird nur innerhalb von `prompits` verwendet:
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

Richtlinienhinweise:

- `outbound`-Regeln gleichen das Ziel unter Verwendung von `practice_id`, `target_agent_id`, `target_name`, `target_address`, `target_role` und `target_pit_type` ab.
- `inbound`-Regeln gleichen den Aufrufer unter Verwendung von `practice_id`, `caller_agent_id`, `caller_name`, `caller_address`, `auth_mode` und `plaza_url` ab.
- Verweigerungsregeln haben Vorrang; wenn eine Allow-Liste existiert, muss ein Remote-Aufruf mit dieser übereinstimmen, andernfalls wird er mit `403` abgelehnt.
- Audit-Zeilen werden protokolliert und, wenn der Agent über einen Pool verfügt, mit einer gemeinsamen `request_id` an die konfigurierte Audit-Tabelle angehängt, um eine Korrelation zwischen Anfrage- und Ergebnisereignissen zu ermöglichen.

## Repository-Struktur
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

## Orientierung

- Beginnen Sie mit `prompts/README.md` für das Kern-Runtime-Modell.
- Lesen Sie `phemacast/README.md` für die Content-Pipeline-Ebene.
- Lesen Sie `attas/README.md` für das Finance-Network-Framing und übergeordnete Konzepte.
- Lesen Sie `ads/README.md` für die Data-Service-Komponenten.

## Komponentenstatus

| Bereich | Aktueller öffentlicher Status | Hinweise |
| --- | --- | --- |
| `prompits` | Bester Startpunkt | Local-first-Beispiele und die Core-Runtime sind der einfachste öffentliche Einstiegspunkt. Das Paket `prompits.teamwork` befindet sich noch in einem frühen Stadium und kann sich schnell ändern. |
| `attas` | Frühe Veröffentlichung | Kernkonzepte und User-Agent-Arbeiten sind öffentlich, aber einige unfertige Komponenten werden im Standard-Workflow absichtlich ausgeblendet. |
| `phemacast` | Frühe Veröffentlichung | Der Kern-Pipeline-Code ist öffentlich; einige Reporting-/Rendering-Komponenten werden noch bereinigt und stabilisiert. `BossPulser` befindet sich noch in aktiver Entwicklung. |
| `ads` | Fortgeschritten | Nützlich für Entwicklung und Forschung, aber einige Daten-Workflows erfordern eine zusätzliche Einrichtung und sind kein Pfad für die Erstausführung. |
| `deploy/` | Nur Beispiele | Deployment-Helfer sind umgebungsspezifisch und sollten nicht als ausgereifte öffentliche Deployment-Lösung betrachtet werden. |
| `mcp_servers/` | Öffentlicher Quellcode | Lokale MCP-Server-Implementierungen sind Teil des öffentlichen Quellcode-Baums. |

## Bekannte Einschränkungen

- Einige Workflows setzen weiterhin optionale Umgebungsvariablen oder Drittanbieterdienste voraus.
- `tests/storage/` enthält nützliche Fixtures, vermischt aber immer noch deterministische Testdaten mit einem veränderlicheren lokalen Zustand als ein ideales öffentliches Fixture-Set.
- Deployment-Skripte sind Beispiele und keine unterstützte Produktionsplattform.
- Das Repository entwickelt sich schnell weiter, daher können sich einige Konfigurationen und Modulgrenzen ändern.

## Roadmap

Die kurzfristige öffentliche Roadmap wird in `docs/ROADMAP.md` verfolgt.

Geplante `prompits`-Funktionen umfassen authentifizierte und berechtigte `UsePractice(...)`-Aufrufe zwischen Agenten, mit Kostenverhandlung und Zahlungsabwicklung vor der Ausführung.

Geplante `phemacast`-Funktionen umfassen reichhaltigere `Phemar`-Darstellungen menschlicher Intelligenz, breitere `Castr`-Ausgabeformate und KI-generierte `Pulse`-Verfeinerung basierend auf Feedback, Effizienz und Kosten, sowie eine erweiterte Diagrammunterstützung in `MapPhemar`.

Geplante `attas`-Funktionen um

umfassen kollaborativere Investment- und Treasury-Workflows, auf Finanzexperten abgestimmte Agentenmodelle und ein automatisches API-Endpoint-zu-`Pulse`-Mapping für Anbieter und Dienstleister.

## Hinweise zum öffentlichen Repository

- Geheimnisse sollten aus Umgebungsvariablen und lokalen Konfigurationen stammen, nicht aus committeten Dateien.
- Lokale Datenbanken, Browser-Artefakte und temporäre Snapshots sind absichtlich vom Versionskontrollsystem ausgeschlossen.
- Der Codebase zielt derzeit eher auf lokale Entwicklungs-, Evaluierungs- und Prototyping-Workflows ab als auf eine polierte Auslieferung für Endbenutzer.

## Mitwirken

Dies ist derzeit ein öffentliches Repository mit einem einzigen Hauptwart. Issues und Pull Requests sind willkommen, aber die Roadmap und Merge-Entscheidungen werden vorerst vom Wartenden bestimmt. Siehe `CONTRIBUTING.md` für den aktuellen Workflow.

## Lizenz

Dieses Repository ist unter der Apache License 2.0 lizenziert. Den vollständigen Text finden Sie in `LICENSE`.
