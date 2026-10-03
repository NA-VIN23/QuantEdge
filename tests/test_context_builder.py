import pytest
from quant.api.context_builder import build_research_context
from quant.data.registry import VALID_SYMBOLS

def test_context_builder_invalid_symbol():
    with pytest.raises(ValueError, match="is not recognised"):
        build_research_context("INVALID_SYM")

def test_context_builder_itc():
    # Assuming ITC has data generated
    ctx, sources = build_research_context("ITC")
    assert "RESEARCH CONTEXT FOR ITC" in ctx
    assert len(sources) > 0
    # Should at least find the backtest summary
    assert "ITC backtest summary" in sources
    assert "91464.71" in ctx or "91,464.71" in ctx or "final_equity" in ctx
