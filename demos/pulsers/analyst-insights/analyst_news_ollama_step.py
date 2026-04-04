"""
Analyst News Ollama pipeline step for the Analyst Insights area.

The demos tree contains runnable examples that illustrate how higher-level pipelines fit
together.

It mainly publishes constants such as `ANALYST_PROMPT_PACK`, `profile`,
`prompt_profile`, and `prompt_spec` that are consumed elsewhere in the codebase.
"""

ANALYST_PROMPT_PACK = {
    "profile": {
        "analyst": "North Harbor Research",
        "coverage_focus": "AI infrastructure and semiconductors",
        "updated_at": "2026-04-02T09:15:00Z",
        "default_model": "qwen3:8b",
    },
    "desk_brief": {
        "audience": "internal portfolio manager",
        "objective": "turn raw company news into a concise desk brief with a stance, one tight summary, and bullet-ready support",
        "style": "direct, high-signal, and evidence-based",
        "schema": {
            "stance": "outperform|market perform|underperform|monitor",
            "confidence_label": "low|medium|high",
            "desk_note": "single paragraph",
            "key_points": ["string"],
            "citations": ["exact article headline"],
        },
    },
    "monitoring_points": {
        "audience": "risk and monitoring desk",
        "objective": "extract what changed, what to monitor next, and where the setup could disappoint",
        "style": "skeptical, operational, and alert-oriented",
        "schema": {
            "changed_view": "short sentence",
            "monitor_now": ["string"],
            "risk_flags": ["string"],
            "citations": ["exact article headline"],
        },
    },
    "client_note": {
        "audience": "client-facing relationship manager",
        "objective": "rewrite the news into a clean external-facing note that explains what matters without internal jargon",
        "style": "clear, calm, and client-safe",
        "schema": {
            "subject_line": "short email-like subject",
            "client_note": "short paragraph",
            "action_items": ["string"],
            "citations": ["exact article headline"],
        },
    },
}


def _normalize_symbol(value):
    """Internal helper to normalize the symbol."""
    return str(value or "").strip().upper()


def _clean_text(value):
    """Internal helper for clean text."""
    return str(value or "").strip()


def _string_list(value):
    """Internal helper for string list."""
    if not isinstance(value, list):
        return []
    items = []
    for entry in value:
        text = _clean_text(entry)
        if text:
            items.append(text)
    return items


def _fallback_citations(news_packet):
    """Internal helper for fallback citations."""
    articles = news_packet.get("articles") or []
    citations = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        headline = _clean_text(article.get("headline"))
        if headline:
            citations.append(headline)
    return citations


def _strip_json_fences(raw_text):
    """Internal helper to strip the JSON fences."""
    text = _clean_text(raw_text)
    if not text.startswith("```"):
        return text
    parts = text.split("```")
    for part in parts:
        candidate = _clean_text(part)
        if "{" not in candidate:
            continue
        if candidate.startswith("json"):
            candidate = _clean_text(candidate[4:])
        return candidate
    return text


profile = ANALYST_PROMPT_PACK["profile"]
prompt_profile = _clean_text(pulse.get("prompt_profile") or pulse.get("insight_view"))
prompt_spec = ANALYST_PROMPT_PACK.get(prompt_profile)

if not isinstance(prompt_spec, dict):
    result = {"error": f"Unsupported prompt_profile '{prompt_profile}'."}
elif step_name == "build_prompt":
    news_packet = steps.get("fetch_news") or {}
    articles = news_packet.get("articles") or []
    symbol = _normalize_symbol(news_packet.get("symbol") or input_data.get("symbol"))
    if not symbol:
        result = {"error": "symbol is required"}
    elif not articles:
        result = {"error": "No articles were returned from the upstream news agent."}
    else:
        article_lines = []
        for index, article in enumerate(articles, start=1):
            if not isinstance(article, dict):
                continue
            article_lines.append(
                f"{index}. Headline: {_clean_text(article.get('headline'))}\n"
                f"   Published: {_clean_text(article.get('published_at'))}\n"
                f"   Publisher: {_clean_text(article.get('publisher'))}\n"
                f"   Sentiment Label: {_clean_text(article.get('sentiment_label'))}\n"
                f"   Summary: {_clean_text(article.get('summary'))}"
            )
        prompt = (
            f"You are {profile['analyst']}, covering {profile['coverage_focus']}.\n"
            "Use the analyst-owned prompt profile below and return JSON only.\n"
            "Do not wrap the answer in markdown. Do not invent facts beyond the supplied news packet.\n\n"
            f"Prompt Profile: {prompt_profile}\n"
            f"Audience: {prompt_spec['audience']}\n"
            f"Objective: {prompt_spec['objective']}\n"
            f"Writing Style: {prompt_spec['style']}\n"
            f"Required JSON Shape:\n{json.dumps(prompt_spec['schema'], indent=2)}\n\n"
            f"Symbol: {symbol}\n"
            f"Article Count: {len(articles)}\n\n"
            "Articles:\n"
            + "\n".join(article_lines)
        )
        result = {
            "symbol": symbol,
            "prompt_profile": prompt_profile,
            "prompt": prompt,
            "model": _clean_text(input_data.get("model")) or profile["default_model"],
            "source_articles": len(articles),
        }
elif step_name == "normalize_output":
    news_packet = steps.get("fetch_news") or {}
    llm_packet = steps.get("llm_analysis") or {}
    raw_text = _strip_json_fences(llm_packet.get("response"))
    if not raw_text:
        result = {"error": "The Ollama response was empty."}
    else:
        try:
            payload = json.loads(raw_text)
        except Exception as exc:
            result = {
                "error": f"Unable to parse JSON from the Ollama response: {exc}",
                "raw_response": raw_text,
            }
        else:
            base = {
                "symbol": _normalize_symbol(payload.get("symbol") or news_packet.get("symbol") or input_data.get("symbol")),
                "analyst": profile["analyst"],
                "prompt_profile": prompt_profile,
                "provider": _clean_text(llm_packet.get("provider")),
                "model": _clean_text(llm_packet.get("model")),
                "source": _clean_text(news_packet.get("source") or "unknown"),
                "source_articles": int(news_packet.get("number_of_articles") or len(news_packet.get("articles") or [])),
                "updated_at": profile["updated_at"],
            }
            citations = _string_list(payload.get("citations")) or _fallback_citations(news_packet)
            if prompt_profile == "desk_brief":
                result = {
                    **base,
                    "stance": _clean_text(payload.get("stance")) or "monitor",
                    "confidence_label": _clean_text(payload.get("confidence_label")) or "medium",
                    "desk_note": _clean_text(payload.get("desk_note")),
                    "key_points": _string_list(payload.get("key_points")),
                    "citations": citations,
                }
            elif prompt_profile == "monitoring_points":
                result = {
                    **base,
                    "changed_view": _clean_text(payload.get("changed_view")),
                    "monitor_now": _string_list(payload.get("monitor_now")),
                    "risk_flags": _string_list(payload.get("risk_flags")),
                    "citations": citations,
                }
            else:
                result = {
                    **base,
                    "subject_line": _clean_text(payload.get("subject_line")),
                    "client_note": _clean_text(payload.get("client_note")),
                    "action_items": _string_list(payload.get("action_items")),
                    "citations": citations,
                }
else:
    result = {"error": f"Unsupported step_name '{step_name}'."}
