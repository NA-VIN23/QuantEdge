"""
tests/test_indicators.py
------------------------
Unit tests for quant.features.indicators.

All tests use small synthetic DataFrames — no dependency on the ITC dataset.
"""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd
import pytest

from quant.features.indicators import (
    FEATURE_COLUMNS,
    REQUIRED_INPUT_COLUMNS,
    atr_wilder,
    avg_volume,
    compute_all_features,
    ema,
    momentum,
    sma,
    true_range,
    volume_ratio,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_close(values: List[float]) -> pd.Series:
    """Build a close Series with a simple integer index."""
    return pd.Series(values, dtype=float, name="close")


def _make_ohlcv(n: int = 60, seed: int = 42) -> pd.DataFrame:
    """
    Build a minimal synthetic OHLCV DataFrame with n rows.

    Uses a deterministic random walk for close prices so that
    tests are reproducible.
    """
    rng = np.random.default_rng(seed)
    close = 100.0 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0.5, 2.0, n)
    low = close - rng.uniform(0.5, 2.0, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.uniform(1_000_000, 10_000_000, n)

    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="B"),
        "symbol": "TEST",
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def _constant_ohlcv(price: float = 100.0, vol: float = 5_000_000.0, n: int = 60) -> pd.DataFrame:
    """
    OHLCV DataFrame where every close equals *price* and volume equals *vol*.
    Useful for arithmetic verification tests.
    """
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=n, freq="B"),
        "symbol": "TEST",
        "open": price,
        "high": price + 1.0,
        "low": price - 1.0,
        "close": float(price),
        "volume": float(vol),
    })


# ---------------------------------------------------------------------------
# EMA tests
# ---------------------------------------------------------------------------


