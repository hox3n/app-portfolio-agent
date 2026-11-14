"""Tests for structured LLM output with validation and retry."""

import pytest
from pydantic import BaseModel, Field

from portfolio_agent.application.llm import ask_structured
from portfolio_agent.application.ports import ChatMessage, LLMError, LLMResponse, ToolCall
from portfolio_agent.infrastructure.llm.fake_client import FakeLLMClient


class Answer(BaseModel):
    workflow: str
    confidence: float = Field(ge=0, le=1)


QUESTION = [ChatMessage(role="user", content="Review UA for January")]


def test_valid_answer_on_first_try() -> None:
    llm = FakeLLMClient(['{"workflow": "budget_review", "confidence": 0.9}'])
    assert ask_structured(llm, QUESTION, Answer) == Answer(workflow="budget_review", confidence=0.9)
    assert len(llm.calls) == 1


def test_invalid_answers_retried_with_feedback() -> None:
    llm = FakeLLMClient(
        ["not json", '{"workflow": "qa", "confidence": 2}', Answer(workflow="qa", confidence=0.5)]
    )
    assert ask_structured(llm, QUESTION, Answer).workflow == "qa"
    assert len(llm.calls) == 3
    feedback = llm.calls[2][-1]
    assert feedback.role == "user"
    assert "confidence" in feedback.content


def test_gives_up_after_max_retries() -> None:
    llm = FakeLLMClient(["bad"] * 5)
    with pytest.raises(LLMError, match="Answer"):
        ask_structured(llm, QUESTION, Answer, max_retries=1)
    assert len(llm.calls) == 2


def test_fake_returns_scripted_tool_calls() -> None:
    scripted = LLMResponse(tool_calls=[ToolCall(name="get_schema")])
    assert FakeLLMClient([scripted]).chat(QUESTION) == scripted


def test_fake_fails_when_script_runs_out() -> None:
    with pytest.raises(LLMError):
        FakeLLMClient([]).chat(QUESTION)
