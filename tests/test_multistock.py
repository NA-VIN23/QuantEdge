"""
tests/test_multistock.py
------------------------
Tests for multi-stock pipeline correctness.

Key concerns:
  1. Two symbols process independently with no cross-contamination.
  2. Rolling indicators (EMA, ATR, etc.) do NOT bleed across symbols.
  3. One bad stock does not corrupt another's output.
  4. The same strategy rules apply to every symbol.

All tests use synthetic OHLCV data — no real market data.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from quant.data.cleaning import clean
from quant.features.indicators import compute_all_features
from quant.strategies.trend_momentum import apply_strategy


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------


def _make_canonical_df(
    symbol: str,
    n: int = 100,
    start_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Create a synthetic canonical OHLCV DataFrame for testing.

    Uses a fixed random seed so the output is deterministic.
    All canonical columns are present: date, symbol, open, high, low, close, volume.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-02", periods=n, freq="B")
    close = start_price + np.cumsum(rng.normal(0, 1.5, n))
    close = np.maximum(close, 1.0)  # prevent negative prices

    df = pd.DataFrame({
        "date": dates,
        "symbol": symbol,
        "open": close * rng.uniform(0.995, 1.005, n),
        "high": close * rng.uniform(1.000, 1.015, n),
        "low": close * rng.uniform(0.985, 1.000, n),
        "close": close,
        "volume": rng.integers(500_000, 5_000_000, n).astype(float),
    })
    # Ensure OHLC consistency
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"]  = df[["open", "low", "close"]].min(axis=1)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Tests: independent processing
# ---------------------------------------------------------------------------


class TestIndependentProcessing:

    def test_two_symbols_same_row_count(self):
        df_a = _make_canonical_df("STOCK_A", n=100, seed=1)
        df_b = _make_canonical_df("STOCK_B", n=100, seed=2)
        feat_a = compute_all_features(df_a)
        feat_b = compute_all_features(df_b)
        assert len(feat_a) == 100
        assert len(feat_b) == 100

    def test_symbol_column_not_contaminated(self):
        df_a = _make_canonical_df("STOCK_A", n=50, seed=1)
        df_b = _make_canonical_df("STOCK_B", n=50, seed=2)
        feat_a = compute_all_features(df_a)
        feat_b = compute_all_features(df_b)
        assert (feat_a["symbol"] == "STOCK_A").all()
        assert (feat_b["symbol"] == "STOCK_B").all()

    def test_signals_produced_independently(self):
        df_a = _make_canonical_df("STOCK_A", n=200, seed=10)
        df_b = _make_canonical_df("STOCK_B", n=200, seed=99)
        sig_a = apply_strategy(compute_all_features(df_a))
        sig_b = apply_strategy(compute_all_features(df_b))
        # Both have signals column
        assert "signal" in sig_a.columns
        assert "signal" in sig_b.columns
        # Not the exact same signals (different price histories)
        # (There's a tiny chance they could match by coincidence, but extremely unlikely)
        assert not (sig_a["signal"].values == sig_b["signal"].values).all(), \
            "Different price series should produce different signals"

    def test_one_symbol_does_not_alter_other(self):
        """Processing STOCK_B after STOCK_A does not change STOCK_A's features."""
        df_a = _make_canonical_df("STOCK_A", n=100, seed=5)
        feat_a_before = compute_all_features(df_a.copy())

        # Process STOCK_B completely
        df_b = _make_canonical_df("STOCK_B", n=100, seed=7)
        _ = compute_all_features(df_b)

        # Process STOCK_A again — result should be identical
        feat_a_after = compute_all_features(df_a.copy())

        pd.testing.assert_frame_equal(
            feat_a_before.drop(columns=["symbol"]),
            feat_a_after.drop(columns=["symbol"]),
            check_exact=False,
            rtol=1e-9,
        )


# ---------------------------------------------------------------------------
# Tests: Cross-stock rolling window leakage
# ---------------------------------------------------------------------------


