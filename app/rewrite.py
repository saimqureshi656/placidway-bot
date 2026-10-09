"""Turn a follow-up into one standalone English query."""

from __future__ import annotations

from app.llm import LLMError, complete_json

SYSTEM = """Rewrite the user's latest message into one standalone English search query.
Use the history. Reply JSON only:
{"standalone_query_en":"", "language":"en", "entities":{"treatment":"", "country":"", "program":""}, "is_followup":false}
Keep the prior treatment when the user only changes country, as in "what about in Turkey?".
"What about recovery time?" after adenocarcinoma becomes a query about recovery time after the adenocarcinoma program at ITC Tijuana.
language is the language of the user's latest message (en, es, ar, or another short code).
"""


def _history_text(history: list[dict]) -> str:
    lines = []
    for turn in history[-6:]:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def rewrite(message: str, history: list[dict] | None = None) -> dict:
    history = history or []
    user = f"History:\n{_history_text(history)}\n\nLatest:\n{message}"
    try:
        parsed = complete_json(SYSTEM, user, reasoning_effort="low", max_tokens=220)
    except (LLMError, ValueError, TypeError):
        parsed = {}
    entities = parsed.get("entities") if isinstance(parsed.get("entities"), dict) else {}
    standalone = str(parsed.get("standalone_query_en") or "").strip() or message
    return {
        "standalone_query_en": standalone,
        "language": str(parsed.get("language") or "en"),
        "entities": {
            "treatment": str(entities.get("treatment") or ""),
            "country": str(entities.get("country") or ""),
            "program": str(entities.get("program") or ""),
        },
        "is_followup": bool(parsed.get("is_followup")),
    }
