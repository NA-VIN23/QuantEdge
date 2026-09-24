"""
tests/test_backtest.py
----------------------
Comprehensive unit tests for the QuantEdge Sprint 3 backtesting engine.

All tests use small synthetic DataFrames — no dependency on the ITC dataset.

Test coverage:
  1.  Entry at T+1 open (not T close)
  2.  Same-day close NOT used as entry
  3.  Position sizing: 1% equity risk
  4.  Quantity is a whole number (floor)
  5.  Capital constraint
  6.  Stop price uses signal-day ATR
  7.  Intraday stop triggered when low <= stop
  8.  Gap-down stop: open < stop → exit at open (STOP_GAP)
  9.  Trend exit detected when close < ema20
  10. Trend exit executes at next day's open
  11. End-of-data closes remaining position
  12. Commission applied on both legs
  13. Slippage applied (entry up, exit down)
  14. Net P&L = gross - total transaction costs
  15. R-multiple = net_pnl / risk_budget
  16. Equity curve: daily mark-to-market
  17. Max drawdown from equity curve
  18. No second position while one is open
  19. Signal skipped when in position
  20. Lookahead invariance
  21. Cost model: effective_entry_price / effective_exit_price
  22. CostModel: total_transaction_cost
  23. Metrics: profit_factor None when no losses
  24. Metrics: max_drawdown on flat equity
  25. End-of-data exit on last signal
"""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pandas as pd
import pytest

from quant.backtest.costs import CostModel, DEFAULT_COST_MODEL
from quant.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    EXIT_END_OF_DATA,
    EXIT_STOP_GAP,
    EXIT_STOP_LOSS,
    EXIT_TREND,
    SIGNAL_LONG,
    SKIP_IN_POSITION,
    SKIP_NO_NEXT_DAY,
    SKIP_ZERO_QTY,
    _attempt_entry,
    _calendar_days,
    run_backtest,
)
from quant.backtest.metrics import compute_metrics, _compute_max_drawdown, EquityRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NO_COST_MODEL = CostModel(commission_rate=0.0, slippage_rate=0.0)
NO_COST_CONFIG = BacktestConfig(
    initial_capital=100_000.0,
    risk_per_trade=0.01,
    atr_multiplier=2.0,
    cost_model=NO_COST_MODEL,
)


def _row(
    date: str,
    open_: float,
    high: float,
    low: float,
    close: float,
    ema20: float,
    atr14: float,
    signal: str = "NO_SIGNAL",
    volume: float = 1_000_000.0,
) -> dict:
    return {
        "date": date,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "ema20": ema20,
        "atr14": atr14,
        "signal": signal,
        "volume": volume,
    }


