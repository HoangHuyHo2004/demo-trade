"""Anthropic Claude LLM provider.

Uses the Messages API with tool use. Kept minimal on purpose — the SDK
is a runtime-optional dependency, so this module falls back to a clear
RuntimeError when the ``anthropic`` package is not installed or when the
API key is missing. The mock provider covers demo mode / tests.
"""
from __future__ import annotations

from app.agent.llm_base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMToolCall,
    LLMToolSpec,
)
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    slug = "anthropic"
    # Default to Claude Sonnet 5. Operators can override via env in a
    # follow-up. Sticking to a stable public snapshot for reproducibility.
    model = "claude-sonnet-5"

    def __init__(self) -> None:
        settings = get_settings()
        self._key = settings.anthropic_api_key
        if not self._key:
            raise RuntimeError(
                "AnthropicProvider selected but ANTHROPIC_API_KEY is not set"
            )
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "AnthropicProvider selected but the `anthropic` package is "
                "not installed. Install it with `pip install anthropic` "
                "or set LLM_PROVIDER=mock."
            ) from e

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec],
        max_output_tokens: int,
    ) -> LLMResponse:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._key)

        native_messages = _to_anthropic(messages)
        native_tools = [
            {"name": t.name, "description": t.description,
             "input_schema": t.json_schema}
            for t in tools
        ]
        try:
            resp = await client.messages.create(
                model=self.model,
                system=system,
                messages=native_messages,
                tools=native_tools,
                max_tokens=max_output_tokens,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("anthropic_call_failed", err=str(e))
            return LLMResponse(stop_reason="error", text=str(e))

        tool_calls: list[LLMToolCall] = []
        text_parts: list[str] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "tool_use":
                tool_calls.append(LLMToolCall(
                    id=block.id, name=block.name, args=dict(block.input),
                ))
            elif btype == "text":
                text_parts.append(block.text)

        stop = "tool_use" if tool_calls else "end_turn"
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) if usage else 0
        out_tok = getattr(usage, "output_tokens", 0) if usage else 0
        return LLMResponse(
            stop_reason=stop,
            text="".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=in_tok,
            output_tokens=out_tok,
            raw=resp,
        )

    @staticmethod
    def cost_micro_usd(input_tokens: int, output_tokens: int) -> int:
        # Rough Sonnet 5 pricing (subject to change). Kept intentionally
        # conservative for budget accounting; not a billing source of truth.
        # $3 / MTok input, $15 / MTok output → convert to 1e-6 USD.
        input_cost = int(input_tokens * 3.0 * 1_000_000 / 1_000_000)
        output_cost = int(output_tokens * 15.0 * 1_000_000 / 1_000_000)
        return input_cost + output_cost


def _to_anthropic(messages: list[LLMMessage]) -> list[dict]:
    """Convert internal messages to Anthropic Messages API shape."""
    out: list[dict] = []
    for m in messages:
        if m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            content_blocks: list[dict] = []
            if m.content:
                content_blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc.id, "name": tc.name, "input": tc.args,
                })
            out.append({"role": "assistant", "content": content_blocks})
        elif m.role == "tool":
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": m.tool_call_id or "",
                    "content": m.content,
                }],
            })
    return out
