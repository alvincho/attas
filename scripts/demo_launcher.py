#!/usr/bin/env python3
"""
Single-command launcher for the public demo folders.

This script starts each demo's services in dependency order, opens a browser-facing
guide page, waits for healthy endpoints, and opens the main UI pages when the stack
is ready. The guide page includes a language selector for the localized overview and
links to the full English README rendered as HTML.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from phemacast.personal_agent.doc_pages import render_markdown
except Exception:  # pragma: no cover - fallback for minimal environments
    render_markdown = None


LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("en", "English"),
    ("zh-Hant", "繁體中文"),
    ("zh-Hans", "简体中文"),
    ("es", "Español"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("de", "Deutsch"),
    ("ja", "日本語"),
    ("ko", "한국어"),
]

LANGUAGE_CODES = [code for code, _ in LANGUAGE_OPTIONS]


def localized(
    en: str,
    zh_hant: str,
    zh_hans: str,
    es: str,
    fr: str,
    it: str,
    de: str,
    ja: str,
    ko: str,
) -> dict[str, str]:
    """Create a localized string map for every supported language."""
    return {
        "en": en,
        "zh-Hant": zh_hant,
        "zh-Hans": zh_hans,
        "es": es,
        "fr": fr,
        "it": it,
        "de": de,
        "ja": ja,
        "ko": ko,
    }


UI_STRINGS = {
    "eyebrow": localized(
        "Single-Command Demo Launcher",
        "單指令示範啟動器",
        "单指令演示启动器",
        "Lanzador de demos con un solo comando",
        "Lanceur de démos en une commande",
        "Avvio demo con un solo comando",
        "Demo-Starter mit einem einzigen Befehl",
        "単一コマンドのデモランチャー",
        "단일 명령 데모 실행기",
    ),
    "summaryLabel": localized(
        "Overview",
        "概覽",
        "概览",
        "Resumen",
        "Aperçu",
        "Panoramica",
        "Überblick",
        "概要",
        "개요",
    ),
    "noticeLabel": localized(
        "Runtime Note",
        "執行注意事項",
        "运行提示",
        "Nota de ejecución",
        "Note d'exécution",
        "Nota di esecuzione",
        "Laufzeithinweis",
        "実行時メモ",
        "실행 메모",
    ),
    "stackLabel": localized(
        "Stack Services",
        "堆疊服務",
        "堆栈服务",
        "Servicios de la pila",
        "Services de la pile",
        "Servizi dello stack",
        "Stack-Dienste",
        "スタックのサービス",
        "스택 서비스",
    ),
    "pagesLabel": localized(
        "Opened Pages",
        "開啟頁面",
        "打开页面",
        "Páginas abiertas",
        "Pages ouvertes",
        "Pagine aperte",
        "Geöffnete Seiten",
        "開くページ",
        "열리는 페이지",
    ),
    "environmentLabel": localized(
        "Environment Switches",
        "環境開關",
        "环境开关",
        "Variables de entorno",
        "Variables d'environnement",
        "Variabili d'ambiente",
        "Umgebungsoptionen",
        "環境スイッチ",
        "환경 변수 전환",
    ),
    "runLabel": localized(
        "Launch Command",
        "啟動指令",
        "启动命令",
        "Comando de inicio",
        "Commande de lancement",
        "Comando di avvio",
        "Startbefehl",
        "起動コマンド",
        "실행 명령",
    ),
    "readmeLabel": localized(
        "README Reference",
        "README 參考",
        "README 参考",
        "Referencia README",
        "Référence README",
        "Riferimento README",
        "README-Referenz",
        "README 参照",
        "README 참고",
    ),
    "englishReference": localized(
        "Open English README",
        "開啟英文 README",
        "打开英文 README",
        "Abrir README en inglés",
        "Ouvrir le README anglais",
        "Apri il README in inglese",
        "Englisches README öffnen",
        "英語の README を開く",
        "영문 README 열기",
    ),
    "genericNotesLabel": localized(
        "Launcher Notes",
        "啟動器說明",
        "启动器说明",
        "Notas del lanzador",
        "Notes du lanceur",
        "Note del launcher",
        "Launcher-Hinweise",
        "ランチャーのメモ",
        "런처 메모",
    ),
    "openLabel": localized(
        "Open",
        "開啟",
        "打开",
        "Abrir",
        "Ouvrir",
        "Apri",
        "Öffnen",
        "開く",
        "열기",
    ),
    "copyLabel": localized(
        "Copy",
        "複製",
        "复制",
        "Copiar",
        "Copier",
        "Copia",
        "Kopieren",
        "コピー",
        "복사",
    ),
    "refreshLabel": localized(
        "Refresh",
        "重新整理",
        "刷新",
        "Actualizar",
        "Actualiser",
        "Aggiorna",
        "Aktualisieren",
        "更新",
        "새로고침",
    ),
    "serviceCount": localized(
        "Services",
        "服務",
        "服务",
        "Servicios",
        "Services",
        "Servizi",
        "Dienste",
        "サービス",
        "서비스",
    ),
    "pageCount": localized(
        "Pages",
        "頁面",
        "页面",
        "Páginas",
        "Pages",
        "Pagine",
        "Seiten",
        "ページ",
        "페이지",
    ),
    "launcherPath": localized(
        "Launcher",
        "啟動器",
        "启动器",
        "Lanzador",
        "Lanceur",
        "Launcher",
        "Launcher",
        "ランチャー",
        "런처",
    ),
    "kindLabel": localized(
        "Kind",
        "類型",
        "类型",
        "Tipo",
        "Type",
        "Tipo",
        "Typ",
        "種類",
        "종류",
    ),
    "healthLabel": localized(
        "Health",
        "健康檢查",
        "健康检查",
        "Salud",
        "Santé",
        "Salute",
        "Status",
        "ヘルス",
        "상태 확인",
    ),
    "uiLabel": localized(
        "UI",
        "介面",
        "界面",
        "UI",
        "UI",
        "UI",
        "UI",
        "UI",
        "UI",
    ),
    "logLabel": localized(
        "Log",
        "日誌",
        "日志",
        "Log",
        "Journal",
        "Log",
        "Log",
        "ログ",
        "로그",
    ),
    "defaultLabel": localized(
        "Default",
        "預設",
        "默认",
        "Predeterminado",
        "Par défaut",
        "Predefinito",
        "Standard",
        "既定値",
        "기본값",
    ),
    "choicesLabel": localized(
        "Choices",
        "可選值",
        "可选值",
        "Opciones",
        "Choix",
        "Scelte",
        "Optionen",
        "選択肢",
        "선택값",
    ),
    "emptyEnv": localized(
        "No extra environment switches for this demo.",
        "此示範沒有額外的環境開關。",
        "此演示没有额外的环境开关。",
        "Esta demo no tiene variables extra.",
        "Cette démo n'a pas de variables supplémentaires.",
        "Questa demo non ha variabili aggiuntive.",
        "Für diese Demo gibt es keine zusätzlichen Umgebungsoptionen.",
        "このデモには追加の環境スイッチはありません。",
        "이 데모에는 추가 환경 변수가 없습니다.",
    ),
    "noteOne": localized(
        "Healthy services already running on the expected ports are reused instead of restarted.",
        "如果預期連接埠上已經有健康的服務在執行，啟動器會直接重用它們而不是重新啟動。",
        "如果预期端口上已经有健康服务在运行，启动器会直接复用，而不是重新启动。",
        "Si ya hay servicios sanos ejecutándose en los puertos esperados, el lanzador los reutiliza.",
        "Si des services sains tournent déjà sur les ports attendus, le lanceur les réutilise.",
        "Se ci sono già servizi sani sulle porte previste, il launcher li riutilizza.",
        "Wenn auf den erwarteten Ports bereits funktionierende Dienste laufen, werden sie wiederverwendet.",
        "想定ポートで健全なサービスが既に動いている場合、ランチャーは再起動せず再利用します。",
        "예상 포트에서 정상 서비스가 이미 실행 중이면 런처가 재사용합니다.",
    ),
    "noteTwo": localized(
        "Set DEMO_OPEN_BROWSER=0 if you want the launcher to stay in the terminal without opening browser tabs.",
        "若希望只在終端機中執行而不自動開啟分頁，請設定 DEMO_OPEN_BROWSER=0。",
        "如果你只想在终端中运行而不自动打开浏览器标签页，请设置 DEMO_OPEN_BROWSER=0。",
        "Usa DEMO_OPEN_BROWSER=0 si no quieres abrir pestañas del navegador.",
        "Utilisez DEMO_OPEN_BROWSER=0 pour ne pas ouvrir d'onglets automatiquement.",
        "Imposta DEMO_OPEN_BROWSER=0 se non vuoi aprire schede del browser.",
        "Setze DEMO_OPEN_BROWSER=0, wenn keine Browser-Tabs geöffnet werden sollen.",
        "ブラウザタブを自動で開きたくない場合は DEMO_OPEN_BROWSER=0 を設定してください。",
        "브라우저 탭을 자동으로 열지 않으려면 DEMO_OPEN_BROWSER=0을 설정하세요.",
    ),
    "noteThree": localized(
        "Keep this terminal open and press Ctrl-C here when you want to stop the managed processes.",
        "請保持此終端機開啟，停止受管程序時請在這裡按 Ctrl-C。",
        "请保持此终端开启，想停止托管进程时就在这里按 Ctrl-C。",
        "Mantén esta terminal abierta y usa Ctrl-C aquí para detener los procesos gestionados.",
        "Gardez ce terminal ouvert et utilisez Ctrl-C ici pour arrêter les processus gérés.",
        "Tieni aperto questo terminale e usa Ctrl-C qui per fermare i processi gestiti.",
        "Lass dieses Terminal offen und drücke hier Ctrl-C, um die gestarteten Prozesse zu beenden.",
        "このターミナルを開いたままにし、停止するときはここで Ctrl-C を押してください。",
        "이 터미널을 열어 둔 채, 중지할 때는 여기서 Ctrl-C를 누르세요.",
    ),
    "status.pending": localized("Pending", "等待中", "等待中", "Pendiente", "En attente", "In attesa", "Ausstehend", "保留中", "대기 중"),
    "status.launching": localized("Launching", "啟動中", "启动中", "Iniciando", "Démarrage", "Avvio", "Startet", "起動中", "시작 중"),
    "status.ready": localized("Ready", "就緒", "就绪", "Listo", "Prêt", "Pronto", "Bereit", "準備完了", "준비됨"),
    "status.external": localized("Reused", "已重用", "已复用", "Reutilizado", "Réutilisé", "Riutilizzato", "Wiederverwendet", "再利用", "재사용됨"),
    "status.failed": localized("Failed", "失敗", "失败", "Falló", "Échec", "Errore", "Fehlgeschlagen", "失敗", "실패"),
    "status.stopped": localized("Stopped", "已停止", "已停止", "Detenido", "Arrêté", "Fermato", "Gestoppt", "停止", "중지됨"),
}


KIND_LABELS = {
    "registry": localized("Registry", "註冊中心", "注册中心", "Registro", "Registre", "Registro", "Registry", "レジストリ", "레지스트리"),
    "worker": localized("Worker", "工作代理", "工作代理", "Worker", "Worker", "Worker", "Worker", "ワーカー", "워커"),
    "ui": localized("UI", "介面", "界面", "UI", "UI", "UI", "UI", "UI", "UI"),
    "pulser": localized("Pulser", "Pulser", "Pulser", "Pulser", "Pulser", "Pulser", "Pulser", "Pulser", "Pulser"),
    "dispatcher": localized("Dispatcher", "派發器", "派发器", "Despachador", "Répartiteur", "Dispatcher", "Dispatcher", "ディスパッチャー", "디스패처"),
    "boss": localized("Boss UI", "Boss UI", "Boss UI", "Boss UI", "Boss UI", "Boss UI", "Boss UI", "Boss UI", "Boss UI"),
    "bridge": localized("Bridge", "橋接器", "桥接器", "Puente", "Pont", "Bridge", "Bridge", "ブリッジ", "브리지"),
}


OPEN_BROWSER_ENV = {
    "name": "DEMO_OPEN_BROWSER",
    "default": "1",
    "choices": "0, 1",
    "description": localized(
        "Set to 0 to keep the demo in the terminal without opening browser tabs automatically.",
        "設為 0 可避免自動開啟瀏覽器分頁。",
        "设为 0 可避免自动打开浏览器标签页。",
        "Ponlo en 0 para no abrir pestañas automáticamente.",
        "Réglez sur 0 pour ne pas ouvrir d'onglets automatiquement.",
        "Imposta 0 per non aprire schede automaticamente.",
        "Auf 0 setzen, um keine Browser-Tabs automatisch zu öffnen.",
        "0 にするとブラウザタブを自動で開きません。",
        "0으로 설정하면 브라우저 탭을 자동으로 열지 않습니다.",
    ),
}


LLM_PROVIDER_ENV = {
    "name": "DEMO_LLM_PROVIDER",
    "default": "openai if OPENAI_API_KEY exists, otherwise ollama",
    "choices": "openai, ollama",
    "description": localized(
        "Selects which LLM pulser to start for the demo.",
        "選擇此示範要啟動的 LLM pulser。",
        "选择此演示要启动的 LLM pulser。",
        "Selecciona qué pulser LLM iniciar.",
        "Sélectionne le pulser LLM à lancer.",
        "Seleziona quale pulser LLM avviare.",
        "Wählt aus, welcher LLM-Pulser gestartet wird.",
        "デモで起動する LLM pulser を選択します。",
        "데모에서 시작할 LLM pulser를 선택합니다.",
    ),
}


ANALYST_MODE_ENV = {
    "name": "DEMO_ANALYST_MODE",
    "default": "structured",
    "choices": "structured, advanced",
    "description": localized(
        "Use structured for the lightweight analyst pulser path or advanced for news, Ollama, prompted outputs, and personal agent.",
        "structured 為輕量分析師 pulser 流程，advanced 會加入新聞、Ollama、提示輸出與 personal agent。",
        "structured 为轻量分析师 pulser 流程，advanced 会加入新闻、Ollama、提示输出与 personal agent。",
        "Usa structured para el flujo ligero o advanced para noticias, Ollama, salidas con prompts y personal agent.",
        "Utilisez structured pour le flux léger ou advanced pour les news, Ollama, les sorties guidées et personal agent.",
        "Usa structured per il flusso leggero o advanced per news, Ollama, output guidati e personal agent.",
        "Verwende structured für den leichten Pfad oder advanced für News, Ollama, Prompt-Ausgaben und Personal Agent.",
        "軽量な流れは structured、ニュース・Ollama・プロンプト出力・personal agent を含む完全版は advanced を使います。",
        "가벼운 경로는 structured, 뉴스/Ollama/프롬프트 출력/personal agent까지 포함하려면 advanced를 사용합니다.",
    ),
}


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def _safe_slug(value: str) -> str:
    """Normalize one value for display IDs."""
    return str(value or "").strip().lower().replace("_", "-")


def _is_json_response(response: requests.Response) -> bool:
    """Return whether one response likely contains JSON."""
    header = str(response.headers.get("content-type") or "").lower()
    return "application/json" in header or "text/json" in header


def _tail_log(path: Path, *, lines: int = 40) -> str:
    """Return a tail of one log path."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def _find_free_port(host: str = "127.0.0.1") -> int:
    """Find one free local port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _merge_env(extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Merge environment variables for subprocesses."""
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    for key, value in (extra_env or {}).items():
        env[str(key)] = str(value)
    return env


