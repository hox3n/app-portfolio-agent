"""Versioned prompt templates (the .md files in this folder) and safe embedding of user text."""

from importlib.resources import files
from string import Template

_PACKAGE = "portfolio_agent.application.prompts"


def render(name: str, **values: object) -> str:
    text = (files(_PACKAGE) / f"{name}.md").read_text(encoding="utf-8")
    return Template(text).substitute({key: str(value) for key, value in values.items()})


def neutralize(text: str) -> str:
    return text.replace("<", "\u2039").replace(">", "\u203a")


def user_block(text: str) -> str:
    return f"<user_request>\n{neutralize(text)}\n</user_request>"