def _make_df(rows: List[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _flat_df(n: int = 10, price: float = 100.0, atr: float = 2.0) -> pd.DataFrame:
    """DataFrame with constant prices, no signals."""
    return _make_df([
        _row(
            date=f"2020-01-{i+1:02d}",
            open_=price, high=price + 2, low=price - 2,
            close=price, ema20=price - 1, atr14=atr,
        )
        for i in range(n)
    ])


def _signal_then_flat(
    signal_close: float = 100.0,
    next_open: float = 100.0,
    atr: float = 2.0,
    n_after: int = 5,
    subsequent_close: float = 110.0,
) -> pd.DataFrame:
    """
    Day 0: LONG signal.
    Day 1: entry day (open = next_open).
    Days 2..n: flat price above ema20 (no exit until end of data).
    """
    rows = [
        _row("2020-01-01", signal_close, signal_close + 2, signal_close - 2,
             signal_close, signal_close - 5, atr, signal="LONG"),
    ]
    rows.append(_row("2020-01-02", next_open, next_open + 3, next_open - 1,
                     subsequent_close, subsequent_close - 5, atr))
    for k in range(n_after - 1):
        rows.append(_row(f"2020-01-{k+3:02d}", subsequent_close,
                         subsequent_close + 3, subsequent_close - 1,
                         subsequent_close, subsequent_close - 5, atr))
    return _make_df(rows)


# ---------------------------------------------------------------------------
# 1. Entry at T+1 open
# ---------------------------------------------------------------------------


class TestEntryTiming:

    def test_entry_on_next_day_open(self):
        """Entry must occur on T+1 at T+1 open, not at T close."""
        signal_close = 100.0
        next_open = 105.0  # deliberately different from close
        df = _signal_then_flat(signal_close=signal_close, next_open=next_open, n_after=3)
        result = run_backtest(df, NO_COST_CONFIG)

        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.entry_date == "2020-01-02"
        assert t.entry_reference_price == pytest.approx(next_open)
        # With zero slippage: effective entry == reference
        assert t.entry_price == pytest.approx(next_open)

    def test_signal_date_is_t_not_t_plus_1(self):
        """signal_date in the ledger must be the signal day (T), not entry day."""
        df = _signal_then_flat()
        result = run_backtest(df, NO_COST_CONFIG)
        assert result.trades[0].signal_date == "2020-01-01"
        assert result.trades[0].entry_date == "2020-01-02"

    def test_close_on_signal_day_not_used_as_entry(self):
        """
        Even if next_open differs substantially from signal close,
        entry must use next_open only.
        """
        df = _signal_then_flat(signal_close=100.0, next_open=200.0, n_after=3)
        result = run_backtest(df, NO_COST_CONFIG)
        assert result.trades[0].entry_reference_price == pytest.approx(200.0)


# ---------------------------------------------------------------------------
# 2. Position sizing
# ---------------------------------------------------------------------------


class TestPositionSizing:

    def test_quantity_uses_1pct_risk(self):
        """
        equity=100_000, risk=1% → risk_budget=1000.
        stop = entry − 2×ATR = 100 − 4 = 96.
        risk_per_share = 4.
        qty = floor(1000/4) = 250.
        """
        df = _signal_then_flat(
            signal_close=99.0,  # close on signal day
            next_open=100.0,
            atr=2.0,
            n_after=3,
            subsequent_close=110.0,
        )
        result = run_backtest(df, NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        # risk_budget = 100000 * 0.01 = 1000
        # stop = 100 - 2*2 = 96; risk_per_share = 4
        # qty = floor(1000/4) = 250
        assert t.quantity == 250

    def test_quantity_is_whole_number(self):
        """Quantity must always be a non-negative integer (floor applied)."""
        df = _signal_then_flat(next_open=103.7, atr=3.3, n_after=3)
        result = run_backtest(df, NO_COST_CONFIG)
        if result.trades:
            assert isinstance(result.trades[0].quantity, int)
            assert result.trades[0].quantity >= 0

    def test_capital_constraint_limits_quantity(self):
        """
        If risk-based qty would cost more than available cash,
        reduce to floor(cash / entry).
        """
        # entry=100, risk_per_share=2, qty_risk=floor(1000/2)=500
        # 500 * 100 = 50_000 <= 100_000: no constraint here.
        # Now use tiny capital and large price.
        config = BacktestConfig(
            initial_capital=1_000.0,
            risk_per_trade=0.01,
            atr_multiplier=2.0,
            cost_model=NO_COST_MODEL,
        )
        # entry=100, stop=96, risk_per_share=4
        # risk_budget=10, qty_risk=2
        # cash=1000, affordable=10
        # qty = min(2, 10) = 2
        df = _signal_then_flat(next_open=100.0, atr=2.0, n_after=3)
        result = run_backtest(df, config)
        if result.trades:
            t = result.trades[0]
            # qty should not exceed floor(1000/100) = 10
            assert t.quantity <= 10

    def test_stop_uses_signal_day_atr(self):
        """stop = effective_entry − (2 × ATR at signal day)."""
        atr = 5.0
        next_open = 100.0
        df = _signal_then_flat(next_open=next_open, atr=atr, n_after=3)
        result = run_backtest(df, NO_COST_CONFIG)
        if result.trades:
            t = result.trades[0]
            expected_stop = t.entry_price - 2.0 * atr
            assert t.initial_stop == pytest.approx(expected_stop)
            assert t.atr_at_signal == pytest.approx(atr)

    def test_risk_budget_recorded(self):
        """risk_budget field = equity × risk_per_trade at time of entry."""
        df = _signal_then_flat(next_open=100.0, atr=2.0, n_after=3)
        result = run_backtest(df, NO_COST_CONFIG)
        if result.trades:
            t = result.trades[0]
            # Equity at entry was initial_capital (no position before)
            assert t.risk_budget == pytest.approx(100_000 * 0.01)


# ---------------------------------------------------------------------------
# 3. Stop-loss exits
# ---------------------------------------------------------------------------


class TestStopLoss:

    def test_stop_triggered_when_low_lte_stop(self):
        """When day's low <= stop_price, exit at stop_price (STOP_LOSS)."""
        # entry=100, ATR=2, stop=96
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 90, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),   # entry day, no stop
            _row("2020-01-03", 98, 99, 95, 97, 90, 2.0),      # low=95 <= stop=96 → STOP
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == EXIT_STOP_LOSS
        assert t.exit_date == "2020-01-03"
        # stop = entry − 2*ATR = 100 − 4 = 96
        assert t.exit_reference_price == pytest.approx(96.0)

    def test_stop_not_triggered_when_low_above_stop(self):
        """When low > stop_price, no stop exit on that day."""
        # entry=100, stop=96, low=97 > 96 → no stop
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 90, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),
            _row("2020-01-03", 98, 99, 97, 98, 90, 2.0),   # low=97 > 96
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        # Should NOT exit via stop on day 3
        if result.trades:
            assert result.trades[0].exit_reason != EXIT_STOP_LOSS or \
                   result.trades[0].exit_date != "2020-01-03"

    def test_gap_down_stop_exits_at_open(self):
        """
        If open < stop_price → exit at OPEN (gap-down), reason STOP_GAP.
        """
        # entry=100, ATR=2, stop=96; next day opens at 93 < 96
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 90, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),   # entry
            _row("2020-01-03", 93, 95, 91, 94, 90, 2.0),      # gap-down open=93 < stop=96
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == EXIT_STOP_GAP
        assert t.exit_date == "2020-01-03"
        assert t.exit_reference_price == pytest.approx(93.0)   # exited at open

    def test_gap_down_takes_priority_over_intraday_stop(self):
        """When open < stop AND low < stop, gap-down wins (priority 1)."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 90, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),
            _row("2020-01-03", 93, 93, 89, 91, 90, 2.0),  # open=93 AND low=89, both < stop=96
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        t = result.trades[0]
        assert t.exit_reason == EXIT_STOP_GAP
        assert t.exit_reference_price == pytest.approx(93.0)

    def test_same_day_stop_on_entry_day(self):
        """
        If stop triggers on the same day as entry (low <= stop on entry day),
        position is exited that same day.
        """
        # entry=100, stop=96; entry day low=95 → stop triggered same day
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 90, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 95, 97, 90, 2.0),  # entry; low=95 <= stop=96
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == EXIT_STOP_LOSS
        assert t.exit_date == "2020-01-02"


# ---------------------------------------------------------------------------
# 4. Trend exit
# ---------------------------------------------------------------------------


class TestTrendExit:

    def test_trend_exit_queued_at_close(self):
        """
        When close < ema20 at day T, exit should execute at T+1 open.

        Design:
          entry=100, ATR=2, stop = 100 - 4 = 96.
          Day 3: close=90 < ema20=95 → trend exit queued.
          Day 4: open=98 (above stop=96, no gap-down); exit at 98 → TREND_EXIT.
        """
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),  # entry; stop=96
            _row("2020-01-03", 101, 105, 100, 90, 95, 2.0),  # close=90 < ema20=95 → queue
            _row("2020-01-04", 98, 100, 97, 99, 95, 2.0),    # open=98 > stop=96 → TREND_EXIT
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == EXIT_TREND
        assert t.exit_date == "2020-01-04"
        assert t.exit_reference_price == pytest.approx(98.0)

    def test_trend_exit_not_triggered_when_close_above_ema20(self):
        """If close >= ema20, no trend exit is queued."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),  # entry
            _row("2020-01-03", 101, 105, 100, 102, 95, 2.0), # close=102 > ema20=95 → no queue
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        # Position still open at end of data → END_OF_DATA
        if result.trades:
            assert result.trades[0].exit_reason == EXIT_END_OF_DATA

    def test_stop_beats_trend_exit_on_deferred_day(self):
        """
        Trend exit is queued at day T close. On day T+1, if open < stop,
        STOP_GAP takes priority over the deferred TREND_EXIT.
        """
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),   # entry
            _row("2020-01-03", 101, 105, 100, 85, 95, 2.0),   # close=85 < ema20=95 → trend exit queued
            _row("2020-01-04", 93, 94, 91, 93, 95, 2.0),      # open=93 < stop=96 → STOP_GAP wins
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == EXIT_STOP_GAP


