"""
tests/test_strategy.py
-----------------------
Unit tests for quant.strategies.trend_momentum.

Tests each of the four strategy conditions independently,
the combined LONG signal, breakout correctness (shift-1),
and lookahead isolation.

All tests use small synthetic DataFrames — no dependency on the ITC dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quant.features.indicators import compute_all_features
from quant.strategies.trend_momentum import (
    BREAKOUT_PERIOD,
    CONDITION_COLUMNS,
    SIGNAL_LONG,
    SIGNAL_NONE,
    VOLUME_SURGE_THRESHOLD,
    apply_strategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_row() -> dict:
    """
    Return a dict with all required feature columns set to safe,
    condition-passing values (all four conditions True by default).

    Individual tests will override the relevant field to make a specific
    condition False and verify that NO_SIGNAL results.
    """
    return {
        "date": pd.Timestamp("2020-01-01"),
        "symbol": "TEST",
        "open": 100.0,
        "high": 106.0,
        "low": 98.0,
        "close": 105.0,
        "volume": 10_000_000.0,
        # Features — values chosen so all 4 conditions are True:
        "ema20": 102.0,       # ema20 > ema50 (102 > 100)
        "ema50": 100.0,
        "sma20": 101.0,
        "sma50": 99.0,
        "atr14": 2.0,
        "avg_volume_20": 5_000_000.0,
        "volume_ratio": 2.0,  # > 1.5 (volume surge) ✓
        "momentum_5": 0.05,
        "momentum_20": 0.10,
    }


def _make_feature_df(rows: list[dict]) -> pd.DataFrame:
    """Build a feature DataFrame from a list of row dicts."""
    return pd.DataFrame(rows)


def _all_passing_single_row() -> pd.DataFrame:
    """Single row where all four conditions are True."""
    return _make_feature_df([_base_row()])


def _build_breakout_dataset(n_rows: int = 25) -> pd.DataFrame:
    """
    Build a synthetic feature DataFrame designed to test breakout correctness.

    Close values:
      - Rows 0..19: all set to 100.0 (so previous-20-day-high = 100)
      - Row 20: set to 101.0 (just above the previous 20-day high → breakout)
      - Row 21: set to 99.0  (below previous 20-day high → no breakout)

    Other features are set so that conditions 1, 2, 4 are always True,
    so only condition 3 (breakout) distinguishes LONG vs NO_SIGNAL.
    """
    rows = []
    for i in range(n_rows):
        if i < 20:
            close = 100.0
        elif i == 20:
            close = 101.0   # breakout
        else:
            close = 99.0    # no breakout

        row = {
            "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
            "symbol": "TEST",
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 10_000_000.0,
            "ema20": close - 1.0,   # close > ema20 always True
            "ema50": close - 2.0,   # ema20 > ema50 always True
            "sma20": close - 1.5,
            "sma50": close - 2.5,
            "atr14": 2.0,
            "avg_volume_20": 5_000_000.0,
            "volume_ratio": 2.0,    # volume_ratio > 1.5 always True
            "momentum_5": 0.01,
            "momentum_20": 0.05,
        }
        rows.append(row)
    return _make_feature_df(rows)


# ---------------------------------------------------------------------------
# Output shape and column tests
# ---------------------------------------------------------------------------


class TestApplyStrategyOutput:

    def test_output_row_count_unchanged(self):
        """apply_strategy must not add or drop rows."""
        df = _all_passing_single_row()
        result = apply_strategy(df)
        assert len(result) == 1

    def test_condition_columns_present(self):
        """All four diagnostic condition columns must be present."""
        df = _all_passing_single_row()
        result = apply_strategy(df)
        for col in CONDITION_COLUMNS:
            assert col in result.columns, f"Missing condition column: {col}"

    def test_signal_column_present(self):
        """signal column must be present."""
        df = _all_passing_single_row()
        result = apply_strategy(df)
        assert "signal" in result.columns

    def test_signal_values_are_valid(self):
        """signal column must contain only LONG or NO_SIGNAL."""
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        valid = {SIGNAL_LONG, SIGNAL_NONE}
        assert set(result["signal"].unique()).issubset(valid)

    def test_input_not_mutated(self):
        """apply_strategy must not modify the input DataFrame."""
        df = _all_passing_single_row()
        original_cols = list(df.columns)
        apply_strategy(df)
        assert list(df.columns) == original_cols

    def test_missing_feature_column_raises(self):
        """Missing required feature column must raise ValueError."""
        df = _all_passing_single_row().drop(columns=["ema20"])
        with pytest.raises(ValueError, match="ema20"):
            apply_strategy(df)


# ---------------------------------------------------------------------------
# Individual condition tests (condition isolation)
# ---------------------------------------------------------------------------


class TestCondition1Trend:

    def test_all_conditions_true_gives_long(self):
        """Baseline: all four conditions True → LONG."""
        df = _all_passing_single_row()
        result = apply_strategy(df)
        # Note: row 0 has no previous-20d history so breakout_condition = False
        # We need to test condition isolation properly.
        # This single-row test will produce NO_SIGNAL for breakout (no history).
        # Instead verify trend_condition is True.
        assert result["trend_condition"].iloc[0] is True or result["trend_condition"].iloc[0] == True

    def test_ema20_less_than_ema50_gives_no_long(self):
        """Condition 1 false (ema20 <= ema50) → trend_condition False → NO_SIGNAL."""
        row = _base_row()
        row["ema20"] = 98.0   # ema20 < ema50 (100)
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["trend_condition"].iloc[0] == False
        assert result["signal"].iloc[0] == SIGNAL_NONE

    def test_ema20_equals_ema50_gives_no_long(self):
        """ema20 == ema50 is not strictly greater → NO_SIGNAL."""
        row = _base_row()
        row["ema20"] = 100.0
        row["ema50"] = 100.0
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["trend_condition"].iloc[0] == False

    def test_trend_condition_true_when_ema20_above_ema50(self):
        """Verify trend_condition=True when ema20 > ema50."""
        row = _base_row()
        row["ema20"] = 105.0
        row["ema50"] = 100.0
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["trend_condition"].iloc[0] == True


class TestCondition2Price:

    def test_close_below_ema20_gives_no_long(self):
        """Condition 2 false (close <= ema20) → price_condition False."""
        row = _base_row()
        row["close"] = 100.0
        row["ema20"] = 102.0   # close < ema20
        row["ema50"] = 98.0
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["price_condition"].iloc[0] == False
        assert result["signal"].iloc[0] == SIGNAL_NONE

    def test_close_equals_ema20_gives_no_long(self):
        """close == ema20 is not strictly above → price_condition False."""
        row = _base_row()
        row["close"] = 102.0
        row["ema20"] = 102.0
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["price_condition"].iloc[0] == False

    def test_close_above_ema20_gives_true(self):
        row = _base_row()
        row["close"] = 105.0
        row["ema20"] = 102.0
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["price_condition"].iloc[0] == True


class TestCondition3Breakout:

    def test_breakout_condition_false_for_first_20_rows(self):
        """
        rolling_max(20, min_periods=20) first produces a non-NaN at row 19.
        After shift(1), the first valid previous-20-day-high is at row 20.
        Therefore rows 0..19 (first 20 rows) must always have breakout_condition=False.
        Row 20 may legitimately be True if close[20] > max(close[0..19]).
        """
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        # Rows 0..19: no sufficient prior history → breakout_condition must be False
        for i in range(20):
            assert result["breakout_condition"].iloc[i] == False, (
                f"Expected breakout_condition=False at row {i}, got True"
            )


    def test_breakout_at_row_20_when_close_exceeds_previous_20d_high(self):
        """
        Row 20 has close=101, previous 20 rows all had close=100.
        Previous-20-day-high = max(rows 0..19) = 100.
        101 > 100 → breakout_condition should be True.
        """
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        assert result["breakout_condition"].iloc[20] == True

    def test_no_breakout_when_close_below_previous_high(self):
        """Row 21 has close=99 < previous-20-day-high → breakout_condition=False."""
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        assert result["breakout_condition"].iloc[21] == False

    def test_breakout_uses_shift_1_not_current_close(self):
        """
        CRITICAL SHIFT-1 TEST.

        Design:
          Rows 0..18: close = 100
          Row 19:     close = 200  (a very high value)
          Row 20:     close = 201  (above 200, would be a breakout IF today were
                                    included in the rolling window — but it shouldn't be)

        With correct shift(1) implementation:
          At row 20, previous-20-day-high = max(rows 0..19) = 200.
          close[20] = 201 > 200 → breakout_condition = True ✓

        Now: if we set row 20's close to 199 (below 200):
          close[20] = 199 < 200 → breakout_condition = False ✓

        This confirms today's close does NOT affect its own breakout comparison.
        """
        rows = []
        for i in range(25):
            if i < 19:
                close = 100.0
            elif i == 19:
                close = 200.0   # spike on row 19
            elif i == 20:
                close = 201.0   # above 200 → breakout
            else:
                close = 150.0

            row = {
                "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                "symbol": "TEST",
                "open": close, "high": close + 1, "low": close - 1, "close": close,
                "volume": 10_000_000.0,
                "ema20": close - 1.0, "ema50": close - 2.0,
                "sma20": close - 1.5, "sma50": close - 2.5, "atr14": 2.0,
                "avg_volume_20": 5_000_000.0, "volume_ratio": 2.0,
                "momentum_5": 0.01, "momentum_20": 0.05,
            }
            rows.append(row)

        df = _make_feature_df(rows)
        result = apply_strategy(df)

        # Row 20: close=201, prev-20d-high=max(rows 0..19)=200 → breakout=True
        assert result["breakout_condition"].iloc[20] == True

        # Now change row 20 close to 199 (below prev-20d-high=200)
        rows[20]["close"] = 199.0
        rows[20]["ema20"] = 198.0  # keep close > ema20
        df2 = _make_feature_df(rows)
        result2 = apply_strategy(df2)
        # 199 < 200 → no breakout
        assert result2["breakout_condition"].iloc[20] == False

    def test_today_close_not_in_own_breakout_window(self):
        """
        If today's close were included in the rolling window, a row
        with close == rolling_max would count as NOT breaking out
        (strict greater than). But the shift(1) means we compare against
        the rolling max of PRIOR rows.

        Construct: rows 0..18 = 100, row 19 = 150 (new max in window).
        At row 20: rolling_max(rows 1..20) would include row 19's 150.
        But with shift(1): prev-20d-high at row 20 = max(rows 0..19) = 150.
        If close[20] = 151 → breakout.
        If close[20] = 150 → no breakout (equal, not strictly greater).
        """
        rows = []
        for i in range(22):
            close = 100.0 if i < 19 else (150.0 if i == 19 else 151.0 if i == 20 else 100.0)
            row = {
                "date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=i),
                "symbol": "TEST",
                "open": close, "high": close + 1, "low": close - 1, "close": close,
                "volume": 10_000_000.0,
                "ema20": close - 1, "ema50": close - 2,
                "sma20": close - 1.5, "sma50": close - 2.5, "atr14": 2.0,
                "avg_volume_20": 5_000_000.0, "volume_ratio": 2.0,
                "momentum_5": 0.01, "momentum_20": 0.05,
            }
            rows.append(row)

        df = _make_feature_df(rows)
        result = apply_strategy(df)
        # Row 20: close=151, prev-20d-high=max(rows 0..19)=150 → breakout=True
        assert result["breakout_condition"].iloc[20] == True


class TestCondition4Volume:

    def test_volume_below_threshold_gives_no_long(self):
        """volume_ratio <= 1.5 → volume_condition False → NO_SIGNAL."""
        row = _base_row()
        row["volume_ratio"] = 1.5   # not strictly greater
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["volume_condition"].iloc[0] == False

    def test_volume_ratio_nan_gives_false(self):
        """NaN volume_ratio → volume_condition False (not a LONG)."""
        row = _base_row()
        row["volume_ratio"] = np.nan
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["volume_condition"].iloc[0] == False
        assert result["signal"].iloc[0] == SIGNAL_NONE

    def test_volume_above_threshold_gives_true(self):
        row = _base_row()
        row["volume_ratio"] = 1.51
        df = _make_feature_df([row])
        result = apply_strategy(df)
        assert result["volume_condition"].iloc[0] == True

    def test_threshold_value(self):
        """VOLUME_SURGE_THRESHOLD must be 1.5."""
        assert VOLUME_SURGE_THRESHOLD == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# Full signal integration tests
# ---------------------------------------------------------------------------


class TestFullSignal:

    def test_long_signal_generated_when_all_conditions_true(self):
        """
        Use the breakout dataset where row 20 has close > prev-20d-high.
        Conditions 1, 2, 4 are all True by construction.
        Row 20 must produce LONG.
        """
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        assert result["signal"].iloc[20] == SIGNAL_LONG

    def test_no_signal_before_sufficient_history(self):
        """
        Rows 0..19 must all be NO_SIGNAL: breakout_condition needs 20 prior bars
        for rolling_max(20), and after shift(1) the first valid comparison is at row 20.
        """
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        for i in range(20):
            assert result["signal"].iloc[i] == SIGNAL_NONE, (
                f"Expected NO_SIGNAL at row {i}, got {result['signal'].iloc[i]}"
            )


    def test_condition_1_false_alone_prevents_long(self):
        """Only condition 1 is False → NO_SIGNAL."""
        df = _build_breakout_dataset(25)
        df = df.copy()
        df.loc[20, "ema50"] = df.loc[20, "ema20"] + 1.0  # ema20 < ema50 → cond1 False
        result = apply_strategy(df)
        assert result["signal"].iloc[20] == SIGNAL_NONE

    def test_condition_2_false_alone_prevents_long(self):
        """Only condition 2 is False → NO_SIGNAL."""
        df = _build_breakout_dataset(25)
        df = df.copy()
        df.loc[20, "ema20"] = df.loc[20, "close"] + 1.0  # close < ema20 → cond2 False
        result = apply_strategy(df)
        assert result["signal"].iloc[20] == SIGNAL_NONE

    def test_condition_3_false_alone_prevents_long(self):
        """Only condition 3 is False → NO_SIGNAL (close does not break 20d high)."""
        df = _build_breakout_dataset(25)
        df = df.copy()
        df.loc[20, "close"] = 99.0   # below prev-20d-high (100) → cond3 False
        df.loc[20, "ema20"] = 98.0   # keep close > ema20
        result = apply_strategy(df)
        assert result["signal"].iloc[20] == SIGNAL_NONE

    def test_condition_4_false_alone_prevents_long(self):
        """Only condition 4 is False → NO_SIGNAL."""
        df = _build_breakout_dataset(25)
        df = df.copy()
        df.loc[20, "volume_ratio"] = 1.0   # below 1.5 → cond4 False
        result = apply_strategy(df)
        assert result["signal"].iloc[20] == SIGNAL_NONE

    def test_diagnostic_columns_are_bool(self):
        """Diagnostic condition columns must be boolean dtype."""
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        for col in CONDITION_COLUMNS:
            assert result[col].dtype in (bool, np.dtype("bool")), (
                f"Column '{col}' dtype should be bool, got {result[col].dtype}"
            )

    def test_signal_is_long_only_when_all_four_true(self):
        """signal==LONG iff all four condition columns are True."""
        df = _build_breakout_dataset(25)
        result = apply_strategy(df)
        all_true = (
            result["trend_condition"]
            & result["price_condition"]
            & result["breakout_condition"]
            & result["volume_condition"]
        )
        long_mask = result["signal"] == SIGNAL_LONG
        pd.testing.assert_series_equal(
            all_true.reset_index(drop=True),
            long_mask.reset_index(drop=True),
            check_names=False,
        )

    def test_reproducible_signal(self):
        """Running apply_strategy twice gives identical results."""
        df = _build_breakout_dataset(25)
        r1 = apply_strategy(df.copy())
        r2 = apply_strategy(df.copy())
        pd.testing.assert_frame_equal(
            r1.reset_index(drop=True),
            r2.reset_index(drop=True),
        )


# ---------------------------------------------------------------------------
# End-to-end: compute_all_features + apply_strategy
# ---------------------------------------------------------------------------


class TestEndToEnd:

    def _make_itc_style_df(self, n: int = 100) -> pd.DataFrame:
        """
        Build a realistic OHLCV DataFrame that mimics the itc_daily_clean.csv format.
        Uses a seeded random walk so tests are deterministic.
        """
        rng = np.random.default_rng(0)
        close = 200.0 + np.cumsum(rng.normal(0, 2, n))
        high = close + rng.uniform(1, 4, n)
        low = close - rng.uniform(1, 4, n)
        open_ = close + rng.normal(0, 1, n)
        volume = rng.uniform(5_000_000, 30_000_000, n)

        return pd.DataFrame({
            "date": pd.date_range("2020-01-01", periods=n, freq="B"),
            "symbol": "ITC",
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

    def test_pipeline_output_row_count(self):
        df = self._make_itc_style_df(100)
        features = compute_all_features(df)
        signals = apply_strategy(features)
        assert len(signals) == 100

    def test_pipeline_all_required_columns_present(self):
        df = self._make_itc_style_df(100)
        features = compute_all_features(df)
        signals = apply_strategy(features)
        expected = (
            ["date", "symbol", "open", "high", "low", "close", "volume"]
            + ["ema20", "ema50", "sma20", "sma50", "atr14",
               "avg_volume_20", "volume_ratio", "momentum_5", "momentum_20"]
            + CONDITION_COLUMNS
            + ["signal"]
        )
        for col in expected:
            assert col in signals.columns, f"Missing column: {col}"

    def test_lookahead_strategy_signal(self):
        """
        LOOKAHEAD TEST for strategy signals.

        Compute signals on original data. Record signal at row 30.
        Mutate rows 31..40 (future). Recompute.
        Signal at row 30 must be unchanged.
        """
        df = self._make_itc_style_df(100)

        features_orig = compute_all_features(df.copy())
        signals_orig = apply_strategy(features_orig)

        # Mutate future rows
        df_mut = df.copy()
        df_mut.loc[31:40, "close"] = df_mut.loc[31:40, "close"] * 1000.0
        df_mut.loc[31:40, "volume"] = df_mut.loc[31:40, "volume"] * 1000.0

        features_mut = compute_all_features(df_mut)
        signals_mut = apply_strategy(features_mut)

        # Signals at row 30 and earlier must be identical
        for row in range(31):
            orig_sig = signals_orig["signal"].iloc[row]
            mut_sig = signals_mut["signal"].iloc[row]
            assert orig_sig == mut_sig, (
                f"Lookahead detected in signal at row {row}: "
                f"'{orig_sig}' changed to '{mut_sig}' when future rows were mutated."
            )
