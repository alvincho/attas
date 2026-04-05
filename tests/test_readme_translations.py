from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import generate_readme_translations


def test_split_top_level_sections_preserves_sections():
    text = (
        "## One\n"
        "\n"
        "Alpha\n"
        "\n"
        "## Two\n"
        "\n"
        "Beta\n"
        "### Nested\n"
        "\n"
        "Gamma\n"
    )
    sections = generate_readme_translations.split_top_level_sections(text)
    assert sections == [
        "## One\n\nAlpha\n\n",
        "## Two\n\nBeta\n### Nested\n\nGamma\n",
    ]


def test_chunk_markdown_preserves_content_and_code_fences():
    text = (
        "## Sample\n"
        "\n"
        "Paragraph one.\n"
        "\n"
        "```bash\n"
        "echo hi\n"
        "```\n"
        "\n"
        "Paragraph two.\n"
        "\n"
        "Paragraph three.\n"
    )
    chunks = generate_readme_translations.chunk_markdown(text, max_chars=32)
    assert len(chunks) >= 2
    assert "".join(chunks) == text
    assert sum(generate_readme_translations.code_fence_count(chunk) for chunk in chunks) == 2


def test_split_translatable_segments_keeps_fenced_code_verbatim():
    text = (
        "## Demo\n"
        "\n"
        "Before code.\n"
        "\n"
        "```json\n"
        "{\"ok\": true}\n"
        "```\n"
        "\n"
        "After code.\n"
    )
    segments = generate_readme_translations.split_translatable_segments(text, max_chars=40)
    assert segments == [
        (True, "## Demo\n\nBefore code.\n\n"),
        (False, "```json\n{\"ok\": true}\n```\n\n"),
        (True, "After code.\n"),
    ]


def test_parse_multilingual_response_extracts_all_requested_languages():
    raw = (
        "<<<LANG:zh-Hans>>>\n"
        "## 标题\n"
        "<<<END:zh-Hans>>>\n"
        "<<<LANG:fr>>>\n"
        "## Titre\n"
        "<<<END:fr>>>\n"
    )
    parsed = generate_readme_translations.parse_multilingual_response(raw, ["zh-Hans", "fr"])
    assert parsed == {
        "zh-Hans": "## 标题\n",
        "fr": "## Titre\n",
    }


def test_postprocess_translation_normalizes_simplified_chinese_finance_terms():
    text = (
        "面向浏览器的 user agent\n"
        "基準 worker\n"
        "Pl laza\n"
        "服务提供 供应商\n"
        "财务数据与分析\n"
        "财政摘要\n"
        "投资与财务运营\n"
        "脉冲 (pulses)\n"
        "phemagast\n"
        "attাস\n"
    )
    normalized = generate_readme_translations.postprocess_translation(text, "zh-Hans")
    assert "用户代理" in normalized
    assert "基线 worker" in normalized
    assert "Plaza" in normalized
    assert "服务提供商" in normalized
    assert "金融数据与分析" in normalized
    assert "司库摘要" in normalized
    assert "投资与司库运营" in normalized
    assert "Pulse (pulses)" in normalized
    assert "phemacast" in normalized
    assert "attas" in normalized


def test_postprocess_translation_normalizes_traditional_chinese_finance_terms():
    text = (
        "面向瀏覽器的 user agent\n"
        "基準 worker\n"
        "財務數據與分析\n"
        "投資與財務營運\n"
        "LL 模組\n"
        "脈衝 (pulses)\n"
    )
    normalized = generate_readme_translations.postprocess_translation(text, "zh-Hant")
    assert "用戶代理" in normalized
    assert "基線 worker" in normalized
    assert "金融數據與分析" in normalized
    assert "投資與司庫營運" in normalized
    assert "LLM" in normalized
    assert "Pulse (pulses)" in normalized


def test_postprocess_translation_normalizes_japanese_finance_terms_and_paths():
    text = (
        "prompts/README.md\n"
        "公開パルスカタログ\n"
        "パルスキー\n"
        "財務データと分析\n"
        "財務サマリー\n"
        "投資および財務業務\n"
        "投資および財務ワークフロー\n"
        "内部財務Copilot\n"
        "user-agent\n"
    )
    normalized = generate_readme_translations.postprocess_translation(text, "ja")
    assert "prompits/README.md" in normalized
    assert "公開Pulseカタログ" in normalized
    assert "Pulseキー" in normalized
    assert "金融データと分析" in normalized
    assert "トレジャリー概要" in normalized
    assert "投資およびトレジャリー業務" in normalized
    assert "投資およびトレジャリーワークフロー" in normalized
    assert "内部金融Copilot" in normalized
    assert "ユーザーエージェント" in normalized


def test_all_first_party_readmes_have_translation_links_and_companions():
    for rel_path in generate_readme_translations.README_PATHS:
        readme_path = REPO_ROOT / rel_path
        text = readme_path.read_text(encoding="utf-8")
        assert "## Translations" in text, f"Missing translation links in {rel_path}"
        assert "## Multilingual Summary" not in text, f"Old inline summary still present in {rel_path}"
        for code, label in generate_readme_translations.LANGUAGE_OPTIONS:
            if code == "en":
                continue
            companion = REPO_ROOT / generate_readme_translations.translation_filename(rel_path, code)
            assert companion.exists(), f"Missing translation file for {rel_path}: {companion.name}"
            companion_text = companion.read_text(encoding="utf-8")
            assert label in companion_text
            assert "- [English](README.md)" in companion_text