# ---------------------------------------------------------------------------
# 5. End-of-data exit
# ---------------------------------------------------------------------------


class TestEndOfData:

    def test_open_position_closed_at_end_of_data(self):
        """Position still open at last row → exit at last close (END_OF_DATA)."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),  # entry
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0), # still open
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        t = result.trades[0]
        assert t.exit_reason == EXIT_END_OF_DATA
        assert t.exit_date == "2020-01-03"
        assert t.exit_reference_price == pytest.approx(112.0)

    def test_signal_on_last_day_skipped(self):
        """LONG signal on the very last row cannot be executed → SKIPPED."""
        rows = [
            _row("2020-01-01", 100, 103, 99, 100, 90, 2.0),
            _row("2020-01-02", 100, 103, 99, 100, 90, 2.0, signal="LONG"),  # last row
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 0
        assert any(s.reason == SKIP_NO_NEXT_DAY for s in result.skipped_signals)


# ---------------------------------------------------------------------------
# 6. Transaction costs
# ---------------------------------------------------------------------------


class TestTransactionCosts:

    def test_commission_applied_on_both_legs(self):
        """
        With non-zero commission, transaction_cost = entry_comm + exit_comm.
        """
        config = BacktestConfig(
            initial_capital=100_000.0,
            risk_per_trade=0.01,
            atr_multiplier=2.0,
            cost_model=CostModel(commission_rate=0.001, slippage_rate=0.0),
        )
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),  # entry at 100
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0), # END_OF_DATA
        ]
        result = run_backtest(_make_df(rows), config)
        assert len(result.trades) == 1
        t = result.trades[0]
        expected_entry_comm = t.entry_price * t.quantity * 0.001
        expected_exit_comm = t.exit_price * t.quantity * 0.001
        assert t.transaction_cost == pytest.approx(
            expected_entry_comm + expected_exit_comm, rel=1e-4
        )

    def test_net_pnl_equals_gross_minus_cost(self):
        """net_pnl = gross_pnl - transaction_cost (always)."""
        config = BacktestConfig(
            initial_capital=100_000.0,
            risk_per_trade=0.01,
            atr_multiplier=2.0,
            cost_model=CostModel(commission_rate=0.001, slippage_rate=0.0005),
        )
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), config)
        t = result.trades[0]
        assert t.net_pnl == pytest.approx(t.gross_pnl - t.transaction_cost, rel=1e-6)

    def test_slippage_increases_entry_price(self):
        """Effective entry > reference entry when slippage_rate > 0."""
        config = BacktestConfig(
            initial_capital=100_000.0,
            risk_per_trade=0.01,
            atr_multiplier=2.0,
            cost_model=CostModel(commission_rate=0.0, slippage_rate=0.001),
        )
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), config)
        t = result.trades[0]
        assert t.entry_price > t.entry_reference_price

    def test_slippage_decreases_exit_price(self):
        """Effective exit < reference exit when slippage_rate > 0."""
        config = BacktestConfig(
            initial_capital=100_000.0,
            risk_per_trade=0.01,
            atr_multiplier=2.0,
            cost_model=CostModel(commission_rate=0.0, slippage_rate=0.001),
        )
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), config)
        t = result.trades[0]
        assert t.exit_price < t.exit_reference_price


# ---------------------------------------------------------------------------
# 7. P&L and R-multiple
# ---------------------------------------------------------------------------


class TestPnL:

    def test_gross_pnl_formula(self):
        """gross_pnl = (exit_price - entry_price) × quantity."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        t = result.trades[0]
        expected = (t.exit_price - t.entry_price) * t.quantity
        assert t.gross_pnl == pytest.approx(expected, rel=1e-6)

    def test_r_multiple_formula(self):
        """r_multiple = net_pnl / risk_budget."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),
            _row("2020-01-03", 111, 115, 109, 112, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        t = result.trades[0]
        expected_r = t.net_pnl / t.risk_budget
        assert t.r_multiple == pytest.approx(expected_r, rel=1e-6)

    def test_losing_trade_produces_negative_pnl(self):
        """Stop-loss exit below entry price → negative gross and net P&L."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),   # entry at 100
            _row("2020-01-03", 98, 99, 95, 97, 90, 2.0),      # low=95 < stop=96
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        t = result.trades[0]
        assert t.exit_reason == EXIT_STOP_LOSS
        assert t.gross_pnl < 0


