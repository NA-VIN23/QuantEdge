"""
quant/validation/benchmark.py
------------------------------
Buy-and-hold benchmark for Sprint 6 validation.

Computes a simple passive buy-and-hold return over a given period
using the same transaction cost model as the strategy backtest.

==============================================================
BUY-AND-HOLD DEFINITION
==============================================================

Entry:  Buy at the open price of the first row (+ slippage).
Exit:   Sell at the close price of the last row (- slippage).
Shares: floor(initial_capital / effective_entry_price).
Costs:  Same DEFAULT_COST_MODEL (commission applied on both legs).

This represents the simplest honest passive alternative:
"What if you had just bought and held for the entire period?"

The comparison is always:
  - Same evaluation period
  - Same initial capital
  - Same transaction cost model
  - No optimization or look-ahead
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from quant.backtest.costs import CostModel, DEFAULT_COST_MODEL


def run_buy_hold(
    df: pd.DataFrame,
    initial_capital: float = 100_000.0,
    cost_model: Optional[CostModel] = None,
) -> dict:
    """
    Compute buy-and-hold return over the given price DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Chronologically ordered DataFrame. Must contain columns:
        'date', 'open', 'close'.
    initial_capital : float
        Starting capital in INR.
    cost_model : CostModel, optional
        Transaction cost model. Uses DEFAULT_COST_MODEL if None.

    Returns
    -------
    dict with keys:
        start_date              : str
        end_date                : str
        entry_reference_price   : float   (open of first row, pre-slippage)
        exit_reference_price    : float   (close of last row, pre-slippage)
        entry_price             : float   (effective, post-slippage)
        exit_price              : float   (effective, post-slippage)
        quantity                : int
        initial_capital         : float
        final_equity            : float
        total_net_pnl           : float
        total_return_pct        : float
        transaction_cost        : float
        num_trading_days        : int

    Notes
    -----
    Returns a zeroed result dict if df has fewer than 2 rows (no valid
    holding period).
    """
    if cost_model is None:
        cost_model = DEFAULT_COST_MODEL

    if df is None or len(df) < 2:
        return _empty_result(initial_capital)

    df_sorted = df.sort_values("date").reset_index(drop=True)

    ref_entry = float(df_sorted.iloc[0]["open"])
    ref_exit = float(df_sorted.iloc[-1]["close"])

    eff_entry = cost_model.effective_entry_price(ref_entry)
    eff_exit = cost_model.effective_exit_price(ref_exit)

    quantity = int(math.floor(initial_capital / eff_entry)) if eff_entry > 0 else 0

    if quantity <= 0:
        return _empty_result(initial_capital)

    entry_commission = cost_model.entry_commission(eff_entry, quantity)
    exit_commission = cost_model.exit_commission(eff_exit, quantity)
    transaction_cost = entry_commission + exit_commission

    gross_pnl = (eff_exit - eff_entry) * quantity
    net_pnl = gross_pnl - transaction_cost
    final_equity = initial_capital + net_pnl
    total_return_pct = (net_pnl / initial_capital * 100.0) if initial_capital != 0 else 0.0

    return {
        "start_date": str(df_sorted.iloc[0]["date"]),
        "end_date": str(df_sorted.iloc[-1]["date"]),
        "entry_reference_price": round(ref_entry, 4),
        "exit_reference_price": round(ref_exit, 4),
        "entry_price": round(eff_entry, 4),
        "exit_price": round(eff_exit, 4),
        "quantity": quantity,
        "initial_capital": round(initial_capital, 4),
        "final_equity": round(final_equity, 4),
        "total_net_pnl": round(net_pnl, 4),
        "total_return_pct": round(total_return_pct, 4),
        "transaction_cost": round(transaction_cost, 4),
        "num_trading_days": len(df_sorted),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _empty_result(initial_capital: float) -> dict:
    """Return a zeroed benchmark result when data is insufficient."""
    return {
        "start_date": "",
        "end_date": "",
        "entry_reference_price": 0.0,
        "exit_reference_price": 0.0,
        "entry_price": 0.0,
        "exit_price": 0.0,
        "quantity": 0,
        "initial_capital": round(initial_capital, 4),
        "final_equity": round(initial_capital, 4),
        "total_net_pnl": 0.0,
        "total_return_pct": 0.0,
        "transaction_cost": 0.0,
        "num_trading_days": 0,
    }
