"""
tests/test_walk_forward.py
--------------------------
Comprehensive unit tests for the Sprint 6 validation package.

Coverage (21 tests):

  Walk-forward splitter:
    1.  test_split_no_overlap
    2.  test_split_chronological
    3.  test_split_covers_full_range
    4.  test_split_insufficient_data_skipped
    5.  test_split_reset_index

  Walk-forward engine:
    6.  test_walk_forward_returns_list_of_windows
    7.  test_walk_forward_each_window_has_metrics
    8.  test_walk_forward_deterministic

  Buy-and-hold benchmark:
    9.  test_buy_hold_result_matches_manual
    10. test_buy_hold_costs_applied
    11. test_buy_hold_insufficient_data

  Sensitivity analysis:
    12. test_sensitivity_baseline_included
    13. test_sensitivity_no_extra_configs

  Integrity gates:
    14. test_gate_overlap_detection
    15. test_gate_chronological_detection
    16. test_gate_symbol_isolation
    17. test_gate_determinism

  Truncation-invariance (Correction 3 — MANDATORY):
    18. test_truncation_invariance
    19. test_future_rows_cannot_alter_past_features

  ITC full-dataset regression (explicit lock):
    20. test_itc_full_dataset_regression

  CLI:
    21. test_cli_runs_without_error

All tests use SYNTHETIC DataFrames — no dependency on the ITC dataset
on disk, except test_itc_full_dataset_regression and test_cli_runs_without_error
which require the real ITC features CSV and are marked with
@pytest.mark.integration.

Run unit tests only (no integration):
    pytest tests/test_walk_forward.py -m "not integration" -v

Run all including integration:
    pytest tests/test_walk_forward.py -v
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import pytest

from quant.backtest.costs import CostModel
from quant.backtest.engine import BacktestConfig
from quant.backtest.metrics import compute_metrics
from quant.validation.benchmark import run_buy_hold
from quant.validation.gates import ValidationIntegrityError, run_integrity_gates
from quant.validation.sensitivity import (
    SENSITIVITY_GRID,
    SensitivityResult,
    run_sensitivity,
)
from quant.validation.splitter import (
    DataSplit,
    chronological_splits,
    slice_dev_df,
    slice_test_df,
)
from quant.validation.walk_forward import WalkForwardSummary, WalkForwardWindow, run_walk_forward


# ---------------------------------------------------------------------------
# Project root / ITC path
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent
ITC_FEATURES_CSV = PROJECT_ROOT / "Data" / "processed" / "stocks" / "ITC_features.csv"
ITC_OHLCV_CSV = PROJECT_ROOT / "Data" / "processed" / "stocks" / "ITC.csv"


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

NO_COST = CostModel(commission_rate=0.0, slippage_rate=0.0)
NO_COST_CONFIG = BacktestConfig(
    initial_capital=100_000.0,
    risk_per_trade=0.01,
    atr_multiplier=2.0,
    cost_model=NO_COST,
    symbol="TEST",
)


def _make_ohlcv(n_rows: int, start_date: str = "2010-01-04") -> pd.DataFrame:
    """
    Build a synthetic daily OHLCV DataFrame with deterministic prices.

    Prices follow a simple upward ramp so the strategy can generate
    some signals. The 'signal' column is set to LONG on rows that
    are multiples of 30, otherwise NO_SIGNAL. This gives a predictable
    number of signals for testing.
    """
    dates = pd.bdate_range(start=start_date, periods=n_rows)
    close = 100.0 + np.arange(n_rows) * 0.05
    open_ = close * 0.99
    high = close * 1.01
    low = close * 0.98
    volume = np.full(n_rows, 1_000_000.0)
    symbol = ["TEST"] * n_rows

    df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "symbol": symbol,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    return df


def _make_feature_df(n_rows: int, start_date: str = "2010-01-04") -> pd.DataFrame:
    """
    Build a synthetic features DataFrame with all required backtest columns.

    EMA values are set so trend_condition is True after warm-up.
    ATR is fixed at 2.0. Signals are placed every 30 rows.
    """
    df = _make_ohlcv(n_rows, start_date)

    close = df["close"].values
    # ema20 slightly below close (trend up), ema50 below ema20
    df["ema20"] = close * 0.98
    df["ema50"] = close * 0.96
    df["sma20"] = close * 0.97
    df["sma50"] = close * 0.95
    df["atr14"] = 2.0
    df["avg_volume_20"] = 900_000.0
    df["volume_ratio"] = df["volume"] / df["avg_volume_20"]
    df["momentum_5"] = 0.01
    df["momentum_20"] = 0.04

    # Conditions
    df["trend_condition"] = True
    df["price_condition"] = True
    df["breakout_condition"] = False  # default False, set True on signal rows
    df["volume_condition"] = True

    # Place LONG signals every 30 rows (after warm-up row 20)
    signals = ["NO_SIGNAL"] * n_rows
    for i in range(21, n_rows, 30):
        signals[i] = "LONG"
        df.at[i, "breakout_condition"] = True

    df["signal"] = signals
    return df


# ---------------------------------------------------------------------------
# 1. test_split_no_overlap
# ---------------------------------------------------------------------------

def test_split_no_overlap():
    """
    Development and test date ranges must never share a row.
    For every window: max(dev_dates) < min(test_dates).
    """
    df = _make_feature_df(500, start_date="2010-01-04")
    splits = chronological_splits(df, symbol="TEST", initial_dev_years=1, step_months=3, test_months=3)

    assert splits, "Expected at least one split."

    for split in splits:
        if split.status == "INSUFFICIENT_DATA" or not split.dev_end or not split.test_start:
            continue
        dev_end = pd.Timestamp(split.dev_end)
        test_start = pd.Timestamp(split.test_start)
        assert dev_end < test_start, (
            f"Window {split.window_index}: dev_end={split.dev_end!r} >= "
            f"test_start={split.test_start!r}. Overlap detected."
        )


# ---------------------------------------------------------------------------
# 2. test_split_chronological
# ---------------------------------------------------------------------------

def test_split_chronological():
    """
    Split test_start values must be strictly ascending across all windows.
    """
    df = _make_feature_df(500, start_date="2010-01-04")
    splits = chronological_splits(df, symbol="TEST", initial_dev_years=1, step_months=3, test_months=3)

    ok_splits = [s for s in splits if s.test_start]
    timestamps = [pd.Timestamp(s.test_start) for s in ok_splits]

    for i in range(1, len(timestamps)):
        assert timestamps[i] > timestamps[i - 1], (
            f"Window {ok_splits[i].window_index}: test_start not strictly "
            f"after previous window's test_start."
        )


# ---------------------------------------------------------------------------
# 3. test_split_covers_full_range
# ---------------------------------------------------------------------------

def test_split_covers_full_range():
    """
    No date should appear in more than one test window.
    This verifies that when step_months >= test_months, test windows
    are strictly non-overlapping.
    """
    df = _make_feature_df(500, start_date="2010-01-04")
    # step_months > test_months guarantees non-overlapping test windows.
    splits = chronological_splits(
        df, symbol="TEST",
        initial_dev_years=1, step_months=4, test_months=3,
    )

    covered_dates: set = set()

    for split in splits:
        if not split.test_start or not split.test_end:
            continue
        test_df = slice_test_df(df, split)
        for d in pd.to_datetime(test_df["date"]):
            assert d not in covered_dates, (
                f"Date {d} appears in multiple test windows — overlap detected "
                f"(window {split.window_index}, test_start={split.test_start})."
            )
            covered_dates.add(d)

    assert len(covered_dates) > 0, "No dates were covered by any test window."


# ---------------------------------------------------------------------------
# 4. test_split_insufficient_data_skipped
# ---------------------------------------------------------------------------

def test_split_insufficient_data_skipped():
    """
    Windows with fewer than min_test_rows rows must be labelled INSUFFICIENT_DATA.
    """
    df = _make_feature_df(100, start_date="2010-01-04")
    # Use a very large min_test_rows so all windows are INSUFFICIENT.
    splits = chronological_splits(
        df, symbol="TEST",
        initial_dev_years=0, step_months=1, test_months=1,
        min_test_rows=999,
    )
    for split in splits:
        assert split.status == "INSUFFICIENT_DATA", (
            f"Expected INSUFFICIENT_DATA for window {split.window_index}, "
            f"got {split.status!r}."
        )


# ---------------------------------------------------------------------------
# 5. test_split_reset_index
# ---------------------------------------------------------------------------

def test_split_reset_index():
    """
    Sliced DataFrames returned by slice_test_df and slice_dev_df
    must have a clean 0-based RangeIndex.
    """
    df = _make_feature_df(300, start_date="2012-01-02")
    splits = chronological_splits(df, symbol="TEST", initial_dev_years=1, step_months=3, test_months=3)

    for split in splits:
        test_df = slice_test_df(df, split)
        dev_df = slice_dev_df(df, split)

        expected_test = list(range(len(test_df)))
        expected_dev = list(range(len(dev_df)))

        assert list(test_df.index) == expected_test, (
            f"Window {split.window_index}: test_df does not have a clean RangeIndex."
        )
        assert list(dev_df.index) == expected_dev, (
            f"Window {split.window_index}: dev_df does not have a clean RangeIndex."
        )


# ---------------------------------------------------------------------------
# 6. test_walk_forward_returns_list_of_windows
# ---------------------------------------------------------------------------

def test_walk_forward_returns_list_of_windows():
    """
    run_walk_forward must return a WalkForwardSummary with at least
    one window for a dataset large enough to generate windows.
    """
    df = _make_feature_df(500, start_date="2010-01-04")
    summary = run_walk_forward(
        df=df, symbol="TEST",
        config=NO_COST_CONFIG,
        initial_dev_years=1, step_months=3, test_months=3,
    )
    assert isinstance(summary, WalkForwardSummary)
    assert summary.total_windows >= 1, "Expected at least one walk-forward window."
    assert len(summary.windows) == summary.total_windows


# ---------------------------------------------------------------------------
# 7. test_walk_forward_each_window_has_metrics
# ---------------------------------------------------------------------------

def test_walk_forward_each_window_has_metrics():
    """
    Every window in the WalkForwardSummary must have the required fields.
    """
    df = _make_feature_df(500, start_date="2010-01-04")
    summary = run_walk_forward(
        df=df, symbol="TEST",
        config=NO_COST_CONFIG,
        initial_dev_years=1, step_months=3, test_months=3,
    )
    required_fields = [
        "window_index", "symbol", "dev_start", "dev_end", "dev_rows",
        "test_start", "test_end", "test_rows", "num_trades",
        "total_return_pct", "max_drawdown_pct", "final_equity",
        "bh_total_return_pct", "bh_final_equity", "excess_return_pct", "status",
    ]
    for w in summary.windows:
        for field in required_fields:
            assert hasattr(w, field), (
                f"Window {w.window_index} is missing field {field!r}."
            )


# ---------------------------------------------------------------------------
# 8. test_walk_forward_deterministic
# ---------------------------------------------------------------------------

def test_walk_forward_deterministic():
    """
    Running walk-forward twice on the same DataFrame must produce
    bit-identical results.
    """
    df = _make_feature_df(400, start_date="2011-01-03")
    kwargs = dict(
        df=df, symbol="TEST", config=NO_COST_CONFIG,
        initial_dev_years=1, step_months=3, test_months=3,
    )
    summary_a = run_walk_forward(**kwargs)
    summary_b = run_walk_forward(**kwargs)

    assert summary_a.total_windows == summary_b.total_windows

    for wa, wb in zip(summary_a.windows, summary_b.windows):
        assert wa.num_trades == wb.num_trades
        assert wa.total_return_pct == wb.total_return_pct
        assert wa.max_drawdown_pct == wb.max_drawdown_pct
        assert wa.final_equity == wb.final_equity


# ---------------------------------------------------------------------------
# 9. test_buy_hold_result_matches_manual
# ---------------------------------------------------------------------------

def test_buy_hold_result_matches_manual():
    """
    run_buy_hold must match a manually computed buy-and-hold return
    when costs are zero.
    """
    df = pd.DataFrame({
        "date": ["2020-01-01", "2020-01-02", "2020-01-03"],
        "open":  [100.0, 105.0, 110.0],
        "close": [104.0, 109.0, 115.0],
    })
    result = run_buy_hold(df, initial_capital=10_000.0, cost_model=NO_COST)

    # Manual:
    # entry = open of first row = 100.0 (no slippage)
    # exit  = close of last row = 115.0 (no slippage)
    # qty   = floor(10_000 / 100) = 100
    # pnl   = (115 - 100) * 100 = 1500
    assert result["quantity"] == 100
    assert result["entry_price"] == pytest.approx(100.0)
    assert result["exit_price"] == pytest.approx(115.0)
    assert result["total_net_pnl"] == pytest.approx(1500.0, abs=0.01)
    assert result["total_return_pct"] == pytest.approx(15.0, abs=0.01)
    assert result["final_equity"] == pytest.approx(11_500.0, abs=0.01)


# ---------------------------------------------------------------------------
# 10. test_buy_hold_costs_applied
# ---------------------------------------------------------------------------

def test_buy_hold_costs_applied():
    """
    Slippage and commission must reduce the buy-and-hold return
    compared to the no-cost baseline.
    """
    df = pd.DataFrame({
        "date": ["2020-01-01", "2020-01-02", "2020-01-03"],
        "open":  [100.0, 105.0, 110.0],
        "close": [104.0, 109.0, 120.0],
    })
    no_cost_result = run_buy_hold(df, initial_capital=10_000.0, cost_model=NO_COST)
    with_cost_result = run_buy_hold(
        df, initial_capital=10_000.0,
        cost_model=CostModel(commission_rate=0.0005, slippage_rate=0.0005),
    )

    assert with_cost_result["total_return_pct"] < no_cost_result["total_return_pct"], (
        "Buy-and-hold with costs must produce a lower return than no-cost."
    )
    assert with_cost_result["transaction_cost"] > 0.0


# ---------------------------------------------------------------------------
# 11. test_buy_hold_insufficient_data
# ---------------------------------------------------------------------------

def test_buy_hold_insufficient_data():
    """
    run_buy_hold with fewer than 2 rows must return a zeroed result dict.
    """
    df = pd.DataFrame({
        "date": ["2020-01-01"],
        "open": [100.0],
        "close": [105.0],
    })
    result = run_buy_hold(df, initial_capital=10_000.0, cost_model=NO_COST)
    assert result["quantity"] == 0
    assert result["total_net_pnl"] == 0.0
    assert result["total_return_pct"] == 0.0
    assert result["final_equity"] == pytest.approx(10_000.0)


# ---------------------------------------------------------------------------
# 12. test_sensitivity_baseline_included
# ---------------------------------------------------------------------------

def test_sensitivity_baseline_included():
    """
    run_sensitivity must return at least one result with is_baseline=True
    for each parameter being varied.
    """
    df = _make_feature_df(300, start_date="2012-01-02")
    results = run_sensitivity(df=df, symbol="TEST")
    baseline_results = [r for r in results if r.is_baseline]
    assert len(baseline_results) >= 1, (
        "Expected at least one baseline entry in sensitivity results."
    )
    # Verify baselines cover the documented params.
    baseline_params = {r.param_name for r in baseline_results}
    for expected_param in ("risk_per_trade", "atr_multiplier", "commission_rate"):
        assert expected_param in baseline_params, (
            f"No baseline found for parameter {expected_param!r}."
        )


# ---------------------------------------------------------------------------
# 13. test_sensitivity_no_extra_configs
# ---------------------------------------------------------------------------

def test_sensitivity_no_extra_configs():
    """
    run_sensitivity must test exactly the configurations in SENSITIVITY_GRID
    and no others.
    """
    df = _make_feature_df(300, start_date="2012-01-02")
    results = run_sensitivity(df=df, symbol="TEST")
    assert len(results) == len(SENSITIVITY_GRID), (
        f"Expected {len(SENSITIVITY_GRID)} sensitivity results, got {len(results)}."
    )
    for result, (param_name, param_value, is_baseline) in zip(results, SENSITIVITY_GRID):
        assert result.param_name == param_name
        assert result.param_value == pytest.approx(param_value)
        assert result.is_baseline == is_baseline


# ---------------------------------------------------------------------------
# 14. test_gate_overlap_detection
# ---------------------------------------------------------------------------

def test_gate_overlap_detection():
    """
    run_integrity_gates must raise ValidationIntegrityError when a window
    has dev_end >= test_start (overlap).
    """
    overlapping_window = WalkForwardWindow(
        window_index=0, symbol="TEST",
        dev_start="2010-01-01", dev_end="2011-06-30", dev_rows=375,
        test_start="2011-06-30",   # same date as dev_end → overlap
        test_end="2011-12-31", test_rows=130,
        num_trades=3, total_return_pct=1.0,
        win_rate=0.5, profit_factor=1.2, max_drawdown_pct=-5.0,
        final_equity=101_000.0, bh_total_return_pct=2.0,
        bh_final_equity=102_000.0, excess_return_pct=-1.0,
        status="OK",
    )
    summary = WalkForwardSummary(
        symbol="TEST", total_windows=1, ok_windows=1,
        zero_trade_windows=0, insufficient_data_windows=0,
        windows=[overlapping_window],
    )
    with pytest.raises(ValidationIntegrityError, match="NO_OVERLAP"):
        run_integrity_gates(summary=summary, sensitivity_results=[])


# ---------------------------------------------------------------------------
# 15. test_gate_chronological_detection
# ---------------------------------------------------------------------------

def test_gate_chronological_detection():
    """
    run_integrity_gates must raise ValidationIntegrityError when windows
    are not in chronological order (test_start of window N <= window N-1).
    """
    def _w(idx, ts, te):
        return WalkForwardWindow(
            window_index=idx, symbol="TEST",
            dev_start="2010-01-01", dev_end="2010-12-31", dev_rows=250,
            test_start=ts, test_end=te, test_rows=126,
            num_trades=0, total_return_pct=0.0,
            win_rate=None, profit_factor=None, max_drawdown_pct=0.0,
            final_equity=100_000.0, bh_total_return_pct=0.0,
            bh_final_equity=100_000.0, excess_return_pct=0.0,
            status="ZERO_TRADES",
        )

    summary = WalkForwardSummary(
        symbol="TEST", total_windows=2, ok_windows=0,
        zero_trade_windows=2, insufficient_data_windows=0,
        windows=[
            _w(0, "2011-07-01", "2011-12-31"),
            _w(1, "2011-01-01", "2011-06-30"),   # earlier than window 0 → wrong order
        ],
    )
    with pytest.raises(ValidationIntegrityError, match="CHRONOLOGICAL"):
        run_integrity_gates(summary=summary, sensitivity_results=[])


# ---------------------------------------------------------------------------
# 16. test_gate_symbol_isolation
# ---------------------------------------------------------------------------

def test_gate_symbol_isolation():
    """
    run_integrity_gates must raise ValidationIntegrityError when a window's
    symbol does not match the summary's symbol.
    """
    w = WalkForwardWindow(
        window_index=0, symbol="RELIANCE",   # wrong symbol
        dev_start="2010-01-01", dev_end="2010-12-31", dev_rows=250,
        test_start="2011-01-01", test_end="2011-06-30", test_rows=126,
        num_trades=0, total_return_pct=0.0,
        win_rate=None, profit_factor=None, max_drawdown_pct=0.0,
        final_equity=100_000.0, bh_total_return_pct=0.0,
        bh_final_equity=100_000.0, excess_return_pct=0.0,
        status="ZERO_TRADES",
    )
    summary = WalkForwardSummary(
        symbol="ITC", total_windows=1, ok_windows=0,
        zero_trade_windows=1, insufficient_data_windows=0,
        windows=[w],
    )
    with pytest.raises(ValidationIntegrityError, match="SYMBOL_ISOLATION"):
        run_integrity_gates(summary=summary, sensitivity_results=[])


# ---------------------------------------------------------------------------
# 17. test_gate_determinism
# ---------------------------------------------------------------------------

def test_gate_determinism():
    """
    Running the same valid summary through run_integrity_gates twice
    must produce no exception (gates are deterministic).
    """
    df = _make_feature_df(400, start_date="2011-01-03")
    summary = run_walk_forward(
        df=df, symbol="TEST", config=NO_COST_CONFIG,
        initial_dev_years=1, step_months=3, test_months=3,
    )
    sensitivity_results = run_sensitivity(df=df, symbol="TEST")

    # Must not raise.
    run_integrity_gates(summary=summary, sensitivity_results=sensitivity_results)
    run_integrity_gates(summary=summary, sensitivity_results=sensitivity_results)


# ---------------------------------------------------------------------------
# 18. test_truncation_invariance  (CORRECTION 3 — MANDATORY)
# ---------------------------------------------------------------------------

def test_truncation_invariance():
    """
    CORRECTION 3 — Truncation-invariance formal test.

    Verifies that:
        features(full_dataset).at[T] == features(data_through_T).at[T]

    For a set of sampled timestamps T, recomputing features on the slice
    [0..T] must produce the same feature values at row T as the full-dataset
    computation.

    Indicators tested: ema20, ema50, atr14, avg_volume_20, volume_ratio,
                       momentum_5, momentum_20, signal
    """
    from quant.features.indicators import compute_all_features
    from quant.strategies.trend_momentum import apply_strategy

    # Build a raw OHLCV frame (no pre-computed features).
    n = 150
    raw_df = _make_ohlcv(n, start_date="2015-01-05")

    # Compute features on the FULL dataset.
    full_features = apply_strategy(compute_all_features(raw_df))

    # Sample three timestamps: first valid row (idx 21), mid-dataset, last row.
    sample_indices = [21, n // 2, n - 1]

    for T in sample_indices:
        # Slice raw data to rows [0..T] (data available only through T).
        slice_df = raw_df.iloc[: T + 1].reset_index(drop=True)

        # Recompute features on the slice.
        slice_features = apply_strategy(compute_all_features(slice_df))

        # Last row of slice must match row T of full computation.
        slice_last = slice_features.iloc[-1]
        full_at_T = full_features.iloc[T]

        indicators_to_check = [
            "ema20", "ema50", "atr14", "avg_volume_20",
            "volume_ratio", "momentum_5", "momentum_20",
        ]
        for col in indicators_to_check:
            val_slice = slice_last[col]
            val_full = full_at_T[col]
            # Handle NaN equality.
            if pd.isna(val_slice) and pd.isna(val_full):
                continue
            assert val_slice == pytest.approx(val_full, rel=1e-9), (
                f"Truncation-invariance violated at T={T}, column={col!r}: "
                f"slice value {val_slice!r} != full value {val_full!r}. "
                "Future rows must not alter past feature values."
            )

        # Signal column.
        assert slice_last["signal"] == full_at_T["signal"], (
            f"Truncation-invariance violated at T={T}, column='signal': "
            f"{slice_last['signal']!r} != {full_at_T['signal']!r}."
        )


# ---------------------------------------------------------------------------
# 19. test_future_rows_cannot_alter_past_features  (CORRECTION 3 — MANDATORY)
# ---------------------------------------------------------------------------

def test_future_rows_cannot_alter_past_features():
    """
    CORRECTION 3 — Future-row isolation test.

    Appending synthetic future rows (with extreme prices designed to trigger
    all conditions) after timestamp T must leave all feature and signal
    values at row T completely unchanged.

    This empirically proves that the causal indicator formulas do not
    reach backward into past values.
    """
    from quant.features.indicators import compute_all_features
    from quant.strategies.trend_momentum import apply_strategy

    n = 80
    raw_df = _make_ohlcv(n, start_date="2016-03-01")

    # Compute features on the base dataset.
    base_features = apply_strategy(compute_all_features(raw_df))

    # Append 20 synthetic future rows with extreme prices.
    # If any indicator looks forward, these will alter past values.
    extra_dates = pd.bdate_range(
        start=pd.Timestamp(raw_df["date"].iloc[-1]) + pd.Timedelta(days=1),
        periods=20,
    )
    extreme_close = 100_000.0  # far above baseline prices
    extra = pd.DataFrame({
        "date": extra_dates.strftime("%Y-%m-%d"),
        "symbol": "TEST",
        "open": extreme_close * 0.99,
        "high": extreme_close * 1.01,
        "low": extreme_close * 0.98,
        "close": [extreme_close] * 20,
        "volume": [1.0] * 20,        # near-zero volume to suppress volume signals
    })
    extended_df = pd.concat([raw_df, extra], ignore_index=True)

    # Recompute features on the extended dataset.
    extended_features = apply_strategy(compute_all_features(extended_df))

    # Check that ALL rows in the original base dataset are unchanged.
    indicators = [
        "ema20", "ema50", "atr14", "avg_volume_20",
        "volume_ratio", "momentum_5", "momentum_20",
    ]
    for i in range(n):
        base_row = base_features.iloc[i]
        ext_row = extended_features.iloc[i]

        for col in indicators:
            b = base_row[col]
            e = ext_row[col]
            if pd.isna(b) and pd.isna(e):
                continue
            assert b == pytest.approx(e, rel=1e-9), (
                f"Future rows altered feature {col!r} at row {i}: "
                f"base={b!r}, extended={e!r}. "
                "Indicators must be strictly causal (no forward leakage)."
            )

        assert base_row["signal"] == ext_row["signal"], (
            f"Future rows altered signal at row {i}: "
            f"base={base_row['signal']!r}, extended={ext_row['signal']!r}."
        )


# ---------------------------------------------------------------------------
# 20. test_itc_full_dataset_regression  (INTEGRATION — requires real ITC data)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_itc_full_dataset_regression():
    """
    INTEGRATION: The full ITC backtest must reproduce the verified baseline
    exactly. This is the ITC regression lock for Sprint 6.

    Baseline (verified):
        Final equity:   ₹91,464.71
        Trades:         70
        Return:         -8.54%
        Win rate:       32.9%
        Profit factor:  0.777
        Max drawdown:   -25.14%
    """
    if not ITC_FEATURES_CSV.exists():
        pytest.skip(f"ITC features CSV not found: {ITC_FEATURES_CSV}")

    from quant.backtest.engine import backtest_from_csv, BacktestConfig
    from quant.backtest.metrics import compute_metrics

    result = backtest_from_csv(str(ITC_FEATURES_CSV))
    metrics = compute_metrics(result)

    assert metrics["final_equity"] == pytest.approx(91_464.71, abs=0.01), (
        f"ITC regression: final_equity={metrics['final_equity']:.2f}, "
        "expected ₹91,464.71"
    )
    assert metrics["num_trades"] == 70, (
        f"ITC regression: num_trades={metrics['num_trades']}, expected 70"
    )
    assert metrics["total_return_pct"] == pytest.approx(-8.54, abs=0.01), (
        f"ITC regression: total_return_pct={metrics['total_return_pct']:.2f}%, "
        "expected -8.54%"
    )
    assert metrics["win_rate"] == pytest.approx(0.329, abs=0.001), (
        f"ITC regression: win_rate={metrics['win_rate']:.4f}, expected 0.329"
    )
    assert metrics["profit_factor"] == pytest.approx(0.777, abs=0.001), (
        f"ITC regression: profit_factor={metrics['profit_factor']:.4f}, expected 0.777"
    )
    assert metrics["max_drawdown_pct"] == pytest.approx(-25.14, abs=0.01), (
        f"ITC regression: max_drawdown_pct={metrics['max_drawdown_pct']:.2f}%, "
        "expected -25.14%"
    )


# ---------------------------------------------------------------------------
# 21. test_cli_runs_without_error  (INTEGRATION — requires real ITC data)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_cli_runs_without_error(tmp_path, monkeypatch):
    """
    INTEGRATION: `python -m quant.validation --symbol ITC` must exit with
    code 0 and produce the expected output files.
    """
    if not ITC_FEATURES_CSV.exists():
        pytest.skip(f"ITC features CSV not found: {ITC_FEATURES_CSV}")

    # Redirect output directories to tmp_path to avoid polluting the repo.
    from quant.validation import report as report_module

    orig_val_dir = report_module.VALIDATION_DIR
    orig_docs_dir = report_module.DOCS_DIR
    report_module.VALIDATION_DIR = tmp_path / "validation"
    report_module.DOCS_DIR = tmp_path / "docs"

    try:
        from quant.validation.__main__ import main
        exit_code = main(["--symbol", "ITC"])
    finally:
        report_module.VALIDATION_DIR = orig_val_dir
        report_module.DOCS_DIR = orig_docs_dir

    assert exit_code == 0, "CLI exited with non-zero code."

    # Verify output files were created.
    val_dir = tmp_path / "validation"
    assert (val_dir / "ITC_splits.json").exists(), "ITC_splits.json not written."
    assert (val_dir / "ITC_walkforward.json").exists(), "ITC_walkforward.json not written."
    assert (val_dir / "ITC_sensitivity.json").exists(), "ITC_sensitivity.json not written."
    assert (val_dir / "ITC_summary.json").exists(), "ITC_summary.json not written."
    assert (tmp_path / "docs" / "sprint-6-validation.md").exists(), (
        "sprint-6-validation.md not written."
    )

    # Verify walkforward JSON has at least one window.
    with open(val_dir / "ITC_walkforward.json", encoding="utf-8") as f:
        wf_data = json.load(f)
    assert wf_data["total_windows"] >= 1, "Walk-forward produced no windows."

    # Verify sensitivity JSON has 11 entries.
    with open(val_dir / "ITC_sensitivity.json", encoding="utf-8") as f:
        sens_data = json.load(f)
    assert len(sens_data) == 11, f"Expected 11 sensitivity entries, got {len(sens_data)}."