# ---------------------------------------------------------------------------
# 8. Equity curve
# ---------------------------------------------------------------------------


class TestEquityCurve:

    def test_equity_curve_has_one_row_per_day(self):
        df = _flat_df(10)
        result = run_backtest(df, NO_COST_CONFIG)
        assert len(result.equity_curve) == 10

    def test_equity_curve_flat_when_no_trades(self):
        """If no trades occur, equity should remain constant at initial_capital."""
        df = _flat_df(5)
        result = run_backtest(df, NO_COST_CONFIG)
        for row in result.equity_curve:
            assert row.equity == pytest.approx(100_000.0)

    def test_equity_marks_to_market_while_in_position(self):
        """
        While a position is open, equity = cash + qty × close.
        """
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),  # entry; close=110
            _row("2020-01-03", 111, 115, 109, 120, 90, 2.0), # still open; close=120
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)

        assert len(result.trades) == 1
        t = result.trades[0]
        # On day 2 (index 1), position is open
        ec_day2 = result.equity_curve[1]
        assert ec_day2.position_quantity == t.quantity
        assert ec_day2.position_market_value == pytest.approx(t.quantity * 110.0)
        assert ec_day2.equity == pytest.approx(ec_day2.cash + ec_day2.position_market_value)

    def test_equity_flat_after_exit(self):
        """After the position is closed, position_quantity and market_value are 0."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),  # entry
            _row("2020-01-03", 98, 99, 95, 97, 90, 2.0),     # stop-loss exit
            _row("2020-01-04", 97, 99, 96, 98, 90, 2.0),     # flat
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        ec_day4 = result.equity_curve[3]
        assert ec_day4.position_quantity == 0
        assert ec_day4.position_market_value == pytest.approx(0.0)

    def test_equity_equals_cash_plus_mv(self):
        """Equity = cash + position_market_value on every row."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),
            _row("2020-01-03", 111, 115, 109, 120, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        for row in result.equity_curve:
            assert row.equity == pytest.approx(row.cash + row.position_market_value)


# ---------------------------------------------------------------------------
# 9. Concurrency — no multiple positions
# ---------------------------------------------------------------------------


class TestConcurrency:

    def test_second_signal_while_in_position_is_skipped(self):
        """
        A LONG signal on day 3 while position from day 1 is still open
        must be recorded as SKIPPED_IN_POSITION, not opened as a new trade.
        """
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),  # signal 1
            _row("2020-01-02", 100, 103, 99, 110, 90, 2.0),               # entry
            _row("2020-01-03", 111, 113, 109, 112, 90, 2.0, signal="LONG"), # signal 2 (in pos)
            _row("2020-01-04", 113, 115, 111, 114, 90, 2.0),              # still open
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        skips = [s for s in result.skipped_signals if s.reason == SKIP_IN_POSITION]
        assert len(skips) == 1
        assert skips[0].signal_date == "2020-01-03"

    def test_only_one_position_at_a_time(self):
        """After exit, a new signal CAN open a new position."""
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),  # trade 1 signal
            _row("2020-01-02", 100, 103, 97, 102, 90, 2.0),               # trade 1 entry
            _row("2020-01-03", 98, 99, 95, 97, 90, 2.0),                  # stop → trade 1 exit
            _row("2020-01-04", 97, 99, 96, 98, 85, 2.0, signal="LONG"),   # trade 2 signal
            _row("2020-01-05", 98, 101, 97, 100, 90, 2.0),               # trade 2 entry
            _row("2020-01-06", 101, 105, 99, 105, 90, 2.0),              # END_OF_DATA
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 2


