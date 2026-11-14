"""Deterministic input checks that run before the LLM sees a request."""

import re
import unicodedata

from pydantic import BaseModel

INJECTION_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|prompts?|rules?)\b",
        r"\b(reveal|show|print|repeat|output|tell me)\b.{0,30}"
        r"\b(system|hidden|initial|your)\b.{0,20}\b(prompt|instructions?|rules?)\b",
        r"\byou are now\b",
        r"\b(developer|god|jailbreak|dan)\s+mode\b",
        r"</?\s*(system|assistant|user_request|previous_turns|tool|instructions?)\s*>",
        r"\bnew instructions?\s*:",
    )
)

WRITE_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(drop|truncate|alter)\s+table\b",
        r"\binsert\s+into\b",
        r"\bupdate\s+\w+\s+set\b",
        r"\b(delete|drop|wipe|erase|truncate)\b.{0,40}"
        r"\b(table|tables|database|data|dataset|rows?|records?|metrics)\b",
    )
)


class GuardResult(BaseModel):
    ok: bool
    text: str = ""
    code: str | None = None
    message: str | None = None


def _clean(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(
        ch for ch in normalized if ch in "\n\t" or not unicodedata.category(ch).startswith("C")
    ).strip()


def check_input(text: str, max_chars: int) -> GuardResult:
    cleaned = _clean(text)
    if not cleaned:
        return GuardResult(
            ok=False,
            code="empty_input",
            message="Please type a question about the app portfolio.",
        )
    if len(cleaned) > max_chars:
        return GuardResult(
            ok=False,
            code="input_too_long",
            message=f"Please keep requests under {max_chars} characters.",
        )
    if any(p.search(cleaned) for p in INJECTION_PATTERNS):
        return GuardResult(
            ok=False,
            code="prompt_injection",
            message="I can only answer questions about the app portfolio data, "
            "and I can't change or reveal my instructions.",
        )
    if any(p.search(cleaned) for p in WRITE_PATTERNS):
        return GuardResult(
            ok=False,
            code="write_request",
            message="I have read-only access to the metrics and can't change or delete data.",
        )
    return GuardResult(ok=True, text=cleaned)