def _lang_name_map() -> dict[str, str]:
    """Return the language label map."""
    return {code: label for code, label in LANGUAGE_OPTIONS}


@dataclass(frozen=True)
class ServiceSpec:
    """Definition for one service managed by the launcher."""

    name: str
    kind: str
    command: tuple[str, ...]
    command_label: str
    health_url: str
    expected_agent: str = ""
    ui_url: str = ""
    description: str = ""
    timeout_sec: float = 25.0
    env: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BrowserPage:
    """Metadata for one page that the guide can link to or open."""

    label: str
    url: str
    description: str = ""
    auto_open: bool = True


@dataclass(frozen=True)
class DemoSpec:
    """Resolved demo manifest."""

    demo_id: str
    title: str
    run_script_path: str
    readme_path: str
    summary: dict[str, str]
    notice: dict[str, str]
    services: tuple[ServiceSpec, ...]
    browser_pages: tuple[BrowserPage, ...]
    env_options: tuple[dict[str, Any], ...] = ()
    context_badges: tuple[str, ...] = ()


class LauncherState:
    """Thread-safe runtime state for the guide server."""

    def __init__(self, spec: DemoSpec):
        """Initialize the state."""
        self.spec = spec
        self.lock = threading.Lock()
        self.errors: list[str] = []
        self.guide_url = ""
        self.full_readme_url = ""
        self.started_at = _now_iso()
        self.services: dict[str, dict[str, Any]] = {}
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        for service in spec.services:
            self.services[service.name] = {
                "name": service.name,
                "kind": service.kind,
                "description": service.description,
                "health_url": service.health_url,
                "ui_url": service.ui_url,
                "command_label": service.command_label,
                "status": "pending",
                "status_detail": "",
                "pid": 0,
                "managed": False,
                "log_path": "",
                "updated_at": self.started_at,
            }

    def set_urls(self, guide_url: str, full_readme_url: str):
        """Store guide URLs after the guide server starts."""
        with self.lock:
            self.guide_url = guide_url
            self.full_readme_url = full_readme_url

    def mark_service(
        self,
        service_name: str,
        *,
        status: str,
        detail: str = "",
        pid: int = 0,
        managed: bool = False,
        log_path: str = "",
    ):
        """Update one service status entry."""
        with self.lock:
            entry = self.services.get(service_name)
            if not entry:
                return
            entry["status"] = status
            entry["status_detail"] = detail
            entry["pid"] = int(pid or 0)
            entry["managed"] = bool(managed)
            if log_path:
                entry["log_path"] = str(log_path)
            entry["updated_at"] = _now_iso()

    def add_error(self, message: str):
        """Append one launcher-level error."""
        normalized = str(message or "").strip()
        if not normalized:
            return
        with self.lock:
            self.errors.append(normalized)

    def record_process(self, service_name: str, process: subprocess.Popen[bytes]):
        """Record one managed process."""
        with self.lock:
            self.processes[service_name] = process

    def get_process_items(self) -> list[tuple[str, subprocess.Popen[bytes]]]:
        """Return process items safely."""
        with self.lock:
            return list(self.processes.items())

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot for the guide page."""
        with self.lock:
            return {
                "started_at": self.started_at,
                "guide_url": self.guide_url,
                "full_readme_url": self.full_readme_url,
                "errors": list(self.errors),
                "services": list(self.services.values()),
            }


def _script_command(relative_path: str) -> tuple[str, ...]:
    """Return the shell command tuple for one launcher-managed script."""
    return ("/bin/sh", str(REPO_ROOT / relative_path))


def _summary(text: dict[str, str], fallback: str = "") -> dict[str, str]:
    """Ensure every language has a value."""
    normalized = dict(text or {})
    for code in LANGUAGE_CODES:
        normalized.setdefault(code, fallback or normalized.get("en", ""))
    return normalized


def _empty_notice() -> dict[str, str]:
    """Return an empty localized notice map."""
    return {code: "" for code in LANGUAGE_CODES}


def _hello_plaza_spec() -> DemoSpec:
    """Resolve the hello-plaza manifest."""
    return DemoSpec(
        demo_id="hello-plaza",
        title="Hello Plaza",
        run_script_path="./demos/hello-plaza/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "hello-plaza" / "README.md"),
        summary=_summary(
            localized(
                "Launches a local Plaza, one worker, and a browser-facing user UI so you can watch registration and discovery happen end to end.",
                "啟動本機 Plaza、一個 worker，以及瀏覽器使用者介面，讓你從頭到尾看到註冊與探索流程。",
                "启动本地 Plaza、一个 worker，以及浏览器用户界面，让你从头到尾看到注册与发现流程。",
                "Inicia una Plaza local, un worker y una interfaz de usuario en el navegador para ver el registro y descubrimiento de extremo a extremo.",
                "Lance un Plaza local, un worker et une interface utilisateur dans le navigateur pour voir l'enregistrement et la découverte de bout en bout.",
                "Avvia una Plaza locale, un worker e una UI nel browser per vedere registrazione e scoperta dall'inizio alla fine.",
                "Startet eine lokale Plaza, einen Worker und eine Browser-UI, damit du Registrierung und Discovery Ende-zu-Ende sehen kannst.",
                "ローカルのPlaza、1つのworker、ブラウザUIを起動し、登録と発見の流れを最初から最後まで確認できます。",
                "로컬 Plaza, 워커 1개, 브라우저 UI를 실행해 등록과 발견 흐름을 처음부터 끝까지 볼 수 있습니다.",
            )
        ),
        notice=_empty_notice(),
        services=(
            ServiceSpec(
                name="demo-plaza",
                kind="registry",
                command=_script_command("demos/hello-plaza/start-plaza.sh"),
                command_label="./demos/hello-plaza/start-plaza.sh",
                health_url="http://127.0.0.1:8211/health",
                expected_agent="Plaza",
                description="Local Plaza registry for the smallest public demo.",
            ),
            ServiceSpec(
                name="demo-worker",
                kind="worker",
                command=_script_command("demos/hello-plaza/start-worker.sh"),
                command_label="./demos/hello-plaza/start-worker.sh",
                health_url="http://127.0.0.1:8212/health",
                expected_agent="demo-worker",
                description="Minimal worker that auto-registers with Plaza.",
            ),
            ServiceSpec(
                name="demo-user-ui",
                kind="ui",
                command=_script_command("demos/hello-plaza/start-user.sh"),
                command_label="./demos/hello-plaza/start-user.sh",
                health_url="http://127.0.0.1:8214/health",
                expected_agent="demo-user-ui",
                ui_url="http://127.0.0.1:8214/",
                description="Browser-facing user agent wired to the local Plaza.",
            ),
        ),
        browser_pages=(
            BrowserPage(label="User UI", url="http://127.0.0.1:8214/", description="Main walkthrough page."),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("local-first", "discovery", "public-demo"),
    )


def _data_pipeline_services() -> tuple[ServiceSpec, ...]:
    """Return the shared ADS pipeline services."""
    return (
        ServiceSpec(
            name="SQLiteADSDispatcher",
            kind="dispatcher",
            command=_script_command("demos/data-pipeline/start-dispatcher.sh"),
            command_label="./demos/data-pipeline/start-dispatcher.sh",
            health_url="http://127.0.0.1:9060/health",
            expected_agent="SQLiteADSDispatcher",
            description="SQLite-backed dispatcher queue for the demo ADS stack.",
        ),
        ServiceSpec(
            name="SQLiteADSWorker",
            kind="worker",
            command=_script_command("demos/data-pipeline/start-worker.sh"),
            command_label="./demos/data-pipeline/start-worker.sh",
            health_url="http://127.0.0.1:9061/health",
            expected_agent="SQLiteADSWorker",
            description="Mock-cap worker that polls the dispatcher and writes normalized rows.",
        ),
        ServiceSpec(
            name="SQLiteADSPulser",
            kind="pulser",
            command=_script_command("demos/data-pipeline/start-pulser.sh"),
            command_label="./demos/data-pipeline/start-pulser.sh",
            health_url="http://127.0.0.1:9062/health",
            expected_agent="SQLiteADSPulser",
            ui_url="http://127.0.0.1:9062/",
            description="Pulser surface over the normalized ADS tables.",
        ),
        ServiceSpec(
            name="SQLiteADSBoss",
            kind="boss",
            command=_script_command("demos/data-pipeline/start-boss.sh"),
            command_label="./demos/data-pipeline/start-boss.sh",
            health_url="http://127.0.0.1:9063/health",
            expected_agent="SQLiteADSBoss",
            ui_url="http://127.0.0.1:9063/",
            description="Boss UI for issuing demo jobs and watching queue state.",
        ),
    )


def _data_pipeline_spec() -> DemoSpec:
    """Resolve the full data-pipeline manifest."""
    return DemoSpec(
        demo_id="data-pipeline",
        title="Data Pipeline",
        run_script_path="./demos/data-pipeline/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "data-pipeline" / "README.md"),
        summary=_summary(
            localized(
                "Launches the SQLite ADS dispatcher, worker, pulser, and boss UI so you can issue jobs and inspect the normalized outputs from one stack.",
                "啟動 SQLite ADS 的 dispatcher、worker、pulser 與 boss UI，讓你可在同一個堆疊中派發工作並檢視標準化結果。",
                "启动 SQLite ADS 的 dispatcher、worker、pulser 与 boss UI，让你可以在同一个堆栈中下发任务并查看标准化结果。",
                "Inicia el dispatcher ADS con SQLite, el worker, el pulser y la Boss UI para emitir trabajos y revisar salidas normalizadas en una sola pila.",
                "Lance le dispatcher ADS SQLite, le worker, le pulser et la Boss UI pour émettre des tâches et inspecter les sorties normalisées depuis une seule pile.",
                "Avvia dispatcher ADS SQLite, worker, pulser e Boss UI per emettere job e controllare gli output normalizzati da un unico stack.",
                "Startet den SQLite-ADS-Dispatcher, Worker, Pulser und die Boss-UI, damit du Jobs auslösen und normalisierte Ausgaben in einem Stack prüfen kannst.",
                "SQLite ADS の dispatcher、worker、pulser、boss UI を起動し、1つのスタックからジョブ投入と正規化出力の確認を行えます。",
                "SQLite ADS dispatcher, worker, pulser, boss UI를 실행해 하나의 스택에서 작업 발행과 정규화 결과 확인을 할 수 있습니다.",
            )
        ),
        notice=_empty_notice(),
        services=_data_pipeline_services(),
        browser_pages=(
            BrowserPage(label="Boss UI", url="http://127.0.0.1:9063/", description="Issue jobs and monitor state."),
            BrowserPage(label="ADS Pulser UI", url="http://127.0.0.1:9062/", description="Query the demo ADS tables."),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("sqlite", "mock-collectors", "orchestration"),
    )


def _ads_pulser_spec() -> DemoSpec:
    """Resolve the ADS pulser view manifest."""
    return DemoSpec(
        demo_id="ads",
        title="ADS Pulser Demo",
        run_script_path="./demos/pulsers/ads/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "pulsers" / "ads" / "README.md"),
        summary=_summary(
            localized(
                "Launches the same SQLite ADS stack as the full pipeline demo, but centers the guide and browser links on the pulser-facing workflow.",
                "啟動與完整資料管線示範相同的 SQLite ADS 堆疊，但導覽與瀏覽器連結會聚焦在 pulser 使用流程。",
                "启动与完整数据管线演示相同的 SQLite ADS 堆栈，但导览与浏览器链接会聚焦在 pulser 使用流程。",
                "Lanza la misma pila ADS con SQLite que la demo completa, pero centra la guía y los enlaces en el flujo del pulser.",
                "Lance la même pile ADS SQLite que la démo complète, mais centre le guide et les liens sur le flux orienté pulser.",
                "Avvia lo stesso stack ADS SQLite della demo completa, ma concentra la guida e i link sul flusso del pulser.",
                "Startet denselben SQLite-ADS-Stack wie die vollständige Demo, fokussiert den Guide aber auf den Pulser-Workflow.",
                "完全版と同じ SQLite ADS スタックを起動しますが、ガイドとブラウザリンクは pulser 側の流れに焦点を当てます。",
                "전체 파이프라인 데모와 같은 SQLite ADS 스택을 실행하지만, 가이드와 브라우저 링크는 pulser 중심 흐름에 맞춥니다.",
            )
        ),
        notice=_summary(
            localized(
                "Use this view when you want the ADS query surface first and the dispatcher/boss mechanics second.",
                "若你想先看 ADS 查詢介面，再看 dispatcher 與 boss 的機制，請使用此視角。",
                "如果你想先看 ADS 查询界面，再看 dispatcher 与 boss 的机制，请使用这个视角。",
                "Usa esta vista si quieres ver primero la superficie de consulta ADS y después la mecánica del dispatcher y la boss UI.",
                "Utilisez cette vue si vous voulez d'abord la surface de requête ADS puis la mécanique dispatcher/boss UI.",
                "Usa questa vista se vuoi prima la superficie di query ADS e poi la meccanica dispatcher/boss UI.",
                "Nutze diese Sicht, wenn du zuerst die ADS-Abfrageoberfläche sehen willst und erst danach Dispatcher/Boss-Mechanik.",
                "ADS のクエリ面を先に見たい場合に使うビューです。dispatcher や boss UI はその次です。",
                "ADS 조회 화면을 먼저 보고 dispatcher/boss 동작은 그다음에 보고 싶을 때 사용하는 보기입니다.",
            )
        ),
        services=_data_pipeline_services(),
        browser_pages=(
            BrowserPage(label="ADS Pulser UI", url="http://127.0.0.1:9062/", description="Primary page for this guide."),
            BrowserPage(label="Boss UI", url="http://127.0.0.1:9063/", description="Optional job-issue companion UI.", auto_open=False),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("sqlite", "pulser-first", "normalized-data"),
    )


def _personal_research_spec() -> DemoSpec:
    """Resolve the personal-research-workbench manifest."""
    return DemoSpec(
        demo_id="personal-research-workbench",
        title="Personal Research Workbench",
        run_script_path="./demos/personal-research-workbench/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "personal-research-workbench" / "README.md"),
        summary=_summary(
            localized(
                "Launches the workbench, local Plaza, file-storage pulser, YFinance pulser, and technical-analysis pulser for the richest visual demo in the repo.",
                "啟動 workbench、本機 Plaza、file-storage pulser、YFinance pulser 與 technical-analysis pulser，提供此 repo 中最完整的視覺示範。",
                "启动 workbench、本地 Plaza、file-storage pulser、YFinance pulser 与 technical-analysis pulser，提供此仓库中最完整的视觉演示。",
                "Inicia el workbench, la Plaza local, el pulser de almacenamiento, el pulser de YFinance y el pulser de análisis técnico para la demo visual más completa del repositorio.",
                "Lance le workbench, la Plaza locale, le pulser de stockage, le pulser YFinance et le pulser d'analyse technique pour la démo visuelle la plus riche du dépôt.",
                "Avvia workbench, Plaza locale, pulser di storage, pulser YFinance e pulser di analisi tecnica per la demo visiva più ricca del repository.",
                "Startet Workbench, lokale Plaza, File-Storage-Pulser, YFinance-Pulser und Technical-Analysis-Pulser für die visuell stärkste Demo im Repo.",
                "workbench、ローカルPlaza、file-storage pulser、YFinance pulser、technical-analysis pulser を起動し、このリポジトリで最も視覚的なデモを実行します。",
                "workbench, 로컬 Plaza, file-storage pulser, YFinance pulser, technical-analysis pulser를 실행해 저장소에서 가장 시각적인 데모를 제공합니다.",
            )
        ),
        notice=_summary(
            localized(
                "The launcher opens both the main workbench and the embedded MapPhemar route because the diagram flow is part of the core walkthrough.",
                "啟動器會同時開啟主 workbench 與內嵌的 MapPhemar 路由，因為圖流程是核心導覽的一部分。",
                "启动器会同时打开主 workbench 与内嵌的 MapPhemar 路由，因为图流程是核心演示的一部分。",
                "El lanzador abre tanto el workbench principal como la ruta integrada de MapPhemar porque el flujo de diagramas forma parte del recorrido principal.",
                "Le lanceur ouvre à la fois le workbench principal et la route intégrée MapPhemar, car le flux de diagrammes fait partie du parcours principal.",
                "Il launcher apre sia il workbench principale sia la route integrata di MapPhemar perché il flusso a diagrammi fa parte del percorso principale.",
                "Der Launcher öffnet sowohl den Haupt-Workbench als auch die eingebettete MapPhemar-Route, weil der Diagramm-Flow zur Kerndemo gehört.",
                "ランチャーはメインのworkbenchと埋め込みMapPhemarルートの両方を開きます。図のフローが主要な導線だからです。",
                "런처는 메인 workbench와 내장 MapPhemar 경로를 모두 엽니다. 다이어그램 흐름이 핵심 시연이기 때문입니다.",
            )
        ),
        services=(
            ServiceSpec(
                name="workbench-plaza",
                kind="registry",
                command=_script_command("demos/personal-research-workbench/start-plaza.sh"),
                command_label="./demos/personal-research-workbench/start-plaza.sh",
                health_url="http://127.0.0.1:8241/health",
                expected_agent="Plaza",
                description="Local Plaza dedicated to the workbench demo.",
            ),
            ServiceSpec(
                name="DemoSystemPulser",
                kind="pulser",
                command=_script_command("demos/personal-research-workbench/start-file-storage-pulser.sh"),
                command_label="./demos/personal-research-workbench/start-file-storage-pulser.sh",
                health_url="http://127.0.0.1:8242/health",
                expected_agent="DemoSystemPulser",
                ui_url="http://127.0.0.1:8242/",
                description="Filesystem-backed pulser for the local storage flow.",
            ),
            ServiceSpec(
                name="DemoYFinancePulser",
                kind="pulser",
                command=_script_command("demos/personal-research-workbench/start-yfinance-pulser.sh"),
                command_label="./demos/personal-research-workbench/start-yfinance-pulser.sh",
                health_url="http://127.0.0.1:8243/health",
                expected_agent="DemoYFinancePulser",
                ui_url="http://127.0.0.1:8243/",
                description="Live market-data pulser used by charts and diagram runs.",
            ),
            ServiceSpec(
                name="DemoTechnicalAnalysisPulser",
                kind="pulser",
                command=_script_command("demos/personal-research-workbench/start-technical-analysis-pulser.sh"),
                command_label="./demos/personal-research-workbench/start-technical-analysis-pulser.sh",
                health_url="http://127.0.0.1:8244/health",
                expected_agent="DemoTechnicalAnalysisPulser",
                ui_url="http://127.0.0.1:8244/",
                description="RSI-focused path pulser for the diagram walkthrough.",
            ),
            ServiceSpec(
                name="Phemacast Personal Agent",
                kind="ui",
                command=_script_command("demos/personal-research-workbench/start-workbench.sh"),
                command_label="./demos/personal-research-workbench/start-workbench.sh",
                health_url="http://127.0.0.1:8041/health",
                ui_url="http://127.0.0.1:8041/",
                description="Main workbench UI with the embedded MapPhemar route.",
            ),
        ),
        browser_pages=(
            BrowserPage(label="Workbench", url="http://127.0.0.1:8041/", description="Primary visual workspace."),
            BrowserPage(label="MapPhemar", url="http://127.0.0.1:8041/map-phemar/", description="Diagram editor route."),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("visual-demo", "workbench", "diagram-flow"),
    )


def _file_storage_spec() -> DemoSpec:
    """Resolve the standalone file-storage pulser demo manifest."""
    return DemoSpec(
        demo_id="file-storage",
        title="System Pulser Demo",
        run_script_path="./demos/pulsers/file-storage/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "pulsers" / "file-storage" / "README.md"),
        summary=_summary(
            localized(
                "Launches a local Plaza plus SystemPulser for bucket and object operations with no external services required.",
                "啟動本機 Plaza 與 SystemPulser，可在不依賴外部服務的情況下操作 bucket 與物件。",
                "启动本地 Plaza 与 SystemPulser，可在不依赖外部服务的情况下操作 bucket 与对象。",
                "Inicia una Plaza local y SystemPulser para operaciones de buckets y objetos sin depender de servicios externos.",
                "Lance une Plaza locale et SystemPulser pour les opérations de buckets et d'objets sans services externes.",
                "Avvia una Plaza locale e SystemPulser per operazioni su bucket e oggetti senza servizi esterni.",
                "Startet eine lokale Plaza plus SystemPulser für Bucket- und Objektoperationen ohne externe Dienste.",
                "ローカルのPlazaとSystemPulserを起動し、外部サービスなしで bucket と object の操作を試せます。",
                "로컬 Plaza와 SystemPulser를 실행해 외부 서비스 없이 버킷/오브젝트 작업을 시험할 수 있습니다.",
            )
        ),
        notice=_empty_notice(),
        services=(
            ServiceSpec(
                name="file-storage-demo-plaza",
                kind="registry",
                command=_script_command("demos/pulsers/file-storage/start-plaza.sh"),
                command_label="./demos/pulsers/file-storage/start-plaza.sh",
                health_url="http://127.0.0.1:8256/health",
                expected_agent="Plaza",
                description="Local Plaza for the system pulser demo.",
            ),
            ServiceSpec(
                name="DemoSystemPulser",
                kind="pulser",
                command=_script_command("demos/pulsers/file-storage/start-pulser.sh"),
                command_label="./demos/pulsers/file-storage/start-pulser.sh",
                health_url="http://127.0.0.1:8257/health",
                expected_agent="DemoSystemPulser",
                ui_url="http://127.0.0.1:8257/",
                description="Pulser UI for bucket and object operations.",
            ),
        ),
        browser_pages=(
            BrowserPage(label="System Pulser UI", url="http://127.0.0.1:8257/", description="Primary demo UI."),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("local-only", "filesystem", "safe-start"),
    )


def _yfinance_spec() -> DemoSpec:
    """Resolve the standalone yfinance pulser demo manifest."""
    return DemoSpec(
        demo_id="yfinance",
        title="YFinance Pulser Demo",
        run_script_path="./demos/pulsers/yfinance/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "pulsers" / "yfinance" / "README.md"),
        summary=_summary(
            localized(
                "Launches a local Plaza plus YFinancePulser for quote and OHLC requests. Live data fetches still need outbound internet when you run pulses.",
                "啟動本機 Plaza 與 YFinancePulser 以提供報價與 OHLC 請求；真正執行脈衝時仍需要外網。",
                "启动本地 Plaza 与 YFinancePulser 以提供报价与 OHLC 请求；真正执行脉冲时仍需要外网。",
                "Inicia una Plaza local y YFinancePulser para cotizaciones y OHLC. Las consultas reales siguen necesitando internet.",
                "Lance une Plaza locale et YFinancePulser pour les cotations et OHLC. Les requêtes réelles nécessitent toujours internet.",
                "Avvia una Plaza locale e YFinancePulser per quotazioni e OHLC. Le richieste reali richiedono comunque internet.",
                "Startet eine lokale Plaza plus YFinancePulser für Kurse und OHLC-Anfragen. Echte Abfragen benötigen weiterhin Internet.",
                "ローカルのPlazaとYFinancePulserを起動し、気配値やOHLCを扱います。実際のデータ取得には外部ネットワークが必要です。",
                "로컬 Plaza와 YFinancePulser를 실행해 시세와 OHLC 요청을 처리합니다. 실제 조회에는 외부 인터넷이 필요합니다.",
            )
        ),
        notice=_summary(
            localized(
                "Yahoo can rate-limit or intermittently reject requests, so treat the browser UI as a live demo surface rather than a fixed fixture.",
                "Yahoo 可能會限流或間歇拒絕請求，因此請把瀏覽器 UI 視為即時示範介面，而非固定夾具。",
                "Yahoo 可能会限流或间歇拒绝请求，因此请把浏览器 UI 视为实时演示界面，而不是固定夹具。",
                "Yahoo puede limitar o rechazar solicitudes ocasionalmente, así que trata esta UI como una superficie en vivo.",
                "Yahoo peut limiter ou refuser certaines requêtes, donc considérez cette UI comme une surface de démonstration en direct.",
                "Yahoo può limitare o rifiutare alcune richieste, quindi considera questa UI come una demo live.",
                "Yahoo kann Requests drosseln oder ablehnen. Behandle die UI deshalb als Live-Demo und nicht als starre Fixture.",
                "Yahoo はレート制限や一時的な拒否を返すことがあります。固定のフィクスチャではなくライブデモとして扱ってください。",
                "Yahoo는 요청을 제한하거나 간헐적으로 거부할 수 있으니, 이 UI는 고정된 픽스처가 아니라 라이브 데모로 보세요.",
            )
        ),
        services=(
            ServiceSpec(
                name="yfinance-demo-plaza",
                kind="registry",
                command=_script_command("demos/pulsers/yfinance/start-plaza.sh"),
                command_label="./demos/pulsers/yfinance/start-plaza.sh",
                health_url="http://127.0.0.1:8251/health",
                expected_agent="Plaza",
                description="Local Plaza for the YFinance pulser demo.",
            ),
            ServiceSpec(
                name="DemoYFinancePulser",
                kind="pulser",
                command=_script_command("demos/pulsers/yfinance/start-pulser.sh"),
                command_label="./demos/pulsers/yfinance/start-pulser.sh",
                health_url="http://127.0.0.1:8252/health",
                expected_agent="DemoYFinancePulser",
                ui_url="http://127.0.0.1:8252/",
                description="Pulser UI for quote, profile, and OHLC requests.",
            ),
        ),
        browser_pages=(
            BrowserPage(label="YFinance Pulser UI", url="http://127.0.0.1:8252/", description="Primary demo UI."),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("live-data", "ohlc", "market-demo"),
    )


def _llm_spec(env: dict[str, str]) -> DemoSpec:
    """Resolve the LLM demo manifest based on provider selection."""
    provider_raw = str(env.get("DEMO_LLM_PROVIDER") or "").strip().lower()
    if provider_raw not in {"openai", "ollama"}:
        provider_raw = "openai" if str(env.get("OPENAI_API_KEY") or "").strip() else "ollama"

    if provider_raw == "openai":
        pulser = ServiceSpec(
            name="DemoOpenAIPulser",
            kind="pulser",
            command=_script_command("demos/pulsers/llm/start-openai-pulser.sh"),
            command_label="./demos/pulsers/llm/start-openai-pulser.sh",
            health_url="http://127.0.0.1:8262/health",
            expected_agent="DemoOpenAIPulser",
            ui_url="http://127.0.0.1:8262/",
            description="OpenAI-backed llm_chat pulser demo.",
        )
        browser_page = BrowserPage(label="OpenAI Pulser UI", url="http://127.0.0.1:8262/", description="Primary demo UI.")
        context_badges = ("llm", "provider: openai", "shared-editor")
    else:
        pulser = ServiceSpec(
            name="DemoOllamaPulser",
            kind="pulser",
            command=_script_command("demos/pulsers/llm/start-ollama-pulser.sh"),
            command_label="./demos/pulsers/llm/start-ollama-pulser.sh",
            health_url="http://127.0.0.1:8263/health",
            expected_agent="DemoOllamaPulser",
            ui_url="http://127.0.0.1:8263/",
            description="Ollama-backed llm_chat pulser demo.",
        )
        browser_page = BrowserPage(label="Ollama Pulser UI", url="http://127.0.0.1:8263/", description="Primary demo UI.")
        context_badges = ("llm", "provider: ollama", "shared-editor")

    return DemoSpec(
        demo_id="llm",
        title="LLM Pulser Demo",
        run_script_path="./demos/pulsers/llm/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "pulsers" / "llm" / "README.md"),
        summary=_summary(
            localized(
                "Launches a local Plaza and one LLM pulser. Use DEMO_LLM_PROVIDER to choose OpenAI or Ollama with the same llm_chat interface.",
                "啟動本機 Plaza 與一個 LLM pulser；可用 DEMO_LLM_PROVIDER 在 OpenAI 與 Ollama 之間切換，同樣使用 llm_chat 介面。",
                "启动本地 Plaza 与一个 LLM pulser；可用 DEMO_LLM_PROVIDER 在 OpenAI 与 Ollama 之间切换，仍使用同一 llm_chat 接口。",
                "Inicia una Plaza local y un pulser LLM. Usa DEMO_LLM_PROVIDER para elegir OpenAI u Ollama con la misma interfaz llm_chat.",
                "Lance une Plaza locale et un pulser LLM. Utilisez DEMO_LLM_PROVIDER pour choisir OpenAI ou Ollama avec la même interface llm_chat.",
                "Avvia una Plaza locale e un pulser LLM. Usa DEMO_LLM_PROVIDER per scegliere OpenAI o Ollama con la stessa interfaccia llm_chat.",
                "Startet eine lokale Plaza und einen LLM-Pulser. Mit DEMO_LLM_PROVIDER wählst du OpenAI oder Ollama bei gleicher llm_chat-Schnittstelle.",
                "ローカルのPlazaと1つのLLM pulserを起動します。DEMO_LLM_PROVIDER で OpenAI または Ollama を選択できますが、インターフェースは同じ llm_chat です。",
                "로컬 Plaza와 LLM pulser 하나를 실행합니다. DEMO_LLM_PROVIDER로 OpenAI 또는 Ollama를 고를 수 있고 llm_chat 인터페이스는 동일합니다.",
            )
        ),
        notice=_summary(
            localized(
                "OpenAI mode needs a valid API key for real calls. Ollama mode needs a local Ollama daemon and the configured model.",
                "OpenAI 模式在實際呼叫時需要有效的 API key；Ollama 模式需要本機 Ollama daemon 與設定好的模型。",
                "OpenAI 模式在实际调用时需要有效 API key；Ollama 模式需要本地 Ollama daemon 与配置好的模型。",
                "El modo OpenAI necesita una API key válida para llamadas reales. El modo Ollama necesita un daemon local y el modelo configurado.",
                "Le mode OpenAI a besoin d'une clé API valide pour les appels réels. Le mode Ollama nécessite un daemon local et le modèle configuré.",
                "La modalità OpenAI richiede una API key valida per le chiamate reali. Ollama richiede un daemon locale e il modello configurato.",
                "Der OpenAI-Modus braucht für echte Aufrufe einen gültigen API-Key. Der Ollama-Modus benötigt einen lokalen Daemon und das konfigurierte Modell.",
                "OpenAI モードでは実際の呼び出しに有効な API キーが必要です。Ollama モードではローカルの daemon と設定済みモデルが必要です。",
                "OpenAI 모드는 실제 호출에 유효한 API 키가 필요합니다. Ollama 모드는 로컬 daemon과 설정된 모델이 필요합니다.",
            )
        ),
        services=(
            ServiceSpec(
                name="llm-demo-plaza",
                kind="registry",
                command=_script_command("demos/pulsers/llm/start-plaza.sh"),
                command_label="./demos/pulsers/llm/start-plaza.sh",
                health_url="http://127.0.0.1:8261/health",
                expected_agent="Plaza",
                description="Local Plaza for the LLM pulser demo.",
            ),
            pulser,
        ),
        browser_pages=(browser_page,),
        env_options=(OPEN_BROWSER_ENV, LLM_PROVIDER_ENV),
        context_badges=context_badges,
    )


def _analyst_spec(env: dict[str, str]) -> DemoSpec:
    """Resolve the analyst-insights demo manifest based on selected mode."""
    mode = str(env.get("DEMO_ANALYST_MODE") or "structured").strip().lower()
    if mode not in {"structured", "advanced"}:
        mode = "structured"

    services: list[ServiceSpec] = [
        ServiceSpec(
            name="analyst-insight-demo-plaza",
            kind="registry",
            command=_script_command("demos/pulsers/analyst-insights/start-plaza.sh"),
            command_label="./demos/pulsers/analyst-insights/start-plaza.sh",
            health_url="http://127.0.0.1:8266/health",
            expected_agent="Plaza",
            description="Local Plaza for the analyst pulser demos.",
        ),
        ServiceSpec(
            name="DemoAnalystInsightPulser",
            kind="pulser",
            command=_script_command("demos/pulsers/analyst-insights/start-pulser.sh"),
            command_label="./demos/pulsers/analyst-insights/start-pulser.sh",
            health_url="http://127.0.0.1:8267/health",
            expected_agent="DemoAnalystInsightPulser",
            ui_url="http://127.0.0.1:8267/",
            description="Structured analyst pulser with reusable research views.",
        ),
    ]
    pages: list[BrowserPage] = [
        BrowserPage(label="Structured Pulser UI", url="http://127.0.0.1:8267/", description="Default demo UI."),
    ]
    context_badges = ["analyst", f"mode: {mode}", "research-views"]

    if mode == "advanced":
        services.extend(
            [
                ServiceSpec(
                    name="DemoAnalystNewsWirePulser",
                    kind="pulser",
                    command=_script_command("demos/pulsers/analyst-insights/start-news-pulser.sh"),
                    command_label="./demos/pulsers/analyst-insights/start-news-pulser.sh",
                    health_url="http://127.0.0.1:8268/health",
                    expected_agent="DemoAnalystNewsWirePulser",
                    ui_url="http://127.0.0.1:8268/",
                    description="Seeded upstream news source for the prompted flow.",
                ),
                ServiceSpec(
                    name="DemoAnalystOllamaPulser",
                    kind="pulser",
                    command=_script_command("demos/pulsers/analyst-insights/start-ollama-pulser.sh"),
                    command_label="./demos/pulsers/analyst-insights/start-ollama-pulser.sh",
                    health_url="http://127.0.0.1:8269/health",
                    expected_agent="DemoAnalystOllamaPulser",
                    ui_url="http://127.0.0.1:8269/",
                    description="Local Ollama-backed llm_chat pulser for analyst prompts.",
                ),
                ServiceSpec(
                    name="DemoAnalystPromptedNewsPulser",
                    kind="pulser",
                    command=_script_command("demos/pulsers/analyst-insights/start-analyst-news-pulser.sh"),
                    command_label="./demos/pulsers/analyst-insights/start-analyst-news-pulser.sh",
                    health_url="http://127.0.0.1:8270/health",
                    expected_agent="DemoAnalystPromptedNewsPulser",
                    ui_url="http://127.0.0.1:8270/",
                    description="Prompt-owned analyst pulser that turns news into reusable outputs.",
                ),
                ServiceSpec(
                    name="Phemacast Personal Agent",
                    kind="ui",
                    command=_script_command("demos/pulsers/analyst-insights/start-personal-agent.sh"),
                    command_label="./demos/pulsers/analyst-insights/start-personal-agent.sh",
                    health_url="http://127.0.0.1:8061/health",
                    ui_url="http://127.0.0.1:8061/",
                    description="Consumer-view walkthrough for the advanced analyst stack.",
                ),
            ]
        )
        pages = [
            BrowserPage(label="Personal Agent", url="http://127.0.0.1:8061/", description="Primary advanced walkthrough."),
            BrowserPage(label="Prompted Pulser UI", url="http://127.0.0.1:8270/", description="Advanced prompted outputs."),
            BrowserPage(label="Structured Pulser UI", url="http://127.0.0.1:8267/", description="Structured companion UI.", auto_open=False),
        ]

    return DemoSpec(
        demo_id="analyst-insights",
        title="Analyst Insight Pulser Demo",
        run_script_path="./demos/pulsers/analyst-insights/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "pulsers" / "analyst-insights" / "README.md"),
        summary=_summary(
            localized(
                "Launches the structured analyst pulser by default. Switch to DEMO_ANALYST_MODE=advanced to add the news source, Ollama, prompted pulser, and personal agent flow.",
                "預設啟動結構化分析師 pulser；若設定 DEMO_ANALYST_MODE=advanced，則會加入新聞來源、Ollama、提示版 pulser 與 personal agent 流程。",
                "默认启动结构化分析师 pulser；如果设置 DEMO_ANALYST_MODE=advanced，则会加入新闻源、Ollama、提示版 pulser 与 personal agent 流程。",
                "Lanza por defecto el pulser analista estructurado. Cambia DEMO_ANALYST_MODE=advanced para añadir noticias, Ollama, el pulser con prompts y personal agent.",
                "Lance par défaut le pulser analyste structuré. Passez à DEMO_ANALYST_MODE=advanced pour ajouter la source news, Ollama, le pulser guidé et personal agent.",
                "Avvia di default il pulser analista strutturato. Usa DEMO_ANALYST_MODE=advanced per aggiungere news, Ollama, il pulser guidato e personal agent.",
                "Startet standardmäßig den strukturierten Analysten-Pulser. Mit DEMO_ANALYST_MODE=advanced kommen News-Quelle, Ollama, Prompt-Pulser und Personal Agent dazu.",
                "既定では構造化アナリスト pulser を起動します。DEMO_ANALYST_MODE=advanced にすると、ニュース元・Ollama・プロンプト pulser・personal agent が追加されます。",
                "기본값으로 구조화된 분석가 pulser를 실행합니다. DEMO_ANALYST_MODE=advanced로 바꾸면 뉴스 소스, Ollama, 프롬프트 pulser, personal agent 흐름이 추가됩니다.",
            )
        ),
        notice=_summary(
            localized(
                "Structured mode is fully local and avoids LLM dependencies. Advanced mode expects a working local Ollama setup.",
                "structured 模式完全本機化，避免 LLM 依賴；advanced 模式則預期你已有可用的本機 Ollama。",
                "structured 模式完全本地化，避免 LLM 依赖；advanced 模式则预期你已有可用的本地 Ollama。",
                "El modo structured es totalmente local y evita dependencias LLM. El modo advanced espera un Ollama local funcional.",
                "Le mode structured est entièrement local et évite les dépendances LLM. Le mode advanced suppose un Ollama local fonctionnel.",
                "La modalità structured è completamente locale ed evita dipendenze LLM. La modalità advanced richiede un Ollama locale funzionante.",
                "Der structured-Modus ist komplett lokal und vermeidet LLM-Abhängigkeiten. Für advanced wird ein funktionierendes lokales Ollama erwartet.",
                "structured モードは完全ローカルで LLM 依存を避けます。advanced モードでは動作するローカル Ollama が前提です。",
                "structured 모드는 완전 로컬이며 LLM 의존성을 피합니다. advanced 모드는 동작하는 로컬 Ollama가 필요합니다.",
            )
        ),
        services=tuple(services),
        browser_pages=tuple(pages),
        env_options=(OPEN_BROWSER_ENV, ANALYST_MODE_ENV),
        context_badges=tuple(context_badges),
    )


def _finance_briefings_spec() -> DemoSpec:
    """Resolve the finance-briefings demo manifest."""
    return DemoSpec(
        demo_id="finance-briefings",
        title="Finance Briefing Workflow Demo",
        run_script_path="./demos/pulsers/finance-briefings/run-demo.sh",
        readme_path=str(REPO_ROOT / "demos" / "pulsers" / "finance-briefings" / "README.md"),
        summary=_summary(
            localized(
                "Launches a local Plaza plus the Attas-native financial briefing pulser that exposes workflow context, briefing step pulses, and publication/export outputs for the finance diagrams.",
                "啟動本機 Plaza 與 Attas 原生的 financial briefing pulser，提供工作流程上下文、briefing 步驟脈衝，以及供財經圖使用的發佈與匯出輸出。",
                "启动本地 Plaza 与 Attas 原生的 financial briefing pulser，提供工作流上下文、briefing 步骤脉冲，以及供财经图使用的发布与导出输出。",
                "Inicia una Plaza local y el pulser financiero nativo de Attas que expone el contexto del workflow, los pasos del briefing y las salidas de publicación/exportación para los diagramas.",
                "Lance une Plaza locale et le pulser financier natif d'Attas qui expose le contexte du workflow, les étapes du briefing et les sorties de publication/export pour les diagrammes.",
                "Avvia una Plaza locale e il pulser finanziario nativo di Attas che espone contesto workflow, step del briefing e output di pubblicazione/esportazione per i diagrammi.",
                "Startet eine lokale Plaza plus den nativen Attas-Finanzbriefing-Pulser, der Workflow-Kontext, Briefing-Schritte und Publish/Export-Ausgaben für die Diagramme bereitstellt.",
                "ローカルのPlazaと Attas ネイティブの financial briefing pulser を起動し、ワークフロー文脈、briefing ステップ、公開/エクスポート出力を金融ダイアグラム向けに公開します。",
                "로컬 Plaza와 Attas 네이티브 financial briefing pulser를 실행해 워크플로우 컨텍스트, briefing 단계 pulse, 게시/내보내기 출력을 금융 다이어그램용으로 노출합니다.",
            )
        ),
        notice=_summary(
            localized(
                "This demo now carries its own local Plaza so it no longer depends on the analyst-insights registry being up first.",
                "此示範現在內建自己的本機 Plaza，因此不再需要先啟動 analyst-insights 的註冊中心。",
                "此演示现在自带自己的本地 Plaza，因此不再需要先启动 analyst-insights 的注册中心。",
                "Esta demo ahora trae su propia Plaza local, así que ya no depende del registro de analyst-insights.",
                "Cette démo embarque maintenant sa propre Plaza locale et ne dépend plus du registre d'analyst-insights.",
                "Questa demo ora include la propria Plaza locale e non dipende più dal registry di analyst-insights.",
                "Diese Demo bringt jetzt ihre eigene lokale Plaza mit und hängt nicht mehr vom Registry der analyst-insights-Demo ab.",
                "このデモは専用のローカル Plaza を持つため、analyst-insights のレジストリに依存しません。",
                "이 데모는 자체 로컬 Plaza를 포함하므로 analyst-insights 레지스트리에 의존하지 않습니다.",
            )
        ),
        services=(
            ServiceSpec(
                name="finance-briefing-demo-plaza",
                kind="registry",
                command=_script_command("demos/pulsers/finance-briefings/start-plaza.sh"),
                command_label="./demos/pulsers/finance-briefings/start-plaza.sh",
                health_url="http://127.0.0.1:8272/health",
                expected_agent="Plaza",
                description="Local Plaza for the finance briefing workflow demo.",
            ),
            ServiceSpec(
                name="DemoFinancialBriefingPulser",
                kind="pulser",
                command=_script_command("demos/pulsers/finance-briefings/start-pulser.sh"),
                command_label="./demos/pulsers/finance-briefings/start-pulser.sh",
                health_url="http://127.0.0.1:8271/health",
                expected_agent="DemoFinancialBriefingPulser",
                ui_url="http://127.0.0.1:8271/",
                description="Attas-native pulser for workflow context, briefing steps, and export outputs.",
                timeout_sec=30.0,
            ),
        ),
        browser_pages=(
            BrowserPage(label="Workflow Pulser UI", url="http://127.0.0.1:8271/", description="Primary demo UI."),
        ),
        env_options=(OPEN_BROWSER_ENV,),
        context_badges=("attas", "workflow-steps", "diagram-ready"),
    )


def available_demo_ids() -> list[str]:
    """Return the supported demo IDs."""
    return [
        "hello-plaza",
        "data-pipeline",
        "personal-research-workbench",
        "file-storage",
        "yfinance",
        "llm",
        "analyst-insights",
        "finance-briefings",
        "ads",
    ]


def resolve_demo_spec(demo_id: str, env: dict[str, str] | None = None) -> DemoSpec:
    """Resolve one demo ID into a concrete manifest."""
    normalized = _safe_slug(demo_id)
    runtime_env = dict(env or os.environ)
    if normalized == "hello-plaza":
        return _hello_plaza_spec()
    if normalized == "data-pipeline":
        return _data_pipeline_spec()
    if normalized == "personal-research-workbench":
        return _personal_research_spec()
    if normalized == "file-storage":
        return _file_storage_spec()
    if normalized == "yfinance":
        return _yfinance_spec()
    if normalized == "llm":
        return _llm_spec(runtime_env)
    if normalized == "analyst-insights":
        return _analyst_spec(runtime_env)
    if normalized == "finance-briefings":
        return _finance_briefings_spec()
    if normalized == "ads":
        return _ads_pulser_spec()
    raise ValueError(f"Unknown demo '{demo_id}'. Supported demos: {', '.join(available_demo_ids())}")


def _probe_service(spec: ServiceSpec) -> tuple[bool, str]:
    """Probe one service and return success plus status detail."""
    try:
        response = requests.get(spec.health_url, timeout=0.75)
    except Exception as exc:
        return False, str(exc)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    if not spec.expected_agent:
        return True, "healthy"
    payload: dict[str, Any] = {}
    if _is_json_response(response):
        with contextlib.suppress(Exception):
            payload = response.json()
    actual = str(payload.get("agent") or "").strip()
    if actual and actual != spec.expected_agent:
        return False, f"expected agent {spec.expected_agent}, got {actual}"
    if not actual and spec.expected_agent:
        return False, f"missing agent name in health payload"
    return True, "healthy"


def _wait_for_service(spec: ServiceSpec, *, timeout_sec: float) -> tuple[bool, str]:
    """Wait until one service is healthy or a timeout expires."""
    deadline = time.time() + max(float(timeout_sec), 0.1)
    last_detail = ""
    while time.time() < deadline:
        healthy, detail = _probe_service(spec)
        last_detail = detail
        if healthy:
            return True, detail
        time.sleep(0.25)
    return False, last_detail


def _terminate_process(process: subprocess.Popen[bytes]):
    """Terminate one managed process group."""
    if process.poll() is not None:
        return
    with contextlib.suppress(Exception):
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    deadline = time.time() + 5.0
    while time.time() < deadline:
        if process.poll() is not None:
            return
        time.sleep(0.1)
    with contextlib.suppress(Exception):
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()


def _build_full_readme_html(spec: DemoSpec) -> str:
    """Render the original README as HTML for the guide server."""
    source_path = Path(spec.readme_path)
    markdown = source_path.read_text(encoding="utf-8")
    if render_markdown is not None:
        content_html = render_markdown(markdown, source_path=source_path)
    else:  # pragma: no cover - fallback path
        content_html = f"<pre>{escape(markdown)}</pre>"
    title = escape(spec.title)
    path_label = escape(str(source_path))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} README</title>
  <style>
    :root {{
      --paper: #f6f1e8;
      --paper-deep: #ece1cf;
      --ink: #1d1b18;
      --muted: #6d6257;
      --accent: #9f3e2d;
      --accent-soft: rgba(159, 62, 45, 0.12);
      --panel: rgba(255, 252, 246, 0.9);
      --line: rgba(29, 27, 24, 0.12);
      --shadow: 0 24px 60px rgba(47, 39, 28, 0.14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(159, 62, 45, 0.18), transparent 36%),
        radial-gradient(circle at bottom right, rgba(78, 102, 78, 0.16), transparent 34%),
        linear-gradient(180deg, #f9f5ed 0%, var(--paper) 100%);
    }}
    .shell {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 20px 60px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .hero {{
      padding: 28px 28px 22px;
      margin-bottom: 24px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .eyebrow {{
      margin: 0 0 10px;
      color: var(--accent);
      font-size: 0.76rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: clamp(2.2rem, 5vw, 4rem);
      line-height: 0.95;
      font-weight: 700;
    }}
    .hero p {{
      margin: 14px 0 0;
      max-width: 760px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 1rem;
    }}
    .buttons {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    a.button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      text-decoration: none;
      border-radius: 999px;
      padding: 12px 18px;
      font-weight: 700;
      border: 1px solid rgba(159, 62, 45, 0.2);
      color: var(--ink);
      background: rgba(255, 255, 255, 0.7);
    }}
    a.button.primary {{
      color: white;
      background: linear-gradient(135deg, #9f3e2d 0%, #7d2d20 100%);
      border-color: transparent;
    }}
    .panel {{
      padding: 24px;
    }}
    .path {{
      margin: 14px 0 0;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.72);
      border: 1px dashed var(--line);
      color: var(--muted);
      font-size: 0.95rem;
      word-break: break-word;
    }}
    .doc-prose {{
      font-size: 1rem;
      line-height: 1.8;
      color: var(--ink);
    }}
    .doc-prose h1, .doc-prose h2, .doc-prose h3, .doc-prose h4 {{
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      margin-top: 1.7em;
      margin-bottom: 0.65em;
      line-height: 1.15;
    }}
    .doc-prose p, .doc-prose ul, .doc-prose ol, .doc-prose pre {{
      margin: 0 0 1.05rem;
    }}
    .doc-prose ul, .doc-prose ol {{
      padding-left: 1.35rem;
    }}
    .doc-prose code {{
      font-family: "SFMono-Regular", "Menlo", monospace;
      background: rgba(159, 62, 45, 0.08);
      border-radius: 8px;
      padding: 0.16rem 0.38rem;
    }}
    .doc-prose pre {{
      overflow-x: auto;
      padding: 1rem;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.76);
    }}
    .doc-prose pre code {{
      background: transparent;
      padding: 0;
    }}
    .doc-prose a {{
      color: var(--accent);
    }}
    @media (max-width: 720px) {{
      .shell {{ padding: 24px 14px 44px; }}
      .hero, .panel {{ border-radius: 22px; }}
      .hero {{ padding: 22px 18px 18px; }}
      .panel {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <p class="eyebrow">English README Reference</p>
          <h1>{title}</h1>
          <p>This route renders the original markdown README as HTML from the local workspace. Use the launcher guide page for localized overview text and live runtime status.</p>
        </div>
        <div class="buttons">
          <a class="button" href="/">Back To Launcher Guide</a>
        </div>
      </div>
      <div class="path">{path_label}</div>
    </section>
    <article class="panel">
      <div class="doc-prose">{content_html}</div>
    </article>
  </div>
</body>
</html>"""


