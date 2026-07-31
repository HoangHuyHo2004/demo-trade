"""LLM-provider abstraction.

The orchestrator drives a tool-use loop that is provider-agnostic. Each
provider translates the shared ``LLMTurn`` inputs into its native call
and returns a ``LLMResponse`` with either a final answer or the next
batch of tool invocations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant", "tool"]


@dataclass
class LLMToolSpec:
    name: str
    description: str
    json_schema: dict  # JSON-Schema for the tool's arguments


@dataclass
class LLMMessage:
    role: Role
    content: str = ""
    # For tool-result messages
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_result: dict | None = None
    # For assistant messages that requested tools
    tool_calls: list[LLMToolCall] = field(default_factory=list)


@dataclass
class LLMToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMResponse:
    stop_reason: Literal["end_turn", "tool_use", "budget", "error"]
    text: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    raw: Any = None


class LLMProvider(ABC):
    slug: str
    model: str

    @abstractmethod
    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec],
        max_output_tokens: int,
    ) -> LLMResponse:  # pragma: no cover - abstract
        ...

    @staticmethod
    def cost_micro_usd(input_tokens: int, output_tokens: int) -> int:  # pragma: no cover
        return 0