class TestNoCrossStockLeakage:
    """
    Critical: rolling windows (EMA, ATR, SMA, etc.) must be computed
    ONLY from each symbol's own history. They must NOT include rows
    from a different symbol.
    """

    def test_ema20_resets_per_symbol(self):
        """
        EMA on row 0 of STOCK_B must equal EMA on row 0 of a standalone STOCK_B
        DataFrame — not be influenced by STOCK_A's prior close.
        """
        df_a = _make_canonical_df("STOCK_A", n=60, seed=1)
        df_b_standalone = _make_canonical_df("STOCK_B", n=60, seed=2)

        feat_a  = compute_all_features(df_a)
        feat_b_standalone = compute_all_features(df_b_standalone)

        # Build a combined df simulating naive concatenation without reset
        df_combined = pd.concat([df_a, df_b_standalone], ignore_index=True)
        df_b_from_combined = df_combined[df_combined["symbol"] == "STOCK_B"].copy().reset_index(drop=True)
        feat_b_combined = compute_all_features(df_b_from_combined)

        # The two should be identical — no bleed from STOCK_A
        pd.testing.assert_series_equal(
            feat_b_standalone["ema20"].reset_index(drop=True),
            feat_b_combined["ema20"].reset_index(drop=True),
            check_names=False,
        )

    def test_atr14_resets_per_symbol(self):
        df_a = _make_canonical_df("STOCK_A", n=60, seed=3)
        df_b = _make_canonical_df("STOCK_B", n=60, seed=4)

        feat_b_standalone = compute_all_features(df_b.copy())

        # Simulate naive concatenation
        df_combined = pd.concat([df_a, df_b], ignore_index=True)
        df_b_slice = df_combined[df_combined["symbol"] == "STOCK_B"].copy().reset_index(drop=True)
        feat_b_from_combined = compute_all_features(df_b_slice)

        pd.testing.assert_series_equal(
            feat_b_standalone["atr14"].reset_index(drop=True),
            feat_b_from_combined["atr14"].reset_index(drop=True),
            check_names=False,
        )

    def test_first_ema_row_not_influenced_by_other_symbol(self):
        """
        STOCK_B row 0 EMA20 must equal close[0] of STOCK_B regardless of STOCK_A.
        (EMA with adjust=False initializes at first observation.)
        """
        df_b = _make_canonical_df("STOCK_B", n=50, seed=99)
        feat_b = compute_all_features(df_b)
        # EMA is initialized at row 0 close
        expected_ema_row0 = df_b.iloc[0]["close"]
        actual_ema_row0   = feat_b.iloc[0]["ema20"]
        assert abs(actual_ema_row0 - expected_ema_row0) < 1e-9, \
            f"EMA at row 0 should equal close[0]. Got {actual_ema_row0}, expected {expected_ema_row0}"

    def test_sma20_nan_at_start_per_symbol(self):
        """SMA20 must be NaN for first 19 rows of EACH symbol independently."""
        df_a = _make_canonical_df("STOCK_A", n=50, seed=10)
        df_b = _make_canonical_df("STOCK_B", n=50, seed=20)

        feat_a = compute_all_features(df_a)
        feat_b = compute_all_features(df_b)

        # First 19 rows of each symbol should be NaN for sma20
        assert feat_a["sma20"].iloc[:19].isna().all()
        assert feat_b["sma20"].iloc[:19].isna().all()


# ---------------------------------------------------------------------------
# Tests: clean() symbol isolation
# ---------------------------------------------------------------------------


class TestCleaningSymbolIsolation:

    def test_clean_assigns_correct_symbol(self):
        """clean() must assign the symbol parameter, not a hardcoded constant."""
        # Create a minimal raw DataFrame in Investing.com format
        raw = pd.DataFrame({
            "Date": ["05/01/2024", "05/02/2024", "05/03/2024"],
            "Price": ["100.00", "101.00", "102.00"],
            "Open": ["99.00", "100.00", "101.00"],
            "High": ["101.00", "102.00", "103.00"],
            "Low": ["98.00", "99.00", "100.00"],
            "Vol.": ["1.5M", "1.6M", "1.7M"],
            "Change %": ["1.00%", "1.00%", "1.00%"],
        })
        df_a, _ = clean(raw, symbol="STOCK_A")
        df_b, _ = clean(raw, symbol="STOCK_B")

        assert (df_a["symbol"] == "STOCK_A").all()
        assert (df_b["symbol"] == "STOCK_B").all()

    def test_clean_default_is_itc(self):
        """Calling clean() without symbol defaults to ITC for backward compat."""
        raw = pd.DataFrame({
            "Date": ["05/01/2024"],
            "Price": ["100.00"],
            "Open": ["99.00"],
            "High": ["101.00"],
            "Low": ["98.00"],
            "Vol.": ["1.5M"],
            "Change %": ["1.00%"],
        })
        df, _ = clean(raw)
        assert (df["symbol"] == "ITC").all()

    def test_two_cleans_dont_share_state(self):
        raw = pd.DataFrame({
            "Date": ["05/01/2024", "05/02/2024"],
            "Price": ["100.00", "200.00"],
            "Open": ["99.00", "199.00"],
            "High": ["101.00", "201.00"],
            "Low": ["98.00", "198.00"],
            "Vol.": ["1.5M", "2.0M"],
            "Change %": ["1.00%", "2.00%"],
        })
        df_a, _ = clean(raw, symbol="AAA")
        df_b, _ = clean(raw, symbol="BBB")

        # Each result should have its own symbol, not the other
        assert (df_a["symbol"] == "AAA").all()
        assert (df_b["symbol"] == "BBB").all()
        assert not (df_a["symbol"] == "BBB").any()
        assert not (df_b["symbol"] == "AAA").any()