def _build_main_page_html(spec: DemoSpec) -> str:
    """Build the localized launcher guide HTML."""
    payload = {
        "demoId": spec.demo_id,
        "title": spec.title,
        "runScriptPath": spec.run_script_path,
        "readmePath": spec.readme_path,
        "summary": spec.summary,
        "notice": spec.notice,
        "languages": [{"code": code, "label": label} for code, label in LANGUAGE_OPTIONS],
        "languageNames": _lang_name_map(),
        "ui": UI_STRINGS,
        "kindLabels": KIND_LABELS,
        "browserPages": [
            {
                "label": page.label,
                "url": page.url,
                "description": page.description,
                "auto_open": bool(page.auto_open),
            }
            for page in spec.browser_pages
        ],
        "services": [
            {
                "name": service.name,
                "kind": service.kind,
                "description": service.description,
                "commandLabel": service.command_label,
                "healthUrl": service.health_url,
                "uiUrl": service.ui_url,
            }
            for service in spec.services
        ],
        "envOptions": list(spec.env_options),
        "contextBadges": list(spec.context_badges),
        "statusUrl": "/api/status",
        "fullReadmeUrl": "/full-readme",
    }
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(spec.title)} Launcher Guide</title>
  <style>
    :root {{
      --paper: #f5efe4;
      --paper-bright: rgba(255, 252, 246, 0.92);
      --ink: #191613;
      --muted: #6b6158;
      --accent: #a33d2a;
      --accent-2: #5b7d5a;
      --line: rgba(25, 22, 19, 0.12);
      --line-strong: rgba(25, 22, 19, 0.18);
      --shadow: 0 30px 80px rgba(54, 39, 25, 0.14);
      --ready: #255d35;
      --failed: #9f2f20;
      --pending: #9c7b39;
      --chip: rgba(255,255,255,0.72);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(163, 61, 42, 0.2), transparent 34%),
        radial-gradient(circle at 86% 14%, rgba(91, 125, 90, 0.18), transparent 28%),
        radial-gradient(circle at bottom right, rgba(163, 61, 42, 0.12), transparent 30%),
        linear-gradient(180deg, #faf6ee 0%, var(--paper) 100%);
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.07;
      background-image:
        linear-gradient(0deg, transparent 24%, rgba(0,0,0,0.7) 25%, transparent 26%),
        linear-gradient(90deg, transparent 24%, rgba(0,0,0,0.7) 25%, transparent 26%);
      background-size: 18px 18px;
      mix-blend-mode: multiply;
    }}
    .shell {{
      width: min(1180px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 26px 0 46px;
      position: relative;
    }}
    .hero, .panel {{
      background: var(--paper-bright);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .hero {{
      border-radius: 34px;
      padding: 28px 28px 24px;
      position: relative;
      overflow: hidden;
      animation: rise 700ms ease both;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -60px -80px auto;
      width: 220px;
      height: 220px;
      border-radius: 42px;
      transform: rotate(18deg);
      background: linear-gradient(135deg, rgba(163, 61, 42, 0.14), rgba(91, 125, 90, 0.12));
      filter: blur(6px);
    }}
    .hero-top {{
      display: grid;
      grid-template-columns: 1.35fr 0.65fr;
      gap: 24px;
      align-items: start;
      position: relative;
      z-index: 1;
    }}
    .eyebrow {{
      margin: 0 0 12px;
      color: var(--accent);
      letter-spacing: 0.16em;
      text-transform: uppercase;
      font-size: 0.78rem;
      font-weight: 800;
    }}
    h1 {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: clamp(2.5rem, 5vw, 4.8rem);
      line-height: 0.92;
      letter-spacing: -0.03em;
      max-width: 9ch;
    }}
    .summary {{
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 1.02rem;
      line-height: 1.75;
      max-width: 740px;
    }}
    .notice {{
      margin: 18px 0 0;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(163, 61, 42, 0.16);
      background: rgba(163, 61, 42, 0.08);
      color: var(--ink);
      font-size: 0.96rem;
      line-height: 1.65;
    }}
    .hero-side {{
      display: grid;
      gap: 14px;
    }}
    .hero-side .select-block,
    .hero-side .metrics {{
      padding: 18px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid var(--line);
    }}
    .select-block label {{
      display: block;
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 0.82rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-weight: 800;
    }}
    select {{
      width: 100%;
      appearance: none;
      border: 1px solid var(--line-strong);
      border-radius: 16px;
      background: white;
      padding: 14px 16px;
      font: inherit;
      color: var(--ink);
    }}
    .badge-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .context-badge {{
      padding: 10px 13px;
      border-radius: 999px;
      background: var(--chip);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.85rem;
      text-transform: lowercase;
    }}
    .metrics {{
      display: grid;
      gap: 12px;
    }}
    .metric {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 0.88rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .metric .value {{
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: 1.2rem;
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
      gap: 20px;
      margin-top: 22px;
    }}
    .panel {{
      border-radius: 28px;
      padding: 22px;
      animation: rise 900ms ease both;
    }}
    .panel h2 {{
      margin: 0 0 16px;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      font-size: 1.55rem;
      line-height: 1;
    }}
    .service-list, .page-list, .env-list, .notes-list {{
      display: grid;
      gap: 12px;
    }}
    .service-card, .page-card, .env-card, .note-card {{
      padding: 16px;
      border-radius: 22px;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid var(--line);
    }}
    .service-head {{
      display: flex;
      gap: 12px;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .service-name {{
      font-size: 1.08rem;
      font-weight: 700;
      margin: 0;
    }}
    .service-kind {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.86rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      font-size: 0.85rem;
      font-weight: 800;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .status-pill.pending, .status-pill.launching {{
      color: #6d5218;
      background: rgba(245, 209, 120, 0.2);
      border-color: rgba(156, 123, 57, 0.24);
    }}
    .status-pill.ready, .status-pill.external {{
      color: var(--ready);
      background: rgba(50, 110, 67, 0.12);
      border-color: rgba(37, 93, 53, 0.2);
    }}
    .status-pill.failed, .status-pill.stopped {{
      color: var(--failed);
      background: rgba(159, 47, 32, 0.1);
      border-color: rgba(159, 47, 32, 0.18);
    }}
    .service-description, .page-description, .env-description {{
      margin: 10px 0 0;
      color: var(--muted);
      line-height: 1.65;
      font-size: 0.95rem;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 12px;
      margin-top: 14px;
    }}
    .meta-item {{
      min-width: 0;
    }}
    .meta-item strong {{
      display: block;
      color: var(--muted);
      margin-bottom: 6px;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .meta-item span, .mono, code {{
      word-break: break-word;
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 0.9rem;
      color: var(--ink);
    }}
    .meta-item a, .meta-link {{
      word-break: break-word;
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 0.9rem;
      color: var(--accent);
      text-decoration: underline;
      text-decoration-color: rgba(163, 61, 42, 0.38);
      text-underline-offset: 0.18em;
    }}
    .meta-item a:hover, .meta-link:hover {{
      color: #7d2d20;
      text-decoration-color: currentColor;
    }}
    .button-row {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 16px;
    }}
    .button {{
      appearance: none;
      border: 1px solid rgba(163, 61, 42, 0.16);
      background: white;
      color: var(--ink);
      border-radius: 999px;
      padding: 11px 15px;
      font: inherit;
      font-weight: 800;
      text-decoration: none;
      cursor: pointer;
    }}
    .button.primary {{
      color: white;
      border-color: transparent;
      background: linear-gradient(135deg, #a33d2a 0%, #7e3022 100%);
    }}
    .button.ghost {{
      background: rgba(255,255,255,0.74);
    }}
    .page-card.auto-open {{
      border-color: rgba(91, 125, 90, 0.26);
      box-shadow: inset 0 0 0 1px rgba(91, 125, 90, 0.08);
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-top: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(91, 125, 90, 0.12);
      color: #33523b;
      font-size: 0.84rem;
      font-weight: 800;
    }}
    .command-card {{
      margin-top: 16px;
      padding: 18px;
      border-radius: 22px;
      background: rgba(255,255,255,0.68);
      border: 1px solid var(--line);
    }}
    .command-card pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "SFMono-Regular", "Menlo", monospace;
      font-size: 0.95rem;
      line-height: 1.65;
    }}
    .footer-note {{
      margin-top: 16px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 0.94rem;
    }}
    .error-banner {{
      display: none;
      margin-top: 18px;
      padding: 14px 16px;
      border-radius: 20px;
      border: 1px solid rgba(159, 47, 32, 0.22);
      background: rgba(159, 47, 32, 0.08);
      color: var(--failed);
      line-height: 1.55;
      font-weight: 700;
    }}
    .error-banner.visible {{
      display: block;
    }}
    @keyframes rise {{
      from {{
        opacity: 0;
        transform: translateY(18px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}
    @media (max-width: 980px) {{
      .hero-top, .grid {{
        grid-template-columns: 1fr;
      }}
      h1 {{
        max-width: none;
      }}
    }}
    @media (max-width: 720px) {{
      .shell {{
        width: min(100vw - 18px, 100%);
        padding: 18px 0 28px;
      }}
      .hero {{
        padding: 22px 18px 18px;
        border-radius: 26px;
      }}
      .panel {{
        padding: 18px;
        border-radius: 24px;
      }}
      .meta-grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <p class="eyebrow" id="eyebrow"></p>
          <h1 id="title"></h1>
          <p class="summary" id="summary"></p>
          <div class="notice" id="notice" hidden></div>
          <div class="badge-row" id="context-badges"></div>
          <div class="error-banner" id="error-banner"></div>
        </div>
        <div class="hero-side">
          <div class="select-block">
            <label for="language-select">Language</label>
            <select id="language-select"></select>
            <div class="button-row">
              <button class="button ghost" id="refresh-button" type="button"></button>
              <a class="button primary" id="full-readme-button" href="/full-readme"></a>
            </div>
          </div>
          <div class="metrics">
            <div class="metric"><span class="label" id="metric-services-label"></span><span class="value" id="metric-services-value"></span></div>
            <div class="metric"><span class="label" id="metric-pages-label"></span><span class="value" id="metric-pages-value"></span></div>
            <div class="metric"><span class="label" id="metric-launcher-label"></span><span class="value mono" id="metric-launcher-value"></span></div>
          </div>
        </div>
      </div>
    </section>
    <div class="grid">
      <section class="panel">
        <h2 id="stack-label"></h2>
        <div class="service-list" id="service-list"></div>
      </section>
      <section class="panel">
        <h2 id="pages-label"></h2>
        <div class="page-list" id="page-list"></div>
        <div class="command-card">
          <h2 id="environment-label" style="margin-top:0;"></h2>
          <div class="env-list" id="env-list"></div>
        </div>
        <div class="command-card">
          <h2 id="run-label" style="margin-top:0;"></h2>
          <pre id="launch-command"></pre>
          <div class="button-row">
            <button class="button ghost" id="copy-command-button" type="button"></button>
          </div>
        </div>
        <div class="command-card">
          <h2 id="readme-label" style="margin-top:0;"></h2>
          <div class="meta-grid">
            <div class="meta-item">
              <strong id="readme-path-label"></strong>
              <span id="readme-path-value"></span>
            </div>
          </div>
          <div class="footer-note" id="generic-notes-label"></div>
          <div class="notes-list" id="generic-notes"></div>
        </div>
      </section>
    </div>
  </div>
  <script id="demo-payload" type="application/json">{payload_json}</script>
  <script>
    const payload = JSON.parse(document.getElementById("demo-payload").textContent);
    const storageKey = `demo-launcher-lang-${{payload.demoId}}`;
    let currentLang = window.localStorage.getItem(storageKey) || "en";
    let currentStatus = null;

    function localizedValue(map) {{
      if (!map) return "";
      return map[currentLang] || map.en || "";
    }}

    function ui(key) {{
      return localizedValue(payload.ui[key]);
    }}

    function kindLabel(kind) {{
      return localizedValue(payload.kindLabels[kind]) || kind;
    }}

    function statusLabel(status) {{
      return ui(`status.${{status}}`) || status;
    }}

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function looksLikeUrl(value) {{
      return /^https?:\\/\\/\\S+$/i.test(String(value ?? "").trim());
    }}

    function renderMetaValue(value, options = {{}}) {{
      const text = String(value ?? "").trim();
      if (!text) {{
        return "";
      }}
      const href = String(options.href ?? "").trim();
      if ((options.preferLink && looksLikeUrl(text)) || (href && looksLikeUrl(href))) {{
        const target = href || text;
        return `<a class="meta-link" href="${{escapeHtml(target)}}" target="_blank" rel="noopener">${{escapeHtml(text)}}</a>`;
      }}
      return `<span class="mono">${{escapeHtml(text)}}</span>`;
    }}

    function renderLanguageSelect() {{
      const select = document.getElementById("language-select");
      select.innerHTML = "";
      for (const option of payload.languages) {{
        const node = document.createElement("option");
        node.value = option.code;
        node.textContent = option.label;
        if (option.code === currentLang) {{
          node.selected = true;
        }}
        select.appendChild(node);
      }}
    }}

    function renderHero() {{
      document.getElementById("eyebrow").textContent = ui("eyebrow");
      document.getElementById("title").textContent = payload.title;
      document.getElementById("summary").textContent = localizedValue(payload.summary);
      const notice = localizedValue(payload.notice);
      const noticeNode = document.getElementById("notice");
      noticeNode.textContent = notice;
      noticeNode.hidden = !notice;
      document.getElementById("refresh-button").textContent = ui("refreshLabel");
      document.getElementById("full-readme-button").textContent = ui("englishReference");
      document.getElementById("metric-services-label").textContent = ui("serviceCount");
      document.getElementById("metric-pages-label").textContent = ui("pageCount");
      document.getElementById("metric-launcher-label").textContent = ui("launcherPath");
      document.getElementById("metric-services-value").textContent = String(payload.services.length);
      document.getElementById("metric-pages-value").textContent = String(payload.browserPages.length);
      document.getElementById("metric-launcher-value").textContent = payload.runScriptPath;
      const badges = document.getElementById("context-badges");
      badges.innerHTML = "";
      for (const item of payload.contextBadges || []) {{
        const badge = document.createElement("span");
        badge.className = "context-badge";
        badge.textContent = item;
        badges.appendChild(badge);
      }}
    }}

    function renderPages() {{
      document.getElementById("pages-label").textContent = ui("pagesLabel");
      const pageList = document.getElementById("page-list");
      pageList.innerHTML = "";
      const combinedPages = [
        {{
          label: ui("summaryLabel"),
          url: currentStatus?.guide_url || window.location.origin + "/",
          description: payload.title,
          auto_open: true,
        }},
        ...payload.browserPages,
      ];
      for (const page of combinedPages) {{
        const card = document.createElement("article");
        card.className = "page-card" + (page.auto_open ? " auto-open" : "");
        const autoOpenChip = page.auto_open ? '<span class="chip">auto-open</span>' : "";
        card.innerHTML = `
          <div class="service-head">
            <div>
              <p class="service-name">${{page.label}}</p>
            </div>
            <a class="button ghost" href="${{page.url}}" target="_blank" rel="noopener">${{ui("openLabel")}}</a>
          </div>
          <p class="page-description">${{page.description || ""}}</p>
          <div class="meta-grid">
            <div class="meta-item">
              <strong>URL</strong>
              ${{renderMetaValue(page.url, {{ preferLink: true }})}}
            </div>
          </div>
          ${{autoOpenChip}}
        `;
        pageList.appendChild(card);
      }}
    }}

    function renderServices() {{
      document.getElementById("stack-label").textContent = ui("stackLabel");
      const serviceList = document.getElementById("service-list");
      serviceList.innerHTML = "";
      const runtimeServices = new Map((currentStatus?.services || []).map((item) => [item.name, item]));
      for (const service of payload.services) {{
        const runtime = runtimeServices.get(service.name) || {{
          status: "pending",
          status_detail: "",
          log_path: "",
          pid: 0,
        }};
        const card = document.createElement("article");
        card.className = "service-card";
        const detail = runtime.status_detail ? `<p class="service-description">${{service.description}}<br><strong style="color:var(--ink)">Status:</strong> ${{runtime.status_detail}}</p>` : `<p class="service-description">${{service.description}}</p>`;
        const uiButton = service.uiUrl
          ? `<a class="button ghost" href="${{service.uiUrl}}" target="_blank" rel="noopener">${{ui("openLabel")}}</a>`
          : "";
        const uiMeta = service.uiUrl
          ? `<div class="meta-item"><strong>${{ui("uiLabel")}}</strong>${{renderMetaValue(service.uiUrl, {{ preferLink: true }})}}</div>`
          : "";
        const logMeta = (runtime.log_path || "").trim()
          ? `<div class="meta-item"><strong>${{ui("logLabel")}}</strong>${{renderMetaValue(runtime.log_path)}}</div>`
          : "";
        card.innerHTML = `
          <div class="service-head">
            <div>
              <p class="service-name">${{service.name}}</p>
              <div class="service-kind">${{kindLabel(service.kind)}}</div>
            </div>
            <div class="button-row">
              <span class="status-pill ${{runtime.status}}">${{statusLabel(runtime.status)}}</span>
              ${{uiButton}}
            </div>
          </div>
          ${{detail}}
          <div class="meta-grid">
            <div class="meta-item">
              <strong>${{ui("healthLabel")}}</strong>
              ${{renderMetaValue(service.healthUrl, {{ preferLink: true }})}}
            </div>
            <div class="meta-item">
              <strong>${{ui("runLabel")}}</strong>
              ${{renderMetaValue(service.commandLabel)}}
            </div>
            ${{uiMeta}}
            ${{logMeta}}
          </div>
        `;
        serviceList.appendChild(card);
      }}
    }}

    function renderEnv() {{
      document.getElementById("environment-label").textContent = ui("environmentLabel");
      const list = document.getElementById("env-list");
      list.innerHTML = "";
      const items = payload.envOptions || [];
      if (!items.length) {{
        const empty = document.createElement("article");
        empty.className = "env-card";
        empty.innerHTML = `<p class="env-description" style="margin:0;">${{ui("emptyEnv")}}</p>`;
        list.appendChild(empty);
        return;
      }}
      for (const item of items) {{
        const card = document.createElement("article");
        card.className = "env-card";
        card.innerHTML = `
          <div class="service-head">
            <div>
              <p class="service-name">${{item.name}}</p>
            </div>
          </div>
          <p class="env-description">${{localizedValue(item.description)}}</p>
          <div class="meta-grid">
            <div class="meta-item">
              <strong>${{ui("defaultLabel")}}</strong>
              <span>${{item.default}}</span>
            </div>
            <div class="meta-item">
              <strong>${{ui("choicesLabel")}}</strong>
              <span>${{item.choices}}</span>
            </div>
          </div>
        `;
        list.appendChild(card);
      }}
    }}

    function renderCommandAndReadme() {{
      document.getElementById("run-label").textContent = ui("runLabel");
      document.getElementById("launch-command").textContent = payload.runScriptPath;
      document.getElementById("copy-command-button").textContent = ui("copyLabel");
      document.getElementById("readme-label").textContent = ui("readmeLabel");
      document.getElementById("readme-path-label").textContent = "README.md";
      document.getElementById("readme-path-value").innerHTML = renderMetaValue(payload.readmePath);
      document.getElementById("generic-notes-label").textContent = ui("genericNotesLabel");
      const notes = document.getElementById("generic-notes");
      notes.innerHTML = "";
      for (const key of ["noteOne", "noteTwo", "noteThree"]) {{
        const card = document.createElement("article");
        card.className = "note-card";
        card.textContent = ui(key);
        notes.appendChild(card);
      }}
    }}

    function renderErrors() {{
      const node = document.getElementById("error-banner");
      const errors = currentStatus?.errors || [];
      if (!errors.length) {{
        node.classList.remove("visible");
        node.textContent = "";
        return;
      }}
      node.classList.add("visible");
      node.textContent = errors[errors.length - 1];
    }}

    function renderAll() {{
      renderLanguageSelect();
      renderHero();
      renderPages();
      renderServices();
      renderEnv();
      renderCommandAndReadme();
      renderErrors();
    }}

    async function refreshStatus() {{
      try {{
        const response = await fetch(payload.statusUrl, {{ cache: "no-store" }});
        if (!response.ok) {{
          throw new Error(`HTTP ${{response.status}}`);
        }}
        currentStatus = await response.json();
      }} catch (error) {{
        currentStatus = currentStatus || {{ services: [], errors: [] }};
        currentStatus.errors = [String(error)];
      }}
      renderAll();
    }}

    document.getElementById("language-select").addEventListener("change", (event) => {{
      currentLang = event.target.value || "en";
      window.localStorage.setItem(storageKey, currentLang);
      renderAll();
    }});
    document.getElementById("refresh-button").addEventListener("click", () => {{
      refreshStatus();
    }});
    document.getElementById("copy-command-button").addEventListener("click", async () => {{
      try {{
        await navigator.clipboard.writeText(payload.runScriptPath);
      }} catch (_error) {{
        const textArea = document.createElement("textarea");
        textArea.value = payload.runScriptPath;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        textArea.remove();
      }}
    }});

    renderAll();
    refreshStatus();
    window.setInterval(refreshStatus, 2000);
  </script>
</body>
</html>"""


class GuideHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying launcher state."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], handler_class, *, spec: DemoSpec, state: LauncherState):
        """Initialize the guide server."""
        super().__init__(server_address, handler_class)
        self.spec = spec
        self.state = state


class GuideRequestHandler(BaseHTTPRequestHandler):
    """Serve the demo guide and status endpoints."""

    server: GuideHTTPServer

    def log_message(self, format: str, *args):  # pragma: no cover - quiet handler
        """Suppress default noisy request logging."""
        return

    def _send_bytes(self, payload: bytes, *, content_type: str = "text/html; charset=utf-8", status_code: int = 200):
        """Send one response payload."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler interface
        """Handle guide server routes."""
        path = urlparse(self.path).path
        if path in {"/", "/index.html"}:
            html = _build_main_page_html(self.server.spec).encode("utf-8")
            self._send_bytes(html)
            return
        if path == "/api/status":
            payload = json.dumps(self.server.state.snapshot(), ensure_ascii=False).encode("utf-8")
            self._send_bytes(payload, content_type="application/json; charset=utf-8")
            return
        if path == "/full-readme":
            html = _build_full_readme_html(self.server.spec).encode("utf-8")
            self._send_bytes(html)
            return
        if path == "/health":
            payload = json.dumps({"status": "ok"}).encode("utf-8")
            self._send_bytes(payload, content_type="application/json; charset=utf-8")
            return
        self._send_bytes(b"Not Found", content_type="text/plain; charset=utf-8", status_code=404)


def _start_guide_server(spec: DemoSpec, state: LauncherState) -> GuideHTTPServer:
    """Start the local guide server."""
    port = _find_free_port("127.0.0.1")
    server = GuideHTTPServer(("127.0.0.1", port), GuideRequestHandler, spec=spec, state=state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    guide_url = f"http://127.0.0.1:{port}/"
    full_readme_url = urljoin(guide_url, "full-readme")
    state.set_urls(guide_url, full_readme_url)
    return server


def _launch_service(spec: ServiceSpec, state: LauncherState, log_root: Path) -> bool:
    """Launch or reuse one service."""
    healthy, detail = _probe_service(spec)
    if healthy:
        state.mark_service(spec.name, status="external", detail="reused existing healthy service")
        return True

    log_path = log_root / f"{_safe_slug(spec.name)}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    state.mark_service(spec.name, status="launching", detail="starting process", log_path=str(log_path))
    with log_path.open("ab") as handle:
        process = subprocess.Popen(
            list(spec.command),
            cwd=str(REPO_ROOT),
            env=_merge_env(spec.env),
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    state.record_process(spec.name, process)
    state.mark_service(
        spec.name,
        status="launching",
        detail=f"waiting for {spec.health_url}",
        pid=process.pid,
        managed=True,
        log_path=str(log_path),
    )
    ok, wait_detail = _wait_for_service(spec, timeout_sec=spec.timeout_sec)
    if ok:
        state.mark_service(spec.name, status="ready", detail="healthy", pid=process.pid, managed=True, log_path=str(log_path))
        return True

    _terminate_process(process)
    log_tail = _tail_log(log_path)
    message = f"{spec.name} did not become healthy: {wait_detail or 'timeout'}"
    if log_tail:
        message = f"{message}\n{log_tail}"
    state.mark_service(spec.name, status="failed", detail=wait_detail or "timeout", pid=process.pid, managed=True, log_path=str(log_path))
    state.add_error(message)
    return False


def _open_browser_pages(state: LauncherState, spec: DemoSpec, *, open_browser: bool):
    """Open the guide and main demo pages in the default browser."""
    if not open_browser:
        return
    urls = [state.guide_url]
    urls.extend(page.url for page in spec.browser_pages if page.auto_open)
    seen: set[str] = set()
    for url in urls:
        normalized = str(url or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        with contextlib.suppress(Exception):
            webbrowser.open_new_tab(normalized)
        time.sleep(0.25)


def _monitor_processes(state: LauncherState):
    """Watch managed processes and record unexpected exits."""
    seen_failures: set[str] = set()
    while True:
        for service_name, process in state.get_process_items():
            if process.poll() is None:
                continue
            key = f"{service_name}:{process.pid}"
            if key in seen_failures:
                continue
            seen_failures.add(key)
            with state.lock:
                entry = state.services.get(service_name, {})
                current_status = str(entry.get("status") or "")
                log_path = Path(str(entry.get("log_path") or ""))
            if current_status in {"failed", "stopped"}:
                continue
            detail = f"process exited with code {process.returncode}"
            log_tail = _tail_log(log_path)
            if log_tail:
                detail = f"{detail}\n{log_tail}"
            state.mark_service(service_name, status="failed", detail=f"exit code {process.returncode}")
            state.add_error(detail)
        time.sleep(1.0)


def _print_launch_header(spec: DemoSpec, state: LauncherState):
    """Print startup banner information."""
    print(f"demo={spec.demo_id}")
    print(f"title={spec.title}")
    print(f"guide={state.guide_url}")
    print(f"readme={state.full_readme_url}")
    print(f"launcher={spec.run_script_path}")


def _cleanup(state: LauncherState, server: GuideHTTPServer | None):
    """Stop managed processes and the guide server."""
    for service_name, process in reversed(state.get_process_items()):
        _terminate_process(process)
        with state.lock:
            entry = state.services.get(service_name)
            if entry and entry.get("status") not in {"external", "failed"}:
                entry["status"] = "stopped"
                entry["status_detail"] = "stopped by launcher"
                entry["updated_at"] = _now_iso()
    if server is not None:
        with contextlib.suppress(Exception):
            server.shutdown()
        with contextlib.suppress(Exception):
            server.server_close()


def run_demo(spec: DemoSpec, *, open_browser: bool = True) -> int:
    """Run one demo until interrupted."""
    state = LauncherState(spec)
    server = _start_guide_server(spec, state)
    log_root = Path(spec.readme_path).resolve().parent / "logs"
    monitor_thread = threading.Thread(target=_monitor_processes, args=(state,), daemon=True)
    monitor_thread.start()
    _print_launch_header(spec, state)
    _open_browser_pages(state, spec, open_browser=open_browser)

    launch_ok = True
    try:
        for service in spec.services:
            if not _launch_service(service, state, log_root):
                launch_ok = False
                break
        if launch_ok:
            # Re-open the main UI pages after all services are healthy so the guide
            # page lands first and the interactive pages land second.
            _open_browser_pages(state, spec, open_browser=open_browser)
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup(state, server)
    return 0 if launch_ok and not state.snapshot().get("errors") else 1


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description="Run a public demo from one script.")
    parser.add_argument("demo", nargs="?", help=f"Demo ID. Choices: {', '.join(available_demo_ids())}")
    parser.add_argument("--list", action="store_true", help="List supported demo IDs and exit.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser tabs automatically.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.list:
        for demo_id in available_demo_ids():
            spec = resolve_demo_spec(demo_id, dict(os.environ))
            print(f"{demo_id}: {spec.run_script_path}")
        return 0
    if not args.demo:
        parser.error("demo is required unless --list is used.")
    spec = resolve_demo_spec(args.demo, dict(os.environ))
    open_browser = not args.no_browser and str(os.environ.get("DEMO_OPEN_BROWSER") or "1").strip() != "0"
    return run_demo(spec, open_browser=open_browser)


if __name__ == "__main__":
    raise SystemExit(main())
