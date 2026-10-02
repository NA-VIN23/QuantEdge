"""
quant/validation/walk_forward.py
---------------------------------
Walk-forward evaluation engine for Sprint 6.

For each (development_window, unseen_test_window) pair produced by
splitter.chronological_splits(), this module:

  1. Slices the pre-computed feature DataFrame to the unseen test window.
  2. Runs the EXISTING deterministic backtest engine on the test slice.
  3. Computes performance metrics using the EXISTING metrics module.
  4. Runs the buy-and-hold benchmark for the same test period.
  5. Records a WalkForwardWindow result.

==============================================================
CRITICAL DESIGN CONSTRAINTS
==============================================================

- The strategy rules and ALL parameters are FIXED.
- Nothing is trained, fitted, or optimized in this module.
- The development window is passed to NO function that modifies
  any parameter. It is recorded in metadata only (date range,
  row count).
- Only the UNSEEN TEST slice is passed to run_backtest().
- Features are read from the pre-computed features CSV; they are
  NOT recomputed per window.

==============================================================
ZERO-TRADE WINDOWS
==============================================================

Many 6-month test windows will produce 0 trades (ITC has a signal
rate of ~2.74%). This is not an error. Such windows are labelled
"ZERO_TRADES" in the status field and are included in all output
files. They are excluded only from aggregate win-rate / profit-factor
calculations where a denominator of zero would be undefined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from quant.backtest.costs import CostModel
from quant.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from quant.backtest.metrics import compute_metrics
from quant.validation.benchmark import run_buy_hold
from quant.validation.splitter import (
    DataSplit,
    chronological_splits,
    slice_test_df,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardWindow:
    """Results for one walk-forward unseen test window."""

    window_index: int
    symbol: str

    # Date ranges
    dev_start: str
    dev_end: str
    dev_rows: int
    test_start: str
    test_end: str
    test_rows: int

    # Strategy backtest metrics for the unseen test period
    num_trades: int
    total_return_pct: float
    win_rate: Optional[float]      # None if no trades
    profit_factor: Optional[float] # None if no losses
    max_drawdown_pct: float
    final_equity: float

    # Buy-and-hold benchmark (same period, same initial capital, same costs)
    bh_total_return_pct: float
    bh_final_equity: float

    # Excess return: strategy - buy-and-hold
    excess_return_pct: float

    # Window status
    status: str = "OK"  # OK | ZERO_TRADES | INSUFFICIENT_DATA


@dataclass
class WalkForwardSummary:
    """Aggregate summary across all walk-forward windows."""

    symbol: str
    total_windows: int
    ok_windows: int
    zero_trade_windows: int
    insufficient_data_windows: int
    windows: list[WalkForwardWindow] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_walk_forward(
    df: pd.DataFrame,
    symbol: str = "ITC",
    config: Optional[BacktestConfig] = None,
    initial_dev_years: int = 3,
    step_months: int = 6,
    test_months: int = 6,
    min_test_rows: int = 50,
) -> WalkForwardSummary:
    """
    Run the full walk-forward validation for a single symbol.

    Parameters
    ----------
    df : pd.DataFrame
        Full feature-enriched DataFrame for the symbol. Must be sorted
        chronologically ascending and contain all required backtest columns.
    symbol : str
        NSE symbol name.
    config : BacktestConfig, optional
        Backtest engine configuration. Uses defaults (fixed parameters) if
        None. No parameter fitting occurs regardless.
    initial_dev_years : int
        Minimum years of development data before the first unseen window.
    step_months : int
        Forward step between successive windows (months).
    test_months : int
        Duration of each unseen test window (months).
    min_test_rows : int
        Minimum rows for a test window to be labelled "OK".

    Returns
    -------
    WalkForwardSummary
        All walk-forward window results plus aggregate counts.
        The actual number of windows is determined by the available data
        and the window configuration — not a fixed target.
    """
    if config is None:
        config = BacktestConfig(symbol=symbol)

    cost_model: CostModel = config.cost_model

    # --- Generate chronological splits ---
    splits: list[DataSplit] = chronological_splits(
        df=df,
        symbol=symbol,
        initial_dev_years=initial_dev_years,
        step_months=step_months,
        test_months=test_months,
        min_test_rows=min_test_rows,
    )

    windows: list[WalkForwardWindow] = []
    ok_count = 0
    zero_trade_count = 0
    insuff_count = 0

    for split in splits:
        # --- INSUFFICIENT_DATA: record but skip backtest ---
        if split.status == "INSUFFICIENT_DATA":
            insuff_count += 1
            windows.append(WalkForwardWindow(
                window_index=split.window_index,
                symbol=symbol,
                dev_start=split.dev_start,
                dev_end=split.dev_end,
                dev_rows=split.dev_rows,
                test_start=split.test_start,
                test_end=split.test_end,
                test_rows=split.test_rows,
                num_trades=0,
                total_return_pct=0.0,
                win_rate=None,
                profit_factor=None,
                max_drawdown_pct=0.0,
                final_equity=config.initial_capital,
                bh_total_return_pct=0.0,
                bh_final_equity=config.initial_capital,
                excess_return_pct=0.0,
                status="INSUFFICIENT_DATA",
            ))
            continue

        # --- Slice the unseen test window (development slice NOT used by engine) ---
        test_df = slice_test_df(df, split)

        # --- Run existing backtest engine on the test slice ONLY ---
        result: BacktestResult = run_backtest(test_df, config)
        metrics = compute_metrics(result)

        # --- Buy-and-hold benchmark for the same test period ---
        bh = run_buy_hold(
            df=test_df,
            initial_capital=config.initial_capital,
            cost_model=cost_model,
        )

        num_trades = metrics["num_trades"]
        total_return = metrics["total_return_pct"]
        bh_return = bh["total_return_pct"]

        status = "ZERO_TRADES" if num_trades == 0 else "OK"
        if status == "OK":
            ok_count += 1
        else:
            zero_trade_count += 1

        windows.append(WalkForwardWindow(
            window_index=split.window_index,
            symbol=symbol,
            dev_start=split.dev_start,
            dev_end=split.dev_end,
            dev_rows=split.dev_rows,
            test_start=split.test_start,
            test_end=split.test_end,
            test_rows=split.test_rows,
            num_trades=num_trades,
            total_return_pct=round(total_return, 4),
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            max_drawdown_pct=round(metrics["max_drawdown_pct"], 4),
            final_equity=round(metrics["final_equity"], 4),
            bh_total_return_pct=round(bh_return, 4),
            bh_final_equity=round(bh["final_equity"], 4),
            excess_return_pct=round(total_return - bh_return, 4),
            status=status,
        ))

    return WalkForwardSummary(
        symbol=symbol,
        total_windows=len(splits),
        ok_windows=ok_count,
        zero_trade_windows=zero_trade_count,
        insufficient_data_windows=insuff_count,
        windows=windows,
    )
