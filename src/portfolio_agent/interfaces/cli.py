"""Command-line interface: one-shot requests or an interactive chat session."""

import argparse
import sys
import uuid

from portfolio_agent import __version__
from portfolio_agent.application.ports import RepositoryError
from portfolio_agent.application.schemas import AgentResult
from portfolio_agent.application.service import AgentService
from portfolio_agent.bootstrap import build_service
from portfolio_agent.config import get_settings
from portfolio_agent.infrastructure.observability.logging import configure_logging
from portfolio_agent.interfaces.formatting import render_text

EXIT_WORDS = {"exit", "quit", ":q"}


def _print(result: AgentResult, as_json: bool, max_rows: int) -> None:
    print(result.model_dump_json(indent=2) if as_json else render_text(result, max_rows))


def _chat(service: AgentService, as_json: bool, max_rows: int) -> int:
    session_id = uuid.uuid4().hex[:12]
    print(f"portfolio-agent {__version__}. Ask about the app portfolio; type 'exit' to quit.")
    while True:
        try:
            request = input("\nyou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if request.lower() in EXIT_WORDS:
            return 0
        if request:
            print()
            _print(service.run(request, session_id), as_json, max_rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="portfolio-agent", description="Ask the app portfolio analytics agent."
    )
    parser.add_argument("request", nargs="*", help="the request; omit to start a chat session")
    parser.add_argument("--json", action="store_true", help="print the full AgentResult as JSON")
    parser.add_argument("--session", help="session id, to continue an earlier conversation")
    parser.add_argument("--verbose", action="store_true", help="print step and tool logs")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(
        settings.log_level if args.verbose else "ERROR",
        "text" if args.verbose else settings.log_format,
        max_value_chars=settings.log_max_value_chars,
    )
    try:
        service = build_service(settings)
    except RepositoryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not args.request:
        return _chat(service, args.json, settings.display_max_rows)
    result = service.run(" ".join(args.request), args.session)
    _print(result, args.json, settings.display_max_rows)
    return 1 if result.status == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