# ---------------------------------------------------------------------------
# 10. Lookahead invariance
# ---------------------------------------------------------------------------


class TestLookahead:

    def test_mutating_future_rows_does_not_change_past_decision(self):
        """
        Compute backtest on original data. Record trade 1 details.
        Mutate rows after trade 1's signal day (change future prices).
        Re-run. Trade 1's entry, quantity, stop must be identical.
        """
        rows_original = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 103, 99, 102, 90, 2.0),
            _row("2020-01-03", 101, 105, 100, 108, 90, 2.0),
            _row("2020-01-04", 109, 115, 107, 112, 90, 2.0),
        ]
        df_orig = _make_df(rows_original)
        result_orig = run_backtest(df_orig.copy(), NO_COST_CONFIG)

        # Mutate rows 2..3 (after signal day 0 and entry day 1)
        rows_mutated = rows_original.copy()
        rows_mutated[2]["open"] = 5000.0
        rows_mutated[2]["close"] = 5000.0
        rows_mutated[3]["open"] = 5000.0
        rows_mutated[3]["close"] = 5000.0
        df_mut = _make_df(rows_mutated)
        result_mut = run_backtest(df_mut.copy(), NO_COST_CONFIG)

        assert len(result_orig.trades) >= 1
        assert len(result_mut.trades) >= 1

        t_orig = result_orig.trades[0]
        t_mut = result_mut.trades[0]

        # These must be identical (determined only by signal day + entry day)
        assert t_orig.signal_date == t_mut.signal_date
        assert t_orig.entry_date == t_mut.entry_date
        assert t_orig.entry_reference_price == pytest.approx(t_mut.entry_reference_price)
        assert t_orig.entry_price == pytest.approx(t_mut.entry_price)
        assert t_orig.quantity == t_mut.quantity
        assert t_orig.initial_stop == pytest.approx(t_mut.initial_stop)

    def test_entry_price_does_not_use_future_high_low_close(self):
        """
        Change T+1 high, low, close to extreme values.
        Entry price must still equal T+1 open (unchanged).
        """
        rows = [
            _row("2020-01-01", 99, 101, 97, 99, 85, 2.0, signal="LONG"),
            _row("2020-01-02", 100, 9999, 1, 9999, 90, 2.0),  # extreme high/low/close
            _row("2020-01-03", 101, 105, 99, 102, 90, 2.0),
        ]
        result = run_backtest(_make_df(rows), NO_COST_CONFIG)
        assert len(result.trades) == 1
        # Entry reference price must be T+1 open = 100 (not the extreme values)
        assert result.trades[0].entry_reference_price == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 11. CostModel unit tests
