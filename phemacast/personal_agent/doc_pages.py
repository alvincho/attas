"""
Document-page extraction helpers for `phemacast.personal_agent.doc_pages`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

Key definitions include `DocPage`, `render_doc_image`, `render_inline`, and
`render_markdown`, which provide the main entry points used by neighboring modules and
tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
import re


BASE_DIR = Path(__file__).resolve().parent
DOC_ASSET_ROUTE_PREFIX = "/docs-static/personal-agent"


@dataclass(frozen=True)
class DocPage:
    """Represent a doc page."""
    slug: str
    title: str
    eyebrow: str
    summary: str
    source_path: Path


DOC_PAGES: dict[str, DocPage] = {
    "user-guide": DocPage(
        slug="user-guide",
        title="Phemacast Personal Agent User Guide",
        eyebrow="Guide",
        summary="Run the app, work with workspaces and panes, save results, and use the integrated MapPhemar editor.",
        source_path=BASE_DIR / "docs" / "user_guide.md",
    ),
    "current-features": DocPage(
        slug="current-features",
        title="Phemacast Personal Agent Current Features",
        eyebrow="Inventory",
        summary="A detailed feature inventory for the current Personal Agent and legacy prototype behavior surface.",
        source_path=BASE_DIR / "docs" / "current_features.md",
    ),
    "readme": DocPage(
        slug="readme",
        title="Phemacast Personal Agent README",
        eyebrow="Package",
        summary="Overview, package layout, and local development notes for the Personal Agent package.",
        source_path=BASE_DIR / "README.md",
    ),
}

_INLINE_LINKS = {
    "../README.md": "/docs/personal-agent/readme",
    "./README.md": "/docs/personal-agent/readme",
    "README.md": "/docs/personal-agent/readme",
    "./current_features.md": "/docs/personal-agent/current-features",
    "current_features.md": "/docs/personal-agent/current-features",
    "./docs/current_features.md": "/docs/personal-agent/current-features",
    "./user_guide.md": "/docs/personal-agent/user-guide",
    "user_guide.md": "/docs/personal-agent/user-guide",
    "./docs/user_guide.md": "/docs/personal-agent/user-guide",
}
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED_LIST_RE = re.compile(r"^\d+\.\s+(.*)$")
_UNORDERED_LIST_RE = re.compile(r"^-\s+(.*)$")
_FENCE_RE = re.compile(r"^```([\w+-]+)?\s*$")
_CODE_SPAN_RE = re.compile(r"(`[^`]+`)")
_INLINE_RICH_TEXT_RE = re.compile(r"!\[([^\]]*)\]\((.+?)\)|\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*")
_MARKDOWN_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\((.+)\)$")
_MARKDOWN_IMAGE_TARGET_RE = re.compile(r'^(?P<src><[^>]+>|.*?)(?:\s+"(?P<title>[^"]*)")?\s*$')
_SCREENSHOT_INSET_RE = re.compile(r"^\[\[screenshot-inset:\s*(.*?)(?:\s*\|\s*(.*?))?\s*\]\]$")


def get_doc_page(slug: str) -> DocPage:
    """Return the doc page."""
    page = DOC_PAGES.get(str(slug or "").strip().lower())
    if page is None:
        raise KeyError(f"Unknown doc page '{slug}'.")
    return page


def load_doc_page(slug: str) -> dict[str, str]:
    """Load the doc page."""
    page = get_doc_page(slug)
    markdown = page.source_path.read_text(encoding="utf-8")
    return {
        "slug": page.slug,
        "title": page.title,
        "eyebrow": page.eyebrow,
        "summary": page.summary,
        "content_html": render_markdown(markdown, source_path=page.source_path),
    }


def rewrite_doc_href(href: str, source_path: Path | None = None) -> str:
    """Handle rewrite doc href."""
    normalized = str(href or "").strip()
    if not normalized:
        return ""
    inline_href = _INLINE_LINKS.get(normalized)
    if inline_href:
        return inline_href
    if normalized.startswith(("/", "#", "http://", "https://", "data:")):
        return normalized
    if source_path is None:
        return normalized
    candidate = (source_path.parent / normalized).resolve(strict=False)
    docs_root = (BASE_DIR / "docs").resolve()
    static_root = (BASE_DIR / "static").resolve()
    if candidate.is_relative_to(docs_root):
        return f"{DOC_ASSET_ROUTE_PREFIX}/{candidate.relative_to(docs_root).as_posix()}"
    if candidate.is_relative_to(static_root):
        return f"/static/{candidate.relative_to(static_root).as_posix()}"
    return normalized


def parse_markdown_image(text: str) -> tuple[str, str, str] | None:
    """Parse the markdown image."""
    match = _MARKDOWN_IMAGE_RE.match(str(text or "").strip())
    if not match:
        return None
    alt_text = str(match.group(1) or "").strip()
    target = str(match.group(2) or "").strip()
    target_match = _MARKDOWN_IMAGE_TARGET_RE.match(target)
    if not target_match:
        return None
    image_src = str(target_match.group("src") or "").strip()
    if image_src.startswith("<") and image_src.endswith(">"):
        image_src = image_src[1:-1].strip()
    if not image_src:
        return None
    image_title = str(target_match.group("title") or "").strip()
    return alt_text, image_src, image_title


def render_doc_image(alt_text: str, image_src: str, title: str = "", source_path: Path | None = None, *, block: bool = False) -> str:
    """Render the doc image."""
    src = escape(rewrite_doc_href(image_src, source_path), quote=True)
    alt = escape(str(alt_text or "").strip(), quote=True)
    caption = escape(str(title or alt_text or "").strip())
    image_tag = f'<img class="doc-image-asset" src="{src}" alt="{alt}" loading="lazy" decoding="async">'
    if not block:
        return image_tag
    caption_html = f"<figcaption>{caption}</figcaption>" if caption else ""
    return f'<figure class="doc-image">{image_tag}{caption_html}</figure>'


def _render_rich_text(text: str, source_path: Path | None = None) -> str:
    """Internal helper to render the rich text."""
    rendered: list[str] = []
    index = 0
    for match in _INLINE_RICH_TEXT_RE.finditer(text):
        rendered.append(escape(text[index:match.start()]))
        if match.group(1) is not None:
            parsed_image = parse_markdown_image(match.group(0))
            if parsed_image is None:
                rendered.append(escape(match.group(0)))
            else:
                alt_text, image_src, title = parsed_image
                rendered.append(render_doc_image(alt_text, image_src, title, source_path, block=False))
        elif match.group(3) is not None:
            label = escape(match.group(3))
            href = escape(rewrite_doc_href(match.group(4), source_path), quote=True)
            rendered.append(f'<a href="{href}">{label}</a>')
        else:
            rendered.append(f"<strong>{escape(match.group(5) or '')}</strong>")
        index = match.end()
    rendered.append(escape(text[index:]))
    return "".join(rendered)


def render_inline(text: str, source_path: Path | None = None) -> str:
    """Render the inline."""
    parts: list[str] = []
    for segment in _CODE_SPAN_RE.split(text):
        if not segment:
            continue
        if segment.startswith("`") and segment.endswith("`"):
            parts.append(f"<code>{escape(segment[1:-1])}</code>")
            continue
        parts.append(_render_rich_text(segment, source_path))
    return "".join(parts)


def render_markdown(markdown: str, source_path: Path | None = None) -> str:
    """Render the markdown."""
    html_parts: list[str] = []
    paragraph_lines: list[str] = []
    list_mode: str | None = None
    code_lines: list[str] = []
    code_lang = ""
    in_code_block = False

    def flush_paragraph() -> None:
        """Handle flush paragraph."""
        if not paragraph_lines:
            return
        text = " ".join(line.strip() for line in paragraph_lines if line.strip())
        if text:
            html_parts.append(f"<p>{render_inline(text, source_path)}</p>")
        paragraph_lines.clear()

    def close_list() -> None:
        """Handle close list."""
        nonlocal list_mode
        if list_mode is None:
            return
        html_parts.append(f"</{list_mode}>")
        list_mode = None

    def flush_code_block() -> None:
        """Handle flush code block."""
        nonlocal code_lang
        if not code_lines:
            code_lang = ""
            return
        language_attr = f' class="language-{escape(code_lang)}"' if code_lang else ""
        code = escape("\n".join(code_lines))
        html_parts.append(f"<pre><code{language_attr}>{code}</code></pre>")
        code_lines.clear()
        code_lang = ""

    def render_screenshot_inset(title: str, caption: str = "") -> str:
        """Render the screenshot inset."""
        title_html = escape(str(title or "").strip() or "Screenshot Inlet")
        caption_text = str(caption or "").strip() or "Drop a product screenshot here when you are ready to replace the placeholder."
        caption_html = escape(caption_text)
        return (
            '<figure class="doc-screenshot-inset">'
            '<div class="doc-screenshot-frame">'
            '<div class="doc-screenshot-toolbar">'
            '<span class="doc-screenshot-dot"></span>'
            '<span class="doc-screenshot-dot"></span>'
            '<span class="doc-screenshot-dot"></span>'
            '</div>'
            '<div class="doc-screenshot-body">'
            '<div class="doc-screenshot-kicker">Screenshot Inlet</div>'
            f'<strong>{title_html}</strong>'
            f'<figcaption>{caption_html}</figcaption>'
            '</div>'
            '</div>'
            '</figure>'
        )

    for raw_line in markdown.splitlines():
        if in_code_block:
            if _FENCE_RE.match(raw_line):
                flush_code_block()
                in_code_block = False
            else:
                code_lines.append(raw_line)
            continue

        fence_match = _FENCE_RE.match(raw_line)
        if fence_match:
            flush_paragraph()
            close_list()
            in_code_block = True
            code_lang = str(fence_match.group(1) or "").strip()
            continue

        stripped = raw_line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            continue

        screenshot_match = _SCREENSHOT_INSET_RE.match(stripped)
        if screenshot_match:
            flush_paragraph()
            close_list()
            html_parts.append(render_screenshot_inset(screenshot_match.group(1), screenshot_match.group(2) or ""))
            continue

        image_match = parse_markdown_image(stripped)
        if image_match:
            flush_paragraph()
            close_list()
            alt_text, image_src, title = image_match
            html_parts.append(render_doc_image(alt_text, image_src, title, source_path, block=True))
            continue

        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            flush_paragraph()
            close_list()
            level = len(heading_match.group(1))
            html_parts.append(f"<h{level}>{render_inline(heading_match.group(2).strip(), source_path)}</h{level}>")
            continue

        unordered_match = _UNORDERED_LIST_RE.match(stripped)
        if unordered_match:
            flush_paragraph()
            if list_mode != "ul":
                close_list()
                list_mode = "ul"
                html_parts.append("<ul>")
            html_parts.append(f"<li>{render_inline(unordered_match.group(1).strip(), source_path)}</li>")
            continue

        ordered_match = _ORDERED_LIST_RE.match(stripped)
        if ordered_match:
            flush_paragraph()
            if list_mode != "ol":
                close_list()
                list_mode = "ol"
                html_parts.append("<ol>")
            html_parts.append(f"<li>{render_inline(ordered_match.group(1).strip(), source_path)}</li>")
            continue

        close_list()
        paragraph_lines.append(stripped)

    flush_paragraph()
    close_list()
    if in_code_block:
        flush_code_block()

    return "\n".join(html_parts)