class TestEMA:

    def test_ema20_length(self):
        """EMA output must have the same length as input."""
        close = _make_close(list(range(1, 31)))
        result = ema(close, span=20)
        assert len(result) == 30

    def test_ema_first_value_equals_first_close(self):
        """
        With adjust=False, the first EMA value must equal the first close.
        This is the initialization convention.
        """
        values = [10.0, 12.0, 15.0, 11.0, 13.0]
        close = _make_close(values)
        result = ema(close, span=3)
        assert result.iloc[0] == pytest.approx(10.0)

    def test_ema_converges_on_constant_series(self):
        """EMA of a constant series must equal that constant."""
        close = _make_close([50.0] * 50)
        result = ema(close, span=20)
        assert result.iloc[-1] == pytest.approx(50.0)

    def test_ema_no_nan_in_output(self):
        """EMA produces no NaN values for any row (by design)."""
        close = _make_close([100.0 + i for i in range(30)])
        result = ema(close, span=20)
        assert result.isna().sum() == 0

    def test_ema50_no_nan(self):
        """EMA50 also produces no NaN."""
        close = _make_close([100.0] * 60)
        result = ema(close, span=50)
        assert result.isna().sum() == 0

    def test_ema_span_1_equals_close(self):
        """EMA with span=1 should equal the close series exactly."""
        values = [10.0, 12.0, 8.0, 15.0]
        close = _make_close(values)
        result = ema(close, span=1)
        for i, v in enumerate(values):
            assert result.iloc[i] == pytest.approx(v)

    def test_ema_invalid_span_raises(self):
        """span < 1 should raise ValueError."""
        close = _make_close([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="span"):
            ema(close, span=0)

    def test_ema20_three_step_manual(self):
        """
        Manual verification of EMA(3) with adjust=False.
        alpha = 2/(3+1) = 0.5
        EMA[0] = 10
        EMA[1] = 0.5*12 + 0.5*10 = 11
        EMA[2] = 0.5*14 + 0.5*11 = 12.5
        """
        close = _make_close([10.0, 12.0, 14.0])
        result = ema(close, span=3)
        assert result.iloc[0] == pytest.approx(10.0)
        assert result.iloc[1] == pytest.approx(11.0)
        assert result.iloc[2] == pytest.approx(12.5)

    def test_ema_index_preserved(self):
        """EMA output index must match input index."""
        idx = pd.date_range("2020-01-01", periods=10)
        close = pd.Series([100.0] * 10, index=idx)
        result = ema(close, span=5)
        assert list(result.index) == list(idx)


# ---------------------------------------------------------------------------
# SMA tests
# ---------------------------------------------------------------------------


class TestSMA:

    def test_sma20_first_19_rows_nan(self):
        """First 19 rows of SMA20 must be NaN (min_periods=20)."""
        close = _make_close([100.0] * 40)
        result = sma(close, window=20)
        assert result.iloc[:19].isna().all()

    def test_sma20_row_19_is_mean_of_first_20(self):
        """Row 19 of SMA20 must equal the mean of the first 20 close values."""
        values = list(range(1, 41))  # 1..40
        close = _make_close(values)
        result = sma(close, window=20)
        expected = sum(range(1, 21)) / 20  # mean of 1..20 = 10.5
        assert result.iloc[19] == pytest.approx(expected)

    def test_sma50_first_49_rows_nan(self):
        """First 49 rows of SMA50 must be NaN."""
        close = _make_close([1.0] * 60)
        result = sma(close, window=50)
        assert result.iloc[:49].isna().all()
        assert not pd.isna(result.iloc[49])

    def test_sma_constant_series(self):
        """SMA of constant series equals that constant from row window-1 onward."""
        close = _make_close([75.0] * 30)
        result = sma(close, window=20)
        valid = result.dropna()
        np.testing.assert_allclose(valid.values, 75.0)

    def test_sma_invalid_window_raises(self):
        with pytest.raises(ValueError):
            sma(_make_close([1.0, 2.0]), window=0)

    def test_sma_length(self):
        close = _make_close([1.0] * 25)
        result = sma(close, window=20)
        assert len(result) == 25


# ---------------------------------------------------------------------------
# True Range tests
# ---------------------------------------------------------------------------


class TestTrueRange:

    def test_true_range_length(self):
        df = _make_ohlcv(20)
        tr = true_range(df["high"], df["low"], df["close"])
        assert len(tr) == 20

    def test_first_bar_equals_high_minus_low(self):
        """Row 0 TR must equal high[0] - low[0] (no previous close)."""
        df = _constant_ohlcv(price=100.0)
        # high = 101, low = 99 → TR[0] = 2.0
        tr = true_range(df["high"], df["low"], df["close"])
        assert tr.iloc[0] == pytest.approx(2.0)

    def test_no_nan_after_row_0(self):
        """After row 0, TR should have no NaN (prev_close is available)."""
        df = _make_ohlcv(20)
        tr = true_range(df["high"], df["low"], df["close"])
        assert tr.isna().sum() == 0

    def test_tr_is_always_nonnegative(self):
        """True Range must be >= 0 for all bars."""
        df = _make_ohlcv(50)
        tr = true_range(df["high"], df["low"], df["close"])
        assert (tr >= 0).all()

    def test_tr_equals_hl_when_no_gap(self):
        """
        When price opens exactly at prior close (no gap), TR = high - low.
        Construct data: prev_close = 100, high = 102, low = 99, close = 101.
        TR = max(102-99, |102-100|, |99-100|) = max(3, 2, 1) = 3
        """
        df = pd.DataFrame({
            "high":  [101.0, 102.0],
            "low":   [99.0,  99.0],
            "close": [100.0, 101.0],
        })
        tr = true_range(df["high"], df["low"], df["close"])
        # Row 1: max(3, |102-100|, |99-100|) = max(3, 2, 1) = 3
        assert tr.iloc[1] == pytest.approx(3.0)

    def test_tr_gap_up(self):
        """
        Gap-up scenario: prev_close = 100, high = 115, low = 108.
        TR = max(7, |115-100|, |108-100|) = max(7, 15, 8) = 15
        """
        df = pd.DataFrame({
            "high":  [100.0, 115.0],
            "low":   [98.0,  108.0],
            "close": [100.0, 110.0],
        })
        tr = true_range(df["high"], df["low"], df["close"])
        assert tr.iloc[1] == pytest.approx(15.0)

    def test_tr_gap_down(self):
        """
        Gap-down scenario: prev_close = 100, high = 93, low = 88.
        TR = max(5, |93-100|, |88-100|) = max(5, 7, 12) = 12
        """
        df = pd.DataFrame({
            "high":  [100.0, 93.0],
            "low":   [98.0,  88.0],
            "close": [100.0, 90.0],
        })
        tr = true_range(df["high"], df["low"], df["close"])
        assert tr.iloc[1] == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# ATR tests
# ---------------------------------------------------------------------------


class TestATR:

    def test_atr14_returns_correct_length(self):
        df = _make_ohlcv(30)
        result = atr_wilder(df["high"], df["low"], df["close"], period=14)
        assert len(result) == 30

    def test_atr14_first_13_rows_are_nan(self):
        """Rows 0..12 must be NaN (need 14 TRs for first ATR)."""
        df = _make_ohlcv(30)
        result = atr_wilder(df["high"], df["low"], df["close"], period=14)
        assert result.iloc[:13].isna().all()

    def test_atr14_row_13_is_mean_of_first_14_trs(self):
        """
        ATR[13] must equal the simple mean of TR[0..13].
        Verified using constant OHLCV (high=101, low=99 → TR=2 for all rows after 0).
        Row 0: TR = 2.0 (high-low, no prev close)
        Rows 1..13: TR = max(2, |101-100|, |99-100|) = max(2,1,1) = 2.0
        So ATR[13] = mean([2.0]*14) = 2.0
        """
        df = _constant_ohlcv(price=100.0, n=30)
        result = atr_wilder(df["high"], df["low"], df["close"], period=14)
        assert result.iloc[13] == pytest.approx(2.0)

    def test_atr14_subsequent_values_use_wilder_smoothing(self):
        """
        ATR[14] should follow Wilder's formula:
        ATR[14] = (ATR[13] * 13 + TR[14]) / 14
        With constant data (ATR[13]=2, TR[14]=2):
        ATR[14] = (2*13 + 2) / 14 = 28/14 = 2.0
        """
        df = _constant_ohlcv(price=100.0, n=30)
        result = atr_wilder(df["high"], df["low"], df["close"], period=14)
        assert result.iloc[14] == pytest.approx(2.0)

    def test_atr14_is_always_positive(self):
        """ATR must be positive (True Range is always >= 0)."""
        df = _make_ohlcv(50)
        result = atr_wilder(df["high"], df["low"], df["close"], period=14)
        valid = result.dropna()
        assert (valid > 0).all()

    def test_atr_insufficient_data_all_nan(self):
        """If fewer rows than period, all values are NaN."""
        df = _make_ohlcv(5)
        result = atr_wilder(df["high"], df["low"], df["close"], period=14)
        assert result.isna().all()

    def test_atr_invalid_period_raises(self):
        df = _make_ohlcv(20)
        with pytest.raises(ValueError):
            atr_wilder(df["high"], df["low"], df["close"], period=0)


# ---------------------------------------------------------------------------
# Average Volume tests
# ---------------------------------------------------------------------------


class TestAvgVolume:

    def test_avg_volume_first_19_nan(self):
        """First 19 rows must be NaN for avg_volume(window=20)."""
        df = _constant_ohlcv(vol=5_000_000.0, n=40)
        result = avg_volume(df["volume"], window=20)
        assert result.iloc[:19].isna().all()

    def test_avg_volume_row_19_correct(self):
        """Row 19 must equal the exact mean of rows 0..19."""
        volumes = list(range(1_000_000, 1_000_000 + 40 * 100_000, 100_000))
        vol = pd.Series(volumes, dtype=float)
        result = avg_volume(vol, window=20)
        expected = sum(volumes[:20]) / 20
        assert result.iloc[19] == pytest.approx(expected)

    def test_avg_volume_constant(self):
        """avg_volume of constant volume series equals that constant."""
        df = _constant_ohlcv(vol=3_000_000.0, n=30)
        result = avg_volume(df["volume"], window=20)
        valid = result.dropna()
        np.testing.assert_allclose(valid.values, 3_000_000.0)

    def test_avg_volume_invalid_window_raises(self):
        with pytest.raises(ValueError):
            avg_volume(pd.Series([1.0, 2.0]), window=0)


# ---------------------------------------------------------------------------
# Volume Ratio tests
# ---------------------------------------------------------------------------


class TestVolumeRatio:

    def test_volume_ratio_correct_value(self):
        """volume_ratio = volume / avg_vol."""
        vol = pd.Series([10_000_000.0] * 5)
        avg = pd.Series([5_000_000.0] * 5)
        result = volume_ratio(vol, avg)
        np.testing.assert_allclose(result.values, 2.0)

    def test_volume_ratio_nan_when_avg_is_nan(self):
        """NaN denominator must produce NaN ratio."""
        vol = pd.Series([1_000_000.0, 2_000_000.0])
        avg = pd.Series([np.nan, 1_000_000.0])
        result = volume_ratio(vol, avg)
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == pytest.approx(2.0)

    def test_volume_ratio_nan_when_avg_is_zero(self):
        """Zero denominator must produce NaN (not infinity)."""
        vol = pd.Series([1_000_000.0])
        avg = pd.Series([0.0])
        result = volume_ratio(vol, avg)
        assert pd.isna(result.iloc[0])

    def test_volume_ratio_less_than_1_when_volume_below_avg(self):
        vol = pd.Series([500_000.0])
        avg = pd.Series([1_000_000.0])
        result = volume_ratio(vol, avg)
        assert result.iloc[0] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Momentum tests
# ---------------------------------------------------------------------------


class TestMomentum:

    def test_momentum_5_first_5_rows_nan(self):
        """First 5 rows of momentum_5 must be NaN."""
        close = _make_close([100.0] * 20)
        result = momentum(close, period=5)
        assert result.iloc[:5].isna().all()

    def test_momentum_5_row_5_correct(self):
        """
        momentum_5[5] = (close[5] / close[0]) - 1
        """
        values = [100.0, 101.0, 102.0, 103.0, 104.0, 110.0]
        close = _make_close(values)
        result = momentum(close, period=5)
        expected = (110.0 / 100.0) - 1.0  # = 0.1
        assert result.iloc[5] == pytest.approx(expected)

    def test_momentum_20_first_20_rows_nan(self):
        """First 20 rows of momentum_20 must be NaN."""
        close = _make_close([100.0] * 30)
        result = momentum(close, period=20)
        assert result.iloc[:20].isna().all()

    def test_momentum_20_row_20_correct(self):
        """momentum_20[20] = (close[20] / close[0]) - 1"""
        values = [100.0] * 20 + [120.0]
        close = _make_close(values)
        result = momentum(close, period=20)
        expected = (120.0 / 100.0) - 1.0  # = 0.2
        assert result.iloc[20] == pytest.approx(expected)

    def test_momentum_zero_when_constant(self):
        """Momentum of constant series is 0 everywhere (after warm-up)."""
        close = _make_close([50.0] * 30)
        result = momentum(close, period=5)
        valid = result.dropna()
        np.testing.assert_allclose(valid.values, 0.0, atol=1e-12)

    def test_momentum_negative_when_price_falls(self):
        values = [110.0] + [100.0] * 5
        close = _make_close(values)
        result = momentum(close, period=5)
        # momentum[5] = (100/110) - 1 < 0
        assert result.iloc[5] < 0

    def test_momentum_invalid_period_raises(self):
        with pytest.raises(ValueError):
            momentum(_make_close([1.0, 2.0]), period=0)


# ---------------------------------------------------------------------------
# compute_all_features integration tests
# ---------------------------------------------------------------------------


class TestComputeAllFeatures:

    def test_output_row_count_unchanged(self):
        """Feature computation must not add or drop rows."""
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert len(result) == 60

    def test_all_feature_columns_present(self):
        """All 9 feature columns must be present in the output."""
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        for col in FEATURE_COLUMNS:
            assert col in result.columns, f"Missing feature column: {col}"

    def test_original_ohlcv_columns_unchanged(self):
        """OHLCV values in the output must be identical to the input."""
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        for col in ["open", "high", "low", "close", "volume"]:
            pd.testing.assert_series_equal(
                df[col].reset_index(drop=True),
                result[col].reset_index(drop=True),
                check_names=False,
            )

    def test_input_not_mutated(self):
        """The input DataFrame must not be modified by compute_all_features."""
        df = _make_ohlcv(60)
        original_cols = list(df.columns)
        compute_all_features(df)
        assert list(df.columns) == original_cols

    def test_missing_column_raises(self):
        """Missing required input column must raise ValueError."""
        df = _make_ohlcv(60).drop(columns=["close"])
        with pytest.raises(ValueError, match="close"):
            compute_all_features(df)

    def test_sma20_nan_in_first_19_rows(self):
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert result["sma20"].iloc[:19].isna().all()

    def test_sma50_nan_in_first_49_rows(self):
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert result["sma50"].iloc[:49].isna().all()

    def test_atr14_nan_in_first_13_rows(self):
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert result["atr14"].iloc[:13].isna().all()

    def test_momentum_5_nan_in_first_5_rows(self):
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert result["momentum_5"].iloc[:5].isna().all()

    def test_momentum_20_nan_in_first_20_rows(self):
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert result["momentum_20"].iloc[:20].isna().all()

    def test_volume_ratio_nan_where_avg_volume_nan(self):
        """volume_ratio must be NaN in the first 19 rows (avg_volume_20 is NaN there)."""
        df = _make_ohlcv(60)
        result = compute_all_features(df)
        assert result["volume_ratio"].iloc[:19].isna().all()

    def test_reproducible_output(self):
        """Running compute_all_features twice on same input produces identical results."""
        df = _make_ohlcv(60)
        r1 = compute_all_features(df.copy())
        r2 = compute_all_features(df.copy())
        pd.testing.assert_frame_equal(r1, r2)

    def test_lookahead_changing_future_row_does_not_affect_past(self):
        """
        LOOKAHEAD TEST.

        Compute features on the original DataFrame, record values at row 10.
        Then change the close prices of rows 11..20 dramatically.
        Recompute features.
        The values at row 10 and earlier must be identical.

        This verifies that no feature uses future information.
        """
        df = _make_ohlcv(60)
        df_original = df.copy()

        # Compute on original
        result_original = compute_all_features(df_original)

        # Mutate future rows (rows 11..20) — multiply close by 100
        df_mutated = df.copy()
        df_mutated.loc[11:20, "close"] = df_mutated.loc[11:20, "close"] * 100.0
        df_mutated.loc[11:20, "high"] = df_mutated.loc[11:20, "high"] * 100.0
        df_mutated.loc[11:20, "low"] = df_mutated.loc[11:20, "low"] * 100.0
        df_mutated.loc[11:20, "volume"] = df_mutated.loc[11:20, "volume"] * 100.0

        result_mutated = compute_all_features(df_mutated)

        # Feature values at rows 0..10 must be identical
        for col in ["ema20", "ema50", "momentum_5"]:
            for row in range(11):
                orig = result_original[col].iloc[row]
                mut = result_mutated[col].iloc[row]
                if pd.isna(orig):
                    assert pd.isna(mut), (
                        f"Lookahead detected: {col}[{row}] changed from NaN to {mut}"
                    )
                else:
                    assert orig == pytest.approx(mut, rel=1e-9), (
                        f"Lookahead detected: {col}[{row}] changed from {orig} to {mut}"
                    )

        # SMA20 at rows 0..10: all NaN (warm-up), so both should be NaN
        for row in range(11):
            assert pd.isna(result_original["sma20"].iloc[row])
            assert pd.isna(result_mutated["sma20"].iloc[row])
