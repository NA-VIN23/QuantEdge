"""
quant/backtest/metrics.py
--------------------------
Performance metrics calculator for QuantEdge Sprint 3.

Responsibility:
  - Accept the BacktestResult produced by engine.run_backtest.
  - Calculate a comprehensive set of performance metrics.
  - Return a structured dict (suitable for JSON serialisation).

Metrics:
  - initial_capital, final_equity, total_net_pnl, total_return_pct
  - num_trades, num_wins, num_losses, win_rate
  - avg_net_pnl, avg_win_pnl, avg_loss_pnl
  - profit_factor (null if no losses)
  - max_drawdown_pct (from daily equity curve)
  - avg_holding_days
  - exposure_pct (fraction of days with open position)
  - best_trade_net_pnl, worst_trade_net_pnl
  - num_signals_total, num_signals_executed, num_signals_skipped

==============================================================
NOTES
==============================================================

profit_factor = sum(gross winning P&L) / abs(sum(gross losing P&L))
  - If no losing trades: returned as None (not infinity).
  - Uses NET P&L, not gross, to reflect actual returns after costs.

max_drawdown_pct:
  - Based on the daily equity curve.
  - running_peak = cumulative max of equity.
  - daily_dd = (equity - running_peak) / running_peak.
  - max_drawdown = min(daily_dd) — expressed as a negative fraction.
  - Reported as a percentage (multiplied by 100).
  - If equity never declines: 0.0%.

exposure_pct:
  - Days where position_quantity > 0 / total days.
"""

from __future__ import annotations

from typing import Any, Optional

from quant.backtest.engine import BacktestResult, TradeRecord, EquityRow


def compute_metrics(result: BacktestResult) -> dict[str, Any]:
    """
    Compute all performance metrics from a BacktestResult.

    Parameters
    ----------
    result : BacktestResult
        Output of run_backtest().

    Returns
    -------
    dict
        All metrics as a flat dictionary. None values indicate mathematically
        undefined metrics (e.g. profit_factor with no losses).
    """
    trades = result.trades
    curve = result.equity_curve
    initial = result.initial_capital

    # ----------------------------------------------------------------
    # Basic counts
    # ----------------------------------------------------------------
    num_trades = len(trades)
    num_signals_total = num_trades + len(result.skipped_signals)
    num_signals_skipped = len(result.skipped_signals)

    final_equity = curve[-1].equity if curve else initial
    total_net_pnl = final_equity - initial
    total_return_pct = (total_net_pnl / initial * 100.0) if initial != 0 else 0.0

    # ----------------------------------------------------------------
    # Win / loss split
    # ----------------------------------------------------------------
    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    num_wins = len(wins)
    num_losses = len(losses)
    win_rate = num_wins / num_trades if num_trades > 0 else None

    # ----------------------------------------------------------------
    # Average P&L
    # ----------------------------------------------------------------
    avg_net_pnl = _mean([t.net_pnl for t in trades])
    avg_win_pnl = _mean([t.net_pnl for t in wins])
    avg_loss_pnl = _mean([t.net_pnl for t in losses])

    # ----------------------------------------------------------------
    # Profit factor
    # ----------------------------------------------------------------
    gross_profits = sum(t.net_pnl for t in wins)
    gross_losses = sum(t.net_pnl for t in losses)   # negative or zero

    if num_losses == 0:
        profit_factor: Optional[float] = None   # no losses → undefined
    elif gross_losses == 0.0:
        profit_factor = None
    else:
        profit_factor = gross_profits / abs(gross_losses)

    # ----------------------------------------------------------------
    # Maximum drawdown
    # ----------------------------------------------------------------
    max_drawdown_pct = _compute_max_drawdown(curve)

    # ----------------------------------------------------------------
    # Holding period
    # ----------------------------------------------------------------
    avg_holding_days = _mean([t.holding_days for t in trades])

    # ----------------------------------------------------------------
    # Exposure
    # ----------------------------------------------------------------
    total_days = len(curve)
    days_in_position = sum(1 for r in curve if r.position_quantity > 0)
    exposure_pct = (days_in_position / total_days * 100.0) if total_days > 0 else 0.0

    # ----------------------------------------------------------------
    # Best / worst trade
    # ----------------------------------------------------------------
    best_trade_net_pnl = max((t.net_pnl for t in trades), default=None)
    worst_trade_net_pnl = min((t.net_pnl for t in trades), default=None)

    # ----------------------------------------------------------------
    # Exit reason distribution
    # ----------------------------------------------------------------
    exit_reasons: dict[str, int] = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    # ----------------------------------------------------------------
    # Skip reason distribution
    # ----------------------------------------------------------------
    skip_reasons: dict[str, int] = {}
    for s in result.skipped_signals:
        skip_reasons[s.reason] = skip_reasons.get(s.reason, 0) + 1

    return {
        # Capital
        "initial_capital": round(initial, 4),
        "final_equity": round(final_equity, 4),
        "total_net_pnl": round(total_net_pnl, 4),
        "total_return_pct": round(total_return_pct, 4),

        # Trade counts
        "num_signals_total": num_signals_total,
        "num_signals_executed": num_trades,
        "num_signals_skipped": num_signals_skipped,
        "num_trades": num_trades,
        "num_wins": num_wins,
        "num_losses": num_losses,
        "win_rate": round(win_rate, 4) if win_rate is not None else None,

        # P&L
        "avg_net_pnl": _rnd(avg_net_pnl),
        "avg_win_pnl": _rnd(avg_win_pnl),
        "avg_loss_pnl": _rnd(avg_loss_pnl),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,

        # Risk
        "max_drawdown_pct": round(max_drawdown_pct, 4),

        # Duration
        "avg_holding_days": _rnd(avg_holding_days),

        # Exposure
        "exposure_pct": round(exposure_pct, 4),

        # Extremes
        "best_trade_net_pnl": _rnd(best_trade_net_pnl),
        "worst_trade_net_pnl": _rnd(worst_trade_net_pnl),

        # Distributions (for audit)
        "exit_reason_counts": exit_reasons,
        "skip_reason_counts": skip_reasons,

        # Config used
        "backtest_config": result.config,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> Optional[float]:
    """Return the mean of a list, or None if the list is empty."""
    if not values:
        return None
    return sum(values) / len(values)


def _rnd(value: Optional[float], ndigits: int = 4) -> Optional[float]:
    """Round a value if not None."""
    return round(value, ndigits) if value is not None else None


def _compute_max_drawdown(curve: list[EquityRow]) -> float:
    """
    Compute maximum drawdown percentage from the daily equity curve.

    Formula:
        running_peak = cumulative maximum equity up to each day
        daily_dd     = (equity - running_peak) / running_peak
        max_drawdown = min(daily_dd)   [most negative value]

    Returns a percentage (e.g. -15.3 means 15.3% drawdown).
    Returns 0.0 if the curve is empty or equity never declines.
    """
    if not curve:
        return 0.0

    peak = curve[0].equity
    max_dd = 0.0

    for row in curve:
        if row.equity > peak:
            peak = row.equity
        if peak != 0:
            dd = (row.equity - peak) / peak
            if dd < max_dd:
                max_dd = dd

    return round(max_dd * 100.0, 6)  # as percentage, negative
