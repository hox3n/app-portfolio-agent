"""Command-line interface (main entry point)."""

import sys

from portfolio_agent import __version__
from portfolio_agent.config import get_settings


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    print(f"portfolio-agent {__version__}")
    print(
        f"  model:    {settings.ollama_model} "
        f"(provider={settings.llm_provider}, think={settings.ollama_think})"
    )
    print(f"  database: {settings.db_path}")
    print("Agent not implemented yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