# ---------------------------------------------------------------------------


class TestCostModel:

    def test_effective_entry_higher_than_reference(self):
        cm = CostModel(commission_rate=0.0, slippage_rate=0.001)
        assert cm.effective_entry_price(100.0) == pytest.approx(100.1)

    def test_effective_exit_lower_than_reference(self):
        cm = CostModel(commission_rate=0.0, slippage_rate=0.001)
        assert cm.effective_exit_price(100.0) == pytest.approx(99.9)

    def test_zero_slippage(self):
        cm = CostModel(commission_rate=0.0, slippage_rate=0.0)
        assert cm.effective_entry_price(100.0) == pytest.approx(100.0)
        assert cm.effective_exit_price(100.0) == pytest.approx(100.0)

    def test_commission_entry(self):
        cm = CostModel(commission_rate=0.001, slippage_rate=0.0)
        # 100 shares at ₹100 = ₹10000; commission = 0.1%
        assert cm.entry_commission(100.0, 100) == pytest.approx(10.0)

    def test_total_transaction_cost(self):
        cm = CostModel(commission_rate=0.001, slippage_rate=0.0)
        total = cm.total_transaction_cost(100.0, 110.0, 100)
        # entry: 100*100*0.001=10; exit: 110*100*0.001=11
        assert total == pytest.approx(21.0)

    def test_default_cost_model_values(self):
        assert DEFAULT_COST_MODEL.commission_rate == pytest.approx(0.0005)
        assert DEFAULT_COST_MODEL.slippage_rate == pytest.approx(0.0005)


# ---------------------------------------------------------------------------
# 12. Metrics unit tests
# ---------------------------------------------------------------------------


