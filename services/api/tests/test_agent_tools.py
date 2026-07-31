"""Tool-layer security + validation tests."""
import pytest
from pydantic import ValidationError

from app.agent.schemas import (
    CalculateSignalArgs,
    GetHistoricalBarsArgs,
    RunBacktestArgs,
)
from app.agent.tools import ALLOWED_TOOLS, ToolExecutor, ToolValidationError
from app.models.asset import Asset


async def _seed_aapl(session) -> Asset:
    a = Asset(
        canonical_id="EQUITY:US:NASDAQ:AAPL",
        asset_type="EQUITY", market="US", exchange_code="NASDAQ",
        symbol="AAPL", display_symbol="AAPL", name="Apple",
        quote_currency="USD", market_timezone="America/New_York",
        calendar="XNYS",
    )
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


def test_unknown_tool_is_rejected_by_schema_registry():
    assert "delete_all_data" not in ALLOWED_TOOLS
    assert "eval" not in ALLOWED_TOOLS
    assert "os_system" not in ALLOWED_TOOLS


def test_schema_forbids_extra_fields():
    with pytest.raises(ValidationError):
        GetHistoricalBarsArgs.model_validate({
            "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
            "shell_cmd": "rm -rf /",   # extra field must be rejected
        })


def test_schema_bounds_lookback_days():
    with pytest.raises(ValidationError):
        GetHistoricalBarsArgs.model_validate({
            "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
            "lookback_days": 999_999,
        })
    with pytest.raises(ValidationError):
        GetHistoricalBarsArgs.model_validate({
            "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
            "lookback_days": 0,
        })


def test_schema_bounds_backtest_thresholds():
    with pytest.raises(ValidationError):
        RunBacktestArgs.model_validate({
            "asset_canonical_id": "X",
            "entry_threshold": 999.0,
        })


def test_calculate_signal_requires_valid_horizon():
    with pytest.raises(ValidationError):
        CalculateSignalArgs.model_validate({
            "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
            "horizon": "7D",
        })


@pytest.mark.asyncio
async def test_executor_rejects_unknown_tool(session):
    e = ToolExecutor(session)
    with pytest.raises(ToolValidationError):
        await e.execute("shell_exec", {})


@pytest.mark.asyncio
async def test_executor_rejects_extra_args(session):
    await _seed_aapl(session)
    e = ToolExecutor(session)
    with pytest.raises(ToolValidationError):
        await e.execute("get_quote", {
            "asset_canonical_id": "EQUITY:US:NASDAQ:AAPL",
            "override_price": 9999,   # extras rejected server-side
        })


@pytest.mark.asyncio
async def test_search_stubs_are_available_but_return_not_available(session):
    e = ToolExecutor(session)
    for name in (
        "search_sec_filings",
        "search_vietnam_disclosures",
        "search_company_announcements",
        "search_crypto_project_announcements",
        "search_approved_news_sources",
    ):
        result, _ = await e.execute(name, {"query": "hello"})
        assert result["status"] == "not_available"
        assert result["matches"] == []


@pytest.mark.asyncio
async def test_quote_tool_returns_provider_source(session):
    asset = await _seed_aapl(session)
    e = ToolExecutor(session)
    result, dur = await e.execute("get_quote", {
        "asset_canonical_id": asset.canonical_id,
    })
    assert result["asset_canonical_id"] == asset.canonical_id
    assert result["source"] == "mock"  # tests force USE_MOCK_PROVIDERS_ONLY
    assert result["currency"] == "USD"
    assert result["market_state"] in {"OPEN", "CLOSED"}
    assert dur >= 0


@pytest.mark.asyncio
async def test_signal_tool_output_shape(session):
    asset = await _seed_aapl(session)
    e = ToolExecutor(session)
    result, _ = await e.execute("calculate_signal", {
        "asset_canonical_id": asset.canonical_id,
        "horizon": "5D",
    })
    for k in ("asset_id", "classification", "score", "confidence", "risk",
              "strategy_version", "data_version"):
        assert k in result
