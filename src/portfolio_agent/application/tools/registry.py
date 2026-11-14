"""Tool registration and contract wrapper: validate input, run, validate output, log."""

import json
import logging
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from langsmith import traceable
from pydantic import BaseModel, ValidationError

from portfolio_agent.application.observability import log_event
from portfolio_agent.application.schemas import ToolError

logger = logging.getLogger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)
ToolArgs = Mapping[str, Any] | BaseModel | None


class ToolExecutionError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.error = ToolError(code=code, message=message, details=details or {})


@dataclass(frozen=True)
class Tool(Generic[InputT, OutputT]):
    name: str
    description: str
    input_model: type[InputT]
    output_model: type[OutputT]
    func: Callable[[InputT], OutputT]
    llm_exposed: bool = False


@dataclass(frozen=True)
class ToolResult:
    tool: str
    output: BaseModel | None
    error: ToolError | None
    duration_ms: float

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_llm_content(self) -> str:

        if self.error is not None:
            return json.dumps({"error": self.error.model_dump()}, default=str)
        return self.output.model_dump_json() if self.output is not None else "{}"


class ToolCallError(Exception):
    def __init__(self, result: ToolResult) -> None:
        message = result.error.message if result.error else "unknown error"
        super().__init__(f"{result.tool} failed: {message}")
        self.result = result


def _as_dict(args: ToolArgs) -> dict[str, Any]:

    if isinstance(args, BaseModel):
        return args.model_dump()
    return dict(args or {})


def _validation_details(error: ValidationError) -> dict[str, Any]:

    return {
        "errors": [
            {"field": ".".join(str(p) for p in e["loc"]) or "(input)", "message": e["msg"]}
            for e in error.errors()
        ]
    }


def _trace_tool_outputs(outputs: Any) -> dict[str, Any]:
    if not (isinstance(outputs, tuple) and len(outputs) == 2):
        return {"output": outputs}
    output, error = outputs
    return {
        "output": output.model_dump(mode="json") if isinstance(output, BaseModel) else None,
        "error": error.model_dump() if isinstance(error, ToolError) else None,
    }


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool[Any, Any]]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def llm_tool_specs(self) -> list[dict[str, Any]]:

        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_model.model_json_schema(),
                },
            }
            for tool in self._tools.values()
            if tool.llm_exposed
        ]

    def call(self, name: str, args: ToolArgs = None, *, llm_only: bool = False) -> ToolResult:

        started = time.perf_counter()
        raw_args = _as_dict(args)
        output, error = self._traced_execute(
            name, raw_args, llm_only, langsmith_extra={"name": f"tool:{name}"}
        )
        result = ToolResult(
            tool=name,
            output=output,
            error=error,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )

        log_event(
            logger,
            "tool_call",
            level=logging.INFO if result.ok else logging.WARNING,
            tool=name,
            ok=result.ok,
            duration_ms=result.duration_ms,
            args=json.dumps(raw_args, default=str),
            error_code=error.code if error else None,
            error_message=error.message if error else None,
            output_chars=len(output.model_dump_json()) if output else 0,
        )

        return result

    def call_typed(self, name: str, args: ToolArgs, output_type: type[OutputT]) -> OutputT:

        result = self.call(name, args)
        if not result.ok:
            raise ToolCallError(result)

        if not isinstance(result.output, output_type):
            raise TypeError(f"{name} returned {type(result.output).__name__}")

        return result.output

    @traceable(
        run_type="tool",
        name="tool",
        process_inputs=lambda inputs: {
            "tool": inputs.get("name"),
            "args": inputs.get("raw_args"),
            "llm_only": inputs.get("llm_only"),
        },
        process_outputs=lambda outputs: _trace_tool_outputs(outputs),
    )
    def _traced_execute(
        self, name: str, raw_args: dict[str, Any], llm_only: bool
    ) -> tuple[BaseModel | None, ToolError | None]:
        return self._execute(name, raw_args, llm_only)

    def _execute(
        self, name: str, raw_args: dict[str, Any], llm_only: bool
    ) -> tuple[BaseModel | None, ToolError | None]:

        tool = self._tools.get(name)
        if tool is None or (llm_only and not tool.llm_exposed):
            allowed = [t.name for t in self._tools.values() if t.llm_exposed or not llm_only]
            return None, ToolError(
                code="unknown_tool",
                message=f"unknown tool '{name}'",
                details={"allowed": sorted(allowed)},
            )

        try:
            validated_input = tool.input_model.model_validate(raw_args)
        except ValidationError as e:
            return None, ToolError(
                code="invalid_input",
                message=f"invalid arguments for {name}",
                details=_validation_details(e),
            )

        try:
            output = tool.func(validated_input)
        except ToolExecutionError as e:
            return None, e.error
        except Exception:
            logger.exception("tool_crashed", extra={"fields": {"tool": name}})
            return None, ToolError(code="internal_error", message=f"{name} failed unexpectedly")

        try:
            # Re-validate even typed outputs: model_construct() or mutation can bypass validation.
            checked = tool.output_model.model_validate(_as_dict(output))
        except ValidationError as e:
            return None, ToolError(
                code="invalid_output",
                message=f"{name} returned invalid data",
                details=_validation_details(e),
            )

        return checked, None
