"""
tests/test_registry.py
-----------------------
Unit tests for quant.data.registry.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from quant.data.registry import (
    SYMBOL_REGISTRY,
    VALID_SYMBOLS,
    SymbolConfig,
    get_raw_path,
    get_processed_path,
    get_features_path,
    get_backtest_dir,
    get_quality_report_paths,
    get_available_symbols,
    get_symbol_config,
)


class TestSymbolRegistry:

    def test_itc_is_in_registry(self):
        assert "ITC" in SYMBOL_REGISTRY

    def test_known_symbols_present(self):
        # These are all defined in Sprint 5 MVP
        for sym in ("ITC", "RELIANCE", "TCS", "INFY", "HDFCBANK"):
            assert sym in SYMBOL_REGISTRY, f"{sym} missing from registry"

    def test_valid_symbols_is_frozenset(self):
        assert isinstance(VALID_SYMBOLS, frozenset)
        assert "ITC" in VALID_SYMBOLS

    def test_symbol_config_fields(self):
        cfg = SYMBOL_REGISTRY["ITC"]
        assert isinstance(cfg, SymbolConfig)
        assert cfg.symbol == "ITC"
        assert cfg.source == "InvestingCom"
        assert len(cfg.description) > 0
        assert len(cfg.raw_file) > 0


class TestPathHelpers:

    def test_get_raw_path_itc(self):
        p = get_raw_path("ITC")
        # ITC uses legacy path
        assert "ITC Stock Price History.csv" in str(p)

    def test_get_processed_path_format(self):
        p = get_processed_path("ITC")
        assert p.suffix == ".csv"
        assert "stocks" in str(p)
        assert "ITC" in str(p)

    def test_get_features_path_format(self):
        p = get_features_path("ITC")
        assert "ITC_features" in str(p)
        assert p.suffix == ".csv"

    def test_get_backtest_dir_format(self):
        d = get_backtest_dir("ITC")
        assert d.name == "ITC"
        assert "backtests" in str(d)

    def test_get_quality_report_paths(self):
        json_p, md_p = get_quality_report_paths("ITC")
        assert json_p.suffix == ".json"
        assert md_p.suffix == ".md"
        assert "ITC" in json_p.name
        assert "ITC" in md_p.name

    def test_unknown_symbol_raises_key_error(self):
        with pytest.raises(KeyError):
            get_raw_path("FAKESYM")

    def test_unknown_symbol_raises_on_features(self):
        with pytest.raises(KeyError):
            get_features_path("FAKESYM")

    def test_unknown_symbol_raises_on_backtest_dir(self):
        with pytest.raises(KeyError):
            get_backtest_dir("FAKESYM")

    def test_get_symbol_config_returns_config(self):
        cfg = get_symbol_config("ITC")
        assert cfg.symbol == "ITC"

    def test_get_symbol_config_unknown_raises(self):
        with pytest.raises(KeyError):
            get_symbol_config("FAKESYM")


class TestGetAvailableSymbols:

    def test_returns_list(self):
        result = get_available_symbols()
        assert isinstance(result, list)

    def test_itc_available_after_pipeline(self):
        """ITC processed file should exist after running the pipeline."""
        p = get_processed_path("ITC")
        if p.exists():
            available = get_available_symbols()
            assert "ITC" in available

    def test_fake_symbol_never_available(self):
        # Even if somehow in registry, FAKESYM file won't exist
        available = get_available_symbols()
        assert "FAKESYM" not in available

    def test_result_is_sorted(self):
        result = get_available_symbols()
        assert result == sorted(result)