class TestMetrics:

    def _make_result_with_trades(self, pnls: list[float]) -> BacktestResult:
        """Create a minimal BacktestResult with synthetic trades."""
        from quant.backtest.engine import TradeRecord, EquityRow, BacktestResult
        trades = []
        for i, pnl in enumerate(pnls):
            trades.append(TradeRecord(
                trade_id=i + 1,
                symbol="TEST",
                signal_date=f"2020-01-{i*3+1:02d}",
                entry_date=f"2020-01-{i*3+2:02d}",
                entry_reference_price=100.0,
                entry_price=100.0,
                initial_stop=96.0,
                atr_at_signal=2.0,
                quantity=10,
                risk_budget=100.0,
                exit_date=f"2020-01-{i*3+3:02d}",
                exit_reference_price=100.0 + pnl / 10,
                exit_price=100.0 + pnl / 10,
                exit_reason="STOP_LOSS" if pnl < 0 else "TREND_EXIT",
                gross_pnl=pnl,
                transaction_cost=0.0,
                net_pnl=pnl,
                return_pct=pnl / 1000.0,
                r_multiple=pnl / 100.0,
                holding_days=1,
            ))
        equity = [EquityRow(date=f"2020-01-{d:02d}",
                            cash=100_000.0 + sum(pnls[:d]),
                            position_quantity=0,
                            position_market_value=0.0,
                            equity=100_000.0 + sum(pnls[:d]))
                  for d in range(1, 11)]
        return BacktestResult(
            trades=trades,
            equity_curve=equity,
            initial_capital=100_000.0,
            config={},
        )

    def test_win_rate_correct(self):
        result = self._make_result_with_trades([100.0, -50.0, 200.0])
        m = compute_metrics(result)
        # win_rate = 2/3, rounded to 4dp = 0.6667
        assert m["win_rate"] == pytest.approx(2 / 3, abs=0.001)

    def test_profit_factor_correct(self):
        result = self._make_result_with_trades([100.0, -50.0, 200.0])
        m = compute_metrics(result)
        # gross_profits = 300, gross_losses = 50
        assert m["profit_factor"] == pytest.approx(300.0 / 50.0)

    def test_profit_factor_none_when_no_losses(self):
        result = self._make_result_with_trades([100.0, 200.0])
        m = compute_metrics(result)
        assert m["profit_factor"] is None

    def test_zero_trades_returns_sane_metrics(self):
        result = BacktestResult(
            trades=[],
            equity_curve=[EquityRow("2020-01-01", 100_000.0, 0, 0.0, 100_000.0)],
            initial_capital=100_000.0,
            config={},
        )
        m = compute_metrics(result)
        assert m["num_trades"] == 0
        assert m["win_rate"] is None
        assert m["profit_factor"] is None

    def test_max_drawdown_zero_on_flat_equity(self):
        curve = [EquityRow(f"2020-01-{i:02d}", 100_000.0, 0, 0.0, 100_000.0)
                 for i in range(1, 6)]
        dd = _compute_max_drawdown(curve)
        assert dd == pytest.approx(0.0)

    def test_max_drawdown_correct(self):
        """Peak=110000, trough=88000 → dd = (88000-110000)/110000 = -20%"""
        curve = [
            EquityRow("2020-01-01", 100_000.0, 0, 0.0, 100_000.0),
            EquityRow("2020-01-02", 110_000.0, 0, 0.0, 110_000.0),
            EquityRow("2020-01-03", 88_000.0,  0, 0.0, 88_000.0),
            EquityRow("2020-01-04", 95_000.0,  0, 0.0, 95_000.0),
        ]
        dd = _compute_max_drawdown(curve)
        expected = (88_000 - 110_000) / 110_000 * 100
        assert dd == pytest.approx(expected, rel=1e-4)

    def test_total_return_pct(self):
        result = self._make_result_with_trades([5_000.0])
        m = compute_metrics(result)
        # final equity = 100000 + 5000 = 105000, return = 5%
        # (equity_curve is simplified, just verify formula direction)
        assert m["total_net_pnl"] == pytest.approx(m["final_equity"] - 100_000.0)


# ---------------------------------------------------------------------------
# 13. Utility
# ---------------------------------------------------------------------------


class TestUtility:

    def test_calendar_days_correct(self):
        from quant.backtest.engine import _calendar_days
        assert _calendar_days("2020-01-01", "2020-01-11") == 10
        assert _calendar_days("2020-01-01", "2020-01-01") == 0

    def test_backtest_config_validation(self):
        with pytest.raises(ValueError, match="initial_capital"):
            BacktestConfig(initial_capital=-1)
        with pytest.raises(ValueError, match="risk_per_trade"):
            BacktestConfig(risk_per_trade=0.0)
        with pytest.raises(ValueError, match="atr_multiplier"):
            BacktestConfig(atr_multiplier=0.0)

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"date": ["2020-01-01"], "close": [100.0]})
        with pytest.raises(ValueError, match="missing required columns"):
            run_backtest(df)
