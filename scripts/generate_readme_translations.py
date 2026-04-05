#!/usr/bin/env python3
"""Generate full translated companion files for first-party README documents."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]

README_PATHS = [
    Path("README.md"),
    Path("ads/README.md"),
    Path("attas/README.md"),
    Path("demos/README.md"),
    Path("demos/data-pipeline/README.md"),
    Path("demos/files/diagrams/README.md"),
    Path("demos/hello-plaza/README.md"),
    Path("demos/personal-research-workbench/README.md"),
    Path("demos/pulsers/README.md"),
    Path("demos/pulsers/ads/README.md"),
    Path("demos/pulsers/analyst-insights/README.md"),
    Path("demos/pulsers/file-storage/README.md"),
    Path("demos/pulsers/finance-briefings/README.md"),
    Path("demos/pulsers/llm/README.md"),
    Path("demos/pulsers/yfinance/README.md"),
    Path("phemacast/README.md"),
    Path("phemacast/personal_agent/README.md"),
    Path("prompits/README.md"),
    Path("prompits/dispatcher/README.md"),
    Path("prompits/examples/README.md"),
]

LANGUAGE_OPTIONS = [
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

TRANSLATIONS_HEADING = {
    "en": "Translations",
    "zh-Hant": "翻譯版本",
    "zh-Hans": "翻译版本",
    "es": "Traducciones",
    "fr": "Traductions",
    "it": "Traduzioni",
    "de": "Uebersetzungen",
    "ja": "翻訳版",
    "ko": "번역본",
}

TARGET_LANGUAGE_DESCRIPTIONS = {
    "zh-Hant": "Traditional Chinese used for technical readers in Taiwan or Hong Kong",
    "zh-Hans": "Simplified Chinese used for technical readers in Mainland China",
    "es": "Spanish",
    "fr": "French",
    "it": "Italian",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
}

NON_ENGLISH_LANGUAGE_CODES = [code for code, _label in LANGUAGE_OPTIONS if code != "en"]

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("FINMAS_README_TRANSLATION_MODEL", "gemma4:26b")
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("FINMAS_README_TRANSLATION_TIMEOUT", "600"))
MAX_CHUNK_SOURCE_CHARS = int(os.environ.get("FINMAS_README_TRANSLATION_CHUNK_CHARS", "1800"))
MAX_TRANSLATION_ATTEMPTS = 3

OUTER_CODE_FENCE_RE = re.compile(r"^\s*```(?:markdown)?\n(.*)\n```\s*$", re.S)
HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+", re.M)

COMMON_POSTPROCESS_RULES: tuple[tuple[str, str], ...] = (
    (r"Pl\xa0laza", "Plaza"),
    (r"Pl laza", "Plaza"),
    (r"phemagast", "phemacast"),
    (r"attাস", "attas"),
)

LANGUAGE_POSTPROCESS_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "zh-Hans": (
        (r"\buser-agent\b", "用户代理"),
        (r"\buser agent\b", "用户代理"),
        (r"基準 worker", "基线 worker"),
        (r"金融智慧", "金融智能"),
        (r"服务提供 供应商", "服务提供商"),
        (r"财务数据与分析", "金融数据与分析"),
        (r"财政摘要", "司库摘要"),
        (r"财政工具", "司库工具"),
        (r"财政经理", "司库经理"),
        (r"财库与流动性报告", "司库与流动性报告"),
        (r"财资团队", "司库团队"),
        (r"投资与财务工作流", "投资与司库工作流"),
        (r"投资与财务运营", "投资与司库运营"),
        (r"内部财务 Copilots", "内部金融 Copilot"),
        (r"脉冲", "Pulse"),
    ),
    "zh-Hant": (
        (r"\buser-agent\b", "用戶代理"),
        (r"\buser agent\b", "用戶代理"),
        (r"基準 worker", "基線 worker"),
        (r"金融智慧", "金融智能"),
        (r"財務數據與分析", "金融數據與分析"),
        (r"財務摘要", "司庫摘要"),
        (r"財務工具", "司庫工具"),
        (r"財務經理", "司庫經理"),
        (r"財務與流動性報告", "司庫與流動性報告"),
        (r"財資團隊", "司庫團隊"),
        (r"投資與財務工作流", "投資與司庫工作流"),
        (r"投資與財務營運", "投資與司庫營運"),
        (r"內部財務 Copilots", "內部金融 Copilot"),
        (r"LL 模組", "LLM"),
        (r"脈衝", "Pulse"),
    ),
    "ja": (
        (r"user-agent", "ユーザーエージェント"),
        (r"user agent", "ユーザーエージェント"),
        (r"prompts/README\.md", "prompits/README.md"),
        (r"財務データと分析", "金融データと分析"),
        (r"財務サマリー", "トレジャリー概要"),
        (r"財務チーム", "トレジャリーチーム"),
        (r"財務および流動性レポート", "トレジャリーおよび流動性レポート"),
        (r"内部財務Copilot", "内部金融Copilot"),
        (r"投資および財務業務", "投資およびトレジャリー業務"),
        (r"投資および財務ワークフロー", "投資およびトレジャリーワークフロー"),
        (r"パルス", "Pulse"),
    ),
}


def translation_filename(readme_path: Path, lang_code: str) -> Path:
    return readme_path.with_name(f"README.{lang_code}.md")


def relative_link(_from_path: Path, to_path: Path) -> str:
    return to_path.name


def strip_generated_sections(text: str) -> str:
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## Multilingual Summary"):
            i += 1
            while i < len(lines):
                current = lines[i]
                if current.startswith("## "):
                    break
                if current.startswith("<details>") or current.startswith("<summary>") or current.startswith("</details>"):
                    i += 1
                    continue
                if current.strip() == "":
                    i += 1
                    continue
                break
            continue
        if line.startswith("## Language Availability") or line.startswith("## Translations"):
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        output.append(line)
        i += 1
    return normalize_spacing("".join(output))


def normalize_spacing(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{4,}", "\n\n\n", text)


def postprocess_translation(text: str, lang_code: str) -> str:
    normalized = text.replace("\u00a0", " ")
    for pattern, replacement in COMMON_POSTPROCESS_RULES:
        normalized = re.sub(pattern, replacement, normalized)
    for pattern, replacement in LANGUAGE_POSTPROCESS_RULES.get(lang_code, ()):
        normalized = re.sub(pattern, replacement, normalized)
    return normalize_spacing(normalized)


def extract_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise ValueError("README missing H1 title")


def split_readme(text: str) -> tuple[str, str, str, str]:
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].startswith("# "):
        raise ValueError("README missing H1 title")
    title_line = lines[0]
    blank = "\n"
    idx = 1
    if idx < len(lines) and lines[idx].strip() == "":
        blank = lines[idx]
        idx += 1
    preamble: list[str] = []
    while idx < len(lines) and not lines[idx].startswith("## "):
        preamble.append(lines[idx])
        idx += 1
    return title_line, blank, "".join(preamble), "".join(lines[idx:])


def split_top_level_sections(text: str) -> list[str]:
    if not text.strip():
        return []
    sections: list[str] = []
    current: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.startswith("## ") and current:
            sections.append("".join(current))
            current = [line]
            continue
        current.append(line)
    if current:
        sections.append("".join(current))
    return [normalize_spacing(section) for section in sections if section.strip()]


def split_markdown_blocks(text: str) -> list[str]:
    if not text:
        return []
    blocks: list[str] = []
    current: list[str] = []
    in_code_fence = False
    for line in text.splitlines(keepends=True):
        current.append(line)
        if line.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if not in_code_fence and line.strip() == "":
            blocks.append("".join(current))
            current = []
    if current:
        blocks.append("".join(current))
    return blocks


def split_large_plain_block(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars or block.lstrip().startswith("```"):
        return [block]
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in block.splitlines(keepends=True):
        if current and current_len + len(line) > max_chars:
            pieces.append("".join(current))
            current = [line]
            current_len = len(line)
            continue
        current.append(line)
        current_len += len(line)
    if current:
        pieces.append("".join(current))
    return pieces


def chunk_markdown(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    expanded_blocks: list[str] = []
    for block in split_markdown_blocks(text):
        expanded_blocks.extend(split_large_plain_block(block, max_chars=max_chars))

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for block in expanded_blocks:
        block_len = len(block)
        if current and current_len + block_len > max_chars:
            chunks.append("".join(current))
            current = [block]
            current_len = block_len
            continue
        current.append(block)
        current_len += block_len
    if current:
        chunks.append("".join(current))
    return [chunk for chunk in chunks if chunk.strip()]


def split_translatable_segments(text: str, max_chars: int) -> list[tuple[bool, str]]:
    segments: list[tuple[bool, str]] = []
    pending: list[str] = []
    pending_len = 0

    def flush_pending() -> None:
        nonlocal pending, pending_len
        if not pending:
            return
        joined = "".join(pending)
        for chunk in chunk_markdown(joined, max_chars=max_chars):
            segments.append((True, chunk))
        pending = []
        pending_len = 0

    for block in split_markdown_blocks(text):
        if block.lstrip().startswith("```"):
            flush_pending()
            segments.append((False, block))
            continue
        if pending and pending_len + len(block) > max_chars:
            flush_pending()
        pending.append(block)
        pending_len += len(block)

    flush_pending()
    return segments


def head_preamble(rel_path: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "show", f"HEAD:{rel_path.as_posix()}"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return ""
    _title, _blank, preamble, _rest = split_readme(completed.stdout)
    return preamble


def build_translation_links(readme_path: Path, lang_code: str) -> str:
    lines = [f"## {TRANSLATIONS_HEADING[lang_code]}", ""]
    for code, label in LANGUAGE_OPTIONS:
        target = readme_path.name if code == "en" else translation_filename(readme_path, code).name
        lines.append(f"- [{label}]({target})")
    return "\n".join(lines).rstrip() + "\n\n"


def inject_translation_links(document_text: str, readme_path: Path, lang_code: str) -> str:
    stripped = strip_generated_sections(document_text)
    title_line, blank, preamble, rest = split_readme(stripped)
    rebuilt = title_line + blank + build_translation_links(readme_path, lang_code)
    if preamble:
        rebuilt += preamble
        if not preamble.endswith("\n\n"):
            rebuilt += "\n"
    rebuilt += rest
    normalized = normalize_spacing(rebuilt).rstrip() + "\n"
    return normalized


def update_english_readme(readme_path: Path) -> str:
    english_text = readme_path.read_text(encoding="utf-8")
    stripped = strip_generated_sections(english_text)
    title_line, blank, preamble, rest = split_readme(stripped)
    if not preamble.strip():
        preamble = head_preamble(readme_path.relative_to(REPO_ROOT))
    rebuilt = title_line + blank + build_translation_links(readme_path.relative_to(REPO_ROOT), "en")
    if preamble:
        rebuilt += preamble
        if not preamble.endswith("\n\n"):
            rebuilt += "\n"
    rebuilt += rest
    return normalize_spacing(rebuilt)


def heading_signature(text: str) -> list[int]:
    return [len(match.group(1)) for match in re.finditer(r"^(#{1,6})\s+", text, flags=re.M)]


def code_fence_count(text: str) -> int:
    return len(re.findall(r"^```", text, flags=re.M))


def nonempty_line_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def validate_translation_shape(
    source_text: str,
    translated_text: str,
    *,
    minimum_content_ratio: float = 0.25,
    minimum_content_chars: int = 20,
) -> list[str]:
    problems: list[str] = []
    source_heading = HEADING_LINE_RE.match(source_text.lstrip())
    translated_heading = HEADING_LINE_RE.match(translated_text.lstrip())
    if source_heading:
        if not translated_heading:
            problems.append("output does not start with the expected heading")
        elif translated_heading.group(1) != source_heading.group(1):
            problems.append("output starts with the wrong heading level")
    if heading_signature(translated_text) != heading_signature(source_text):
        problems.append("heading levels do not match the source README")
    if code_fence_count(translated_text) != code_fence_count(source_text):
        problems.append("fenced code block count does not match the source README")
    source_compact_chars = len(re.sub(r"\s+", "", source_text))
    translated_compact_chars = len(re.sub(r"\s+", "", translated_text))
    minimum_required_chars = max(minimum_content_chars, int(source_compact_chars * minimum_content_ratio))
    if translated_compact_chars < minimum_required_chars:
        problems.append("translated output is too short to be a full README translation")
    return problems


def strip_outer_markdown_fence(response_text: str) -> str:
    cleaned = response_text.replace("\r\n", "\n").replace("\r", "\n").strip()
    fenced = OUTER_CODE_FENCE_RE.match(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    return cleaned


def clean_translated_snippet(source_text: str, response_text: str) -> str:
    cleaned = strip_outer_markdown_fence(response_text)
    if not HEADING_LINE_RE.match(cleaned):
        source_heading = HEADING_LINE_RE.match(source_text.lstrip())
        if source_heading:
            heading_match = HEADING_LINE_RE.search(cleaned)
            if heading_match:
                cleaned = cleaned[heading_match.start():].lstrip()
    suffix = "\n" if source_text.endswith("\n") else ""
    return cleaned.rstrip() + suffix


def language_block_start(lang_code: str) -> str:
    return f"<<<LANG:{lang_code}>>>"


def language_block_end(lang_code: str) -> str:
    return f"<<<END:{lang_code}>>>"


def build_multilingual_translation_prompt(
    readme_path: Path,
    source_markdown: str,
    snippet_label: str,
    lang_codes: list[str],
    prior_errors: dict[str, list[str]] | None,
) -> str:
    requested_languages = "\n".join(
        f"- {code}: {TARGET_LANGUAGE_DESCRIPTIONS[code]}" for code in lang_codes
    )
    response_template = "\n".join(
        f"{language_block_start(code)}\n...\n{language_block_end(code)}" for code in lang_codes
    )
    validation_note = ""
    if prior_errors:
        joined = "; ".join(f"{code}: {', '.join(errors)}" for code, errors in prior_errors.items())
        validation_note = f"\nFix these validation issues from the previous attempt: {joined}.\n"

    return (
        "Translate this markdown snippet from English into all requested target languages.\n"
        "Return only the exact tagged block format shown below.\n"
        "Preserve the snippet completely for every language.\n"
        "Keep the same markdown structure, heading levels, bullets, tables, and code fences.\n"
        "Keep code blocks, inline code, URLs, file paths, env vars, CLI flags, JSON/YAML keys, and link targets unchanged.\n"
        "Translate only human-readable prose and link labels.\n"
        "Keep these names unchanged: FinMAS, ADS, Attas, Prompits, Phemacast, Plaza, Pulser, Phemar, Castr, BossPulser, SystemPulser, YFinance, OpenAI, Ollama, MCP.\n"
        "Do not omit any requested language.\n"
        "Do not add commentary before, after, or between the tagged language blocks.\n"
        f"{validation_note}"
        f"\nPath: {readme_path.as_posix()}\nSnippet: {snippet_label}\n"
        f"\nTarget languages:\n{requested_languages}\n"
        f"\nReturn format:\n{response_template}\n"
        "\n<source_markdown>\n"
        f"{source_markdown}"
        "\n</source_markdown>\n"
    )


def estimate_num_predict(source_markdown: str, attempt: int, language_count: int) -> int:
    multiplier = 0.2 + (0.9 * language_count)
    base = int(len(source_markdown) * multiplier)
    floor = max(160, 120 * language_count)
    ceiling = 16000
    padded = int(base * (1 + 0.2 * (attempt - 1)))
    return max(floor, min(ceiling, padded))


def ollama_generate(prompt: str, model: str, ollama_url: str, timeout: int, num_predict: int) -> str:
    endpoint = ollama_url.rstrip("/") + "/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "think": False,
        "options": {
            "temperature": 0,
            "num_predict": num_predict,
        },
        "keep_alive": "30m",
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    fragments: list[str] = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            payload = json.loads(line)
            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))
            fragments.append(payload.get("response", ""))
            if payload.get("done"):
                break
    text = "".join(fragments)
    if not text.strip():
        raise RuntimeError(f"Ollama returned an empty response for model {model}")
    return text


def parse_multilingual_response(response_text: str, lang_codes: list[str]) -> dict[str, str]:
    cleaned = strip_outer_markdown_fence(response_text)
    translations: dict[str, str] = {}
    cursor = 0
    for code in lang_codes:
        start_marker = language_block_start(code)
        end_marker = language_block_end(code)
        start_index = cleaned.find(start_marker, cursor)
        if start_index == -1:
            raise RuntimeError(f"Missing language block start for {code}")
        body_start = start_index + len(start_marker)
        if body_start < len(cleaned) and cleaned[body_start] == "\n":
            body_start += 1
        end_index = cleaned.find(end_marker, body_start)
        if end_index == -1:
            raise RuntimeError(f"Missing language block end for {code}")
        translations[code] = cleaned[body_start:end_index]
        cursor = end_index + len(end_marker)
    return translations


def translate_markdown_snippet_all_languages(
    readme_path: Path,
    source_snippet: str,
    snippet_label: str,
    lang_codes: list[str],
    model: str,
    ollama_url: str,
    timeout: int,
) -> dict[str, str]:
    last_errors: dict[str, list[str]] | None = None

    for attempt in range(1, MAX_TRANSLATION_ATTEMPTS + 1):
        print(
            f"    attempt {attempt}/{MAX_TRANSLATION_ATTEMPTS} for {snippet_label} [{', '.join(lang_codes)}]",
            flush=True,
        )
        prompt = build_multilingual_translation_prompt(
            readme_path,
            source_snippet,
            snippet_label,
            lang_codes,
            last_errors,
        )
        num_predict = estimate_num_predict(source_snippet, attempt, len(lang_codes))
        print(f"    num_predict={num_predict}", flush=True)
        try:
            raw = ollama_generate(
                prompt,
                model=model,
                ollama_url=ollama_url,
                timeout=timeout,
                num_predict=num_predict,
            )
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to reach Ollama at {ollama_url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP error {exc.code}: {body}") from exc

        try:
            raw_translations = parse_multilingual_response(raw, lang_codes)
        except RuntimeError as exc:
            last_errors = {code: [str(exc)] for code in lang_codes}
            print(f"    validation retry needed: {exc}", flush=True)
            if attempt < MAX_TRANSLATION_ATTEMPTS:
                time.sleep(1)
            continue

        cleaned_translations: dict[str, str] = {}
        current_errors: dict[str, list[str]] = {}
        total_chars = 0
        for code in lang_codes:
            cleaned = clean_translated_snippet(source_snippet, raw_translations[code])
            cleaned_translations[code] = cleaned
            total_chars += len(cleaned)
            issues = validate_translation_shape(
                source_snippet,
                cleaned,
                minimum_content_ratio=0.18,
                minimum_content_chars=3,
            )
            if issues:
                current_errors[code] = issues

        print(f"    received {total_chars} translated characters across {len(lang_codes)} languages", flush=True)
        last_errors = current_errors
        if not last_errors:
            return cleaned_translations

        joined = "; ".join(f"{code}: {', '.join(errors)}" for code, errors in last_errors.items())
        print(f"    validation retry needed: {joined}", flush=True)
        if attempt < MAX_TRANSLATION_ATTEMPTS:
            time.sleep(1)

    detail = "; ".join(
        f"{code}: {', '.join(errors)}" for code, errors in (last_errors or {}).items()
    ) or "unknown validation error"
    raise RuntimeError(
        f"Unable to generate valid translations for {readme_path.as_posix()} ({snippet_label}) in {', '.join(lang_codes)}: {detail}"
    )


def translate_markdown_part(
    readme_path: Path,
    part_text: str,
    part_label: str,
    lang_codes: list[str],
    model: str,
    ollama_url: str,
    timeout: int,
) -> dict[str, str]:
    if not part_text.strip():
        return {code: "" for code in lang_codes}
    segments = split_translatable_segments(part_text, max_chars=MAX_CHUNK_SOURCE_CHARS)
    translated_segments: dict[str, list[str]] = {code: [] for code in lang_codes}
    translatable_count = sum(1 for is_translatable, _segment in segments if is_translatable)
    translated_index = 0

    for is_translatable, segment in segments:
        if not is_translatable:
            for code in lang_codes:
                translated_segments[code].append(segment)
            continue
        translated_index += 1
        label = f"{part_label} chunk {translated_index}/{translatable_count}"
        try:
            translated = translate_markdown_snippet_all_languages(
                readme_path,
                segment,
                label,
                lang_codes,
                model=model,
                ollama_url=ollama_url,
                timeout=timeout,
            )
        except RuntimeError:
            translated = translate_markdown_lines_all_languages(
                readme_path,
                segment,
                label,
                lang_codes,
                model=model,
                ollama_url=ollama_url,
                timeout=timeout,
            )
        for code in lang_codes:
            translated_segments[code].append(translated[code])
    return {code: "".join(parts) for code, parts in translated_segments.items()}


def translate_markdown_lines_all_languages(
    readme_path: Path,
    source_text: str,
    part_label: str,
    lang_codes: list[str],
    model: str,
    ollama_url: str,
    timeout: int,
) -> dict[str, str]:
    lines = source_text.splitlines(keepends=True)
    translated_lines: dict[str, list[str]] = {code: [] for code in lang_codes}
    translatable_lines = [line for line in lines if line.strip()]
    total = len(translatable_lines)
    current = 0
    for line in lines:
        if not line.strip():
            for code in lang_codes:
                translated_lines[code].append(line)
            continue
        current += 1
        translated = translate_markdown_snippet_all_languages(
            readme_path,
            line,
            f"{part_label} fallback line {current}/{total}",
            lang_codes,
            model=model,
            ollama_url=ollama_url,
            timeout=timeout,
        )
        for code in lang_codes:
            translated_lines[code].append(translated[code])
    return {code: "".join(parts) for code, parts in translated_lines.items()}


def translate_full_readme(
    readme_path: Path,
    english_text: str,
    lang_codes: list[str],
    model: str,
    ollama_url: str,
    timeout: int,
) -> dict[str, str]:
    source_core = strip_generated_sections(english_text)
    title_line, _blank, preamble, rest = split_readme(source_core)
    translated_title = translate_markdown_snippet_all_languages(
        readme_path,
        title_line,
        "title",
        lang_codes,
        model=model,
        ollama_url=ollama_url,
        timeout=timeout,
    )
    translated_preamble = translate_markdown_part(
        readme_path,
        preamble,
        "preamble",
        lang_codes,
        model=model,
        ollama_url=ollama_url,
        timeout=timeout,
    )

    translated_sections: list[dict[str, str]] = []
    for index, section in enumerate(split_top_level_sections(rest), start=1):
        translated_sections.append(
            translate_markdown_part(
                readme_path,
                section,
                f"section {index}",
                lang_codes,
                model=model,
                ollama_url=ollama_url,
                timeout=timeout,
            )
        )

    translated_documents: dict[str, str] = {}
    for code in lang_codes:
        pieces = [translated_title[code].rstrip(), "", build_translation_links(readme_path, code).rstrip()]
        preamble_piece = translated_preamble[code].rstrip()
        if preamble_piece:
            pieces.extend(["", preamble_piece])
        for section in translated_sections:
            section_piece = section[code].rstrip()
            if section_piece:
                pieces.extend(["", section_piece])

        translated_full = normalize_spacing("\n".join(pieces)).rstrip() + "\n"
        translated_full = postprocess_translation(translated_full, code).rstrip() + "\n"
        final_errors = validate_translation_shape(english_text, translated_full)
        if final_errors:
            detail = "; ".join(final_errors)
            raise RuntimeError(
                f"Unable to assemble a valid full translation for {readme_path.as_posix()} in {code}: {detail}"
            )
        translated_documents[code] = translated_full
    return translated_documents


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=OLLAMA_MODEL,
        help=f"Ollama model name to use (default: {OLLAMA_MODEL})",
    )
    parser.add_argument(
        "--ollama-url",
        default=OLLAMA_URL,
        help=f"Ollama base URL (default: {OLLAMA_URL})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=REQUEST_TIMEOUT_SECONDS,
        help=f"Per-request timeout in seconds (default: {REQUEST_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--readme",
        action="append",
        dest="readmes",
        help="Specific README path to process, relative to repo root. Can be repeated.",
    )
    parser.add_argument(
        "--language",
        action="append",
        dest="languages",
        choices=[code for code, _label in LANGUAGE_OPTIONS if code != "en"],
        help="Specific language code to generate. Can be repeated.",
    )
    parser.add_argument(
        "--normalize-only",
        action="store_true",
        help="Rewrite existing translated README files with glossary and typo normalization only.",
    )
    return parser.parse_args()


def selected_readmes(requested: list[str] | None) -> list[Path]:
    if not requested:
        return list(README_PATHS)
    allowed = {path.as_posix(): path for path in README_PATHS}
    chosen: list[Path] = []
    for raw in requested:
        path = allowed.get(raw)
        if path is None:
            raise SystemExit(f"Unsupported README path: {raw}")
        chosen.append(path)
    return chosen


def selected_languages(requested: list[str] | None) -> list[str]:
    if requested:
        return requested
    return list(NON_ENGLISH_LANGUAGE_CODES)


def main() -> int:
    args = parse_args()
    readmes = selected_readmes(args.readmes)
    languages = selected_languages(args.languages)

    for rel_path in readmes:
        readme_path = REPO_ROOT / rel_path
        english_text = readme_path.read_text(encoding="utf-8")
        if args.normalize_only:
            for code in languages:
                translation_path = REPO_ROOT / translation_filename(rel_path, code)
                if not translation_path.exists():
                    raise SystemExit(f"Missing translation file for normalization: {translation_path}")
                normalized = postprocess_translation(
                    translation_path.read_text(encoding="utf-8"),
                    code,
                ).rstrip() + "\n"
                final_errors = validate_translation_shape(english_text, normalized)
                if final_errors:
                    detail = "; ".join(final_errors)
                    raise RuntimeError(
                        f"Normalization produced an invalid translation for {rel_path.as_posix()} in {code}: {detail}"
                    )
                translation_path.write_text(normalized, encoding="utf-8")
            continue

        updated_english = update_english_readme(readme_path)
        readme_path.write_text(updated_english, encoding="utf-8")
        english_text = readme_path.read_text(encoding="utf-8")
        print(
            f"Translating {rel_path.as_posix()} -> {', '.join(languages)} with {args.model}",
            flush=True,
        )
        translated_documents = translate_full_readme(
            rel_path,
            english_text,
            languages,
            model=args.model,
            ollama_url=args.ollama_url,
            timeout=args.timeout,
        )
        for code in languages:
            translation_path = REPO_ROOT / translation_filename(rel_path, code)
            translation_path.write_text(translated_documents[code], encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
