"""Deterministic mock LLM.

Runs a fixed script:

  1. If a specific asset was mentioned, resolve it (or accept a pre-resolved id).
  2. Fetch quote + calculated signal for the resolved asset.
  3. Emit a structured final response summarizing what the tools returned.

The script is entirely rule-driven, so:
  * Tests can assert exact behavior.
  * Demo mode works with zero credentials.
  * Any prompt-injection payload embedded in a tool result is IGNORED —
    the mock never reads free-text instructions.

The mock is not a substitute for real reasoning. It is here so the tool
plumbing is exercised end-to-end and the UI has real content to render.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field

from app.agent.llm_base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMToolCall,
    LLMToolSpec,
)

_TICKER_RE = re.compile(r"\b[A-Z]{1,6}(?:[-.][A-Z0-9]{1,5})?\b")


@dataclass
class MockState:
    resolved_asset_id: str | None = None
    saw_quote: bool = False
    saw_signal: bool = False
    tried_symbols: set[str] = field(default_factory=set)
    give_up: bool = False


class MockLLMProvider(LLMProvider):
    slug = "mock"
    model = "mock-agent-v1"

    def __init__(self) -> None:
        self._states: dict[int, MockState] = {}

    async def complete(
        self,
        *,
        system: str,
        messages: list[LLMMessage],
        tools: list[LLMToolSpec],
        max_output_tokens: int,
    ) -> LLMResponse:
        # Use the length of the conversation as a step counter — for a
        # given turn we go: user → tool call → tool result → tool call →
        # tool result → final answer.
        step_key = id(messages)
        st = self._states.setdefault(step_key, MockState())
        st = self._update_state_from_history(st, messages)

        user_text = _first_user_text(messages)
        pre_id = _preresolved_asset_id(user_text)

        # Step 1 — resolve if we don't already have an id.
        if st.resolved_asset_id is None and pre_id is None:
            if st.give_up:
                return _final(_abstain_no_asset(), output_tokens=64)
            symbol = _next_untried_symbol(user_text, st.tried_symbols)
            if symbol:
                st.tried_symbols.add(symbol)
                return _tool_response(
                    "resolve_asset",
                    {"query": symbol},
                    output_tokens=32,
                )
            # Exhausted candidates — mark give_up so we can't loop again.
            st.give_up = True
            return _final(_abstain_no_asset(), output_tokens=64)

        target_id = st.resolved_asset_id or pre_id
        assert target_id is not None

        # Step 2 — quote
        if not st.saw_quote:
            return _tool_response(
                "get_quote", {"asset_canonical_id": target_id},
                output_tokens=32,
            )
        # Step 3 — signal
        if not st.saw_signal:
            return _tool_response(
                "calculate_signal",
                {"asset_canonical_id": target_id, "horizon": "5D",
                 "model": "ensemble-v1"},
                output_tokens=32,
            )

        # Step 4 — synthesize the final structured response from the tool
        # outputs we already saw. We do NOT free-text on top of it.
        quote_result = _last_tool_result(messages, "get_quote") or {}
        signal_result = _last_tool_result(messages, "calculate_signal") or {}
        response_json = _synthesize_response(target_id, quote_result, signal_result)
        return _final(json.dumps(response_json), output_tokens=256)

    @staticmethod
    def _update_state_from_history(st: MockState, messages: list[LLMMessage]) -> MockState:
        for m in messages:
            if m.role != "tool":
                continue
            if m.tool_name == "resolve_asset" and m.tool_result:
                matches = m.tool_result.get("matches") or []
                if len(matches) == 1:
                    st.resolved_asset_id = matches[0].get("canonical_id")
                elif len(matches) > 1:
                    # Ambiguous — pick the first US result first, then VN,
                    # then anything. Deterministic tie-break.
                    ranked = sorted(matches, key=lambda x: (
                        {"US": 0, "VN": 1}.get(x.get("market", ""), 2),
                        x.get("canonical_id", ""),
                    ))
                    st.resolved_asset_id = ranked[0].get("canonical_id")
            elif m.tool_name == "get_quote" and m.tool_result:
                st.saw_quote = True
            elif m.tool_name == "calculate_signal" and m.tool_result:
                st.saw_signal = True
        return st


def _tool_response(name: str, args: dict, *, output_tokens: int = 0) -> LLMResponse:
    return LLMResponse(
        stop_reason="tool_use",
        tool_calls=[LLMToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, args=args)],
        input_tokens=0,
        output_tokens=output_tokens,
    )


def _final(json_text: str, *, output_tokens: int) -> LLMResponse:
    return LLMResponse(
        stop_reason="end_turn",
        text=json_text,
        input_tokens=0,
        output_tokens=output_tokens,
    )


def _first_user_text(messages: list[LLMMessage]) -> str:
    for m in messages:
        if m.role == "user":
            return m.content
    return ""


def _preresolved_asset_id(text: str) -> str | None:
    # Accept a fully qualified canonical id if the user pasted one.
    m = re.search(
        r"\b(?:EQUITY|ETF|INDEX):(?:US|VN):[A-Z]+:[A-Z0-9.-]+\b|"
        r"\bCRYPTO:(?:COINBASE|KRAKEN|BINANCE):[A-Z0-9-]+\b",
        text or "",
    )
    return m.group(0) if m else None


_STOP_WORDS = {
    "I", "A", "AN", "THE", "AND", "OR", "IS", "AM", "PM", "TO", "OF",
    "FOR", "ON", "IN", "BY", "AT", "IT", "WHAT", "WHY", "HOW",
    "PLEASE", "RESEARCH", "ME", "GIVE", "TELL", "SHOW", "FIND", "ABOUT",
    "HELP", "MY", "YOU", "US", "GET", "CAN", "COULD", "WOULD",
}


def _candidate_symbols(text: str) -> list[str]:
    """Return all ticker-like tokens in order of appearance, once each."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _TICKER_RE.finditer((text or "").upper()):
        tok = m.group(0)
        if tok in _STOP_WORDS or tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
    return out


