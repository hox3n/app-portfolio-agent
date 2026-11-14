"""LLM helpers: structured output with validation and retry."""

import logging
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from portfolio_agent.application.observability import log_event
from portfolio_agent.application.ports import ChatMessage, LLMClient, LLMError

logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


def ask_structured(
    llm: LLMClient,
    messages: Sequence[ChatMessage],
    schema: type[ModelT],
    *,
    max_retries: int = 2,
) -> ModelT:

    history = list(messages)
    for attempt in range(1, max_retries + 2):
        response = llm.chat(history, response_schema=schema.model_json_schema())

        try:
            return schema.model_validate_json(response.content)
        except ValidationError as e:
            problems = "; ".join(
                f"{'.'.join(map(str, err['loc'])) or 'json'}: {err['msg']}" for err in e.errors()
            )

            log_event(
                logger,
                "llm_invalid_output",
                level=logging.WARNING,
                schema=schema.__name__,
                attempt=attempt,
                problems=problems,
            )

            history += [
                ChatMessage(role="assistant", content=response.content),
                ChatMessage(
                    role="user",
                    content=f"Your answer was not valid: {problems}. "
                    "Reply with only JSON that matches the schema.",
                ),
            ]

    raise LLMError(f"no valid {schema.__name__} after {max_retries + 1} attempts")