def _next_untried_symbol(text: str, tried: set[str]) -> str | None:
    for tok in _candidate_symbols(text):
        if tok not in tried:
            return tok
    return None


def _last_tool_result(messages: list[LLMMessage], name: str) -> dict | None:
    latest: dict | None = None
    for m in messages:
        if m.role == "tool" and m.tool_name == name and m.tool_result is not None:
            latest = m.tool_result
    return latest


def _abstain_no_asset() -> str:
    return json.dumps({
        "asset_canonical_id": None,
        "executive_summary": (
            "I couldn't identify a specific asset in your question. Please "
            "specify a ticker (e.g. AAPL, VNM, BTC-USD) or a canonical id."
        ),
        "abstained": True,
        "abstention_reason": "No asset identifier detected in the prompt.",
        "citations": [{
            "title": "DEMO-TRADE agent",
            "publisher": "system",
            "kind": "system",
        }],
    })


def _synthesize_response(asset_id: str, quote: dict, signal: dict) -> dict:
    price = quote.get("price")
    currency = quote.get("currency", "")
    event_time = quote.get("event_time", "")
    source = quote.get("source", "")
    market_state = quote.get("market_state", "UNKNOWN")

    classification = signal.get("classification", "INSUFFICIENT_DATA")
    score = signal.get("score", 0)
    confidence = signal.get("confidence", 0)
    risk = signal.get("risk", "MODERATE")
    horizon = signal.get("horizon", "5D")
    strategy_version = signal.get("strategy_version", "ensemble-v1")
    data_version = signal.get("data_version", "unknown")
    pos = signal.get("positive_factors", [])
    neg = signal.get("negative_factors", [])
    warnings = signal.get("liquidity_warnings", [])
    contradictions = signal.get("contradictions", [])
    quality = signal.get("data_quality_score", 0)

    verified = [
        f"Last {source} quote for {asset_id}: {price} {currency} at {event_time} "
        f"(market {market_state})." if price else
        f"No quote available for {asset_id}."
    ]
    signal_summary = (
        f"Signal engine ({strategy_version}, data {data_version}) returned "
        f"{classification} on the {horizon} horizon with score {score} "
        f"and confidence {confidence}. Risk class: {risk}. "
        f"Data quality: {quality}."
    )
    if classification == "INSUFFICIENT_DATA":
        signal_summary = (
            f"Signal engine ({strategy_version}) returned INSUFFICIENT_DATA "
            f"for {asset_id} at horizon {horizon}. Do not act on this signal."
        )

    bull = [
        f"{f.get('label','')} ({f.get('contribution',0):+.2f}) — {f.get('detail','')}"
        for f in pos[:3]
    ]
    bear = [
        f"{f.get('label','')} ({f.get('contribution',0):+.2f}) — {f.get('detail','')}"
        for f in neg[:3]
    ]

    citations = [
        {
            "title": f"Quantitative quote via {source}",
            "publisher": "DEMO-TRADE data provider registry",
            "kind": "quantitative",
            "asset_canonical_id": asset_id,
        },
        {
            "title": f"Signal payload {strategy_version} (data {data_version})",
            "publisher": "DEMO-TRADE signal engine",
            "kind": "quantitative",
            "asset_canonical_id": asset_id,
        },
    ]

    return {
        "asset_canonical_id": asset_id,
        "executive_summary": (
            f"Model output only — not investment advice. {asset_id}: "
            f"{classification} (score {score}, confidence {confidence}, "
            f"risk {risk}, horizon {horizon})."
        ),
        "current_trend": (
            f"Trend regime: {signal.get('regime', 'UNKNOWN')}."
        ),
        "signal_summary": signal_summary,
        "bull_case": bull,
        "bear_case": bear,
        "key_risks": warnings,
        "upcoming_catalysts": [
            "Fundamentals + filings ingest not yet available in this environment (Phase 4.1)."
        ],
        "data_quality_warnings": warnings + contradictions,
        "verified_facts": verified,
        "interpretation": [
            "The signal engine's factor contributions are computed by "
            "deterministic indicator functions; the LLM does not synthesize "
            "them.",
        ],
        "assumptions": [
            "Backtest baselines assume the market cost profile in "
            "app/quant/costs.py; adjust for your actual venue.",
        ],
        "unknowns": [
            "Company-specific fundamentals and news are not indexed here "
            "yet; conclusions relying on them cannot be verified.",
        ],
        "suggested_questions": [
            f"Run a walk-forward backtest of {asset_id} at horizon {horizon}?",
            "Compare against a market benchmark?",
        ],
        "citations": citations,
        "abstained": classification == "INSUFFICIENT_DATA",
        "abstention_reason": (
            "Signal engine reported INSUFFICIENT_DATA."
            if classification == "INSUFFICIENT_DATA" else ""
        ),
    }
