"""
quant/backtest/engine.py
------------------------
Deterministic historical backtesting engine for QuantEdge Sprint 3.

Responsibility:
  - Consume itc_features.csv (Sprint 2 output).
  - Simulate trade execution using explicit, documented rules.
  - Produce a trade ledger (list of TradeRecord).
  - Produce a daily equity curve (list of EquityRow).
  - Produce a list of skipped signals with reasons.

==============================================================
EXECUTION MODEL (LOOKAHEAD-FREE)
==============================================================

Signal at end of day T  →  entry at start of day T+1 (open).

On signal day T the backtester reads: date, OHLCV, ema20, atr14, signal.
It does NOT read any T+1 column to make the entry decision — only
T+1 open is used as the reference price, which is observed AFTER
day T has ended.

==============================================================
ENTRY
==============================================================

If signal = LONG on day T and no position is open:
  1. Look ahead to T+1 open (reference entry price).
     If T+1 does not exist (signal on last day): skip → SKIPPED_NO_NEXT_DAY.
  2. ATR from signal day T must be valid and > 0.
     If not: skip → SKIPPED_ZERO_ATR.
  3. effective_entry = T+1 open × (1 + slippage_rate).
  4. stop_price = effective_entry − (atr_multiplier × atr14_at_T).
  5. risk_budget = current_equity × risk_per_trade.
  6. quantity = floor(risk_budget / (effective_entry − stop_price)).
  7. Capital constraint: quantity = min(quantity, floor(cash / effective_entry)).
  8. If quantity <= 0: skip → SKIPPED_ZERO_QTY.
  9. Deduct: cash -= (effective_entry × quantity) + entry_commission.

If signal = LONG but a position is already open:
  Skip → SKIPPED_IN_POSITION.

==============================================================
EXIT PRIORITY (checked each bar while in position)
==============================================================

1. GAP-DOWN STOP — if day's open < stop_price:
     exit at open, reason STOP_GAP.

2. INTRADAY STOP — else if day's low <= stop_price:
     exit at stop_price, reason STOP_LOSS.

3. DEFERRED TREND EXIT — else if a trend exit was queued at prior close:
     exit at today's open, reason TREND_EXIT.
     (If stop also triggers → stop wins via priorities 1 or 2 above.)

4. END OF DATA — if this is the final row and position still open:
     exit at today's close, reason END_OF_DATA.

After checking exits, if still in position:
  Check if close < ema20 → queue pending_trend_exit for next bar.

==============================================================
CONCURRENCY
==============================================================

Only ONE position in ITC allowed at a time.
No pyramiding. No shorting.

==============================================================
P&L
==============================================================

gross_pnl        = (exit_price - entry_price) × quantity
transaction_cost = entry_commission + exit_commission
net_pnl          = gross_pnl - transaction_cost
return_pct       = net_pnl / (entry_price × quantity)
r_multiple       = net_pnl / risk_budget
holding_days     = calendar days from entry_date to exit_date
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from quant.backtest.costs import CostModel, DEFAULT_COST_MODEL


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGNAL_LONG = "LONG"

EXIT_STOP_LOSS = "STOP_LOSS"
EXIT_STOP_GAP = "STOP_GAP"
EXIT_TREND = "TREND_EXIT"
EXIT_END_OF_DATA = "END_OF_DATA"

SKIP_IN_POSITION = "SKIPPED_IN_POSITION"
SKIP_NO_NEXT_DAY = "SKIPPED_NO_NEXT_DAY"
SKIP_ZERO_QTY = "SKIPPED_ZERO_QTY"
SKIP_ZERO_ATR = "SKIPPED_ZERO_ATR"

# Required columns in the input DataFrame
REQUIRED_COLUMNS: list[str] = [
    "date", "open", "high", "low", "close", "ema20", "atr14", "signal",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TradeRecord:
    """A single closed trade in the ledger."""

    trade_id: int
    symbol: str
    signal_date: str             # Day T — when the LONG signal was generated
    entry_date: str              # Day T+1 — when the position was opened
    entry_reference_price: float # T+1 open (pre-slippage)
    entry_price: float           # Effective entry (post-slippage)
    initial_stop: float          # Stop price at the time of entry
    atr_at_signal: float         # ATR14 value on signal day T
    quantity: int                # Whole shares purchased
    risk_budget: float           # equity × risk_per_trade at entry
    exit_date: str
    exit_reference_price: float  # Raw exit price (pre-slippage)
    exit_price: float            # Effective exit (post-slippage)
    exit_reason: str             # STOP_LOSS / STOP_GAP / TREND_EXIT / END_OF_DATA
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    return_pct: float            # net_pnl / (entry_price × quantity)
    r_multiple: float            # net_pnl / risk_budget
    holding_days: int            # Calendar days from entry to exit


@dataclass
class EquityRow:
    """One day on the daily equity curve."""

    date: str
    cash: float
    position_quantity: int
    position_market_value: float  # quantity × close (0 if flat)
    equity: float                 # cash + position_market_value


@dataclass
class SkippedSignal:
    """A LONG signal that was not executed, with the reason."""

    signal_date: str
    reason: str      # SKIPPED_IN_POSITION / SKIPPED_NO_NEXT_DAY / etc.
    detail: str = ""


@dataclass
class BacktestResult:
    """Complete output of the backtesting engine."""

    trades: list[TradeRecord] = field(default_factory=list)
    equity_curve: list[EquityRow] = field(default_factory=list)
    skipped_signals: list[SkippedSignal] = field(default_factory=list)
    initial_capital: float = 100_000.0
    config: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestConfig:
    """
    Immutable configuration for the backtesting engine.

    All parameters have explicit, documented defaults.
    Override via constructor arguments — do not modify after creation.
    """

    initial_capital: float = 100_000.0
    risk_per_trade: float = 0.01        # fraction of equity risked per trade
    atr_multiplier: float = 2.0         # stop = entry − (multiplier × ATR)
    cost_model: CostModel = field(default_factory=lambda: DEFAULT_COST_MODEL)
    symbol: str = "ITC"

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be > 0")
        if not (0 < self.risk_per_trade <= 1):
            raise ValueError("risk_per_trade must be in (0, 1]")
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be > 0")


# ---------------------------------------------------------------------------
# Main simulation function
# ---------------------------------------------------------------------------


def run_backtest(
    df: pd.DataFrame,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """
    Run the deterministic historical backtest on the feature DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Feature-enriched DataFrame (itc_features.csv), sorted ascending by date.
        Required columns: date, open, high, low, close, ema20, atr14, signal.

    config : BacktestConfig, optional
        Engine configuration. Uses defaults if None.

    Returns
    -------
    BacktestResult
        Full trade ledger, daily equity curve, skipped signals.

    Notes
    -----
    Lookahead guarantee:
      - Signal day T uses only columns from row T.
      - Entry price = row T+1 open (the next day's first price).
      - ATR for stop calculation = row T atr14 (known at signal time).
      - T+1 high/low/close are NEVER used for the entry decision.
    """
    if config is None:
        config = BacktestConfig()

    _validate_input(df)
    df = df.reset_index(drop=True)
    n = len(df)
    cost = config.cost_model

    result = BacktestResult(
        initial_capital=config.initial_capital,
        config={
            "initial_capital": config.initial_capital,
            "risk_per_trade": config.risk_per_trade,
            "atr_multiplier": config.atr_multiplier,
            "commission_rate": cost.commission_rate,
            "slippage_rate": cost.slippage_rate,
            "symbol": config.symbol,
        },
    )

    # ---- Simulation state ----
    cash: float = config.initial_capital
    in_position: bool = False
    pending_trend_exit: bool = False

    # Active position fields (valid only when in_position=True)
    pos_signal_date: str = ""
    pos_entry_date: str = ""
    pos_entry_reference: float = 0.0
    pos_entry_price: float = 0.0
    pos_stop: float = 0.0
    pos_atr: float = 0.0
    pos_quantity: int = 0
    pos_risk_budget: float = 0.0
    trade_id_counter: int = 0

    # ---- Main loop ----
    for i in range(n):
        row = df.iloc[i]
        date_str = str(row["date"])
        day_open = float(row["open"])
        day_low = float(row["low"])
        day_close = float(row["close"])
        day_ema20 = row["ema20"]
        day_signal = str(row["signal"])

        # Current equity (mark-to-market using today's close)
        current_mv = pos_quantity * day_close if in_position else 0.0
        current_equity = cash + current_mv

        # ----------------------------------------------------------------
        # EXITS
        # ----------------------------------------------------------------
        if in_position:
            exit_triggered = False
            exit_ref_price = 0.0
            exit_eff_price = 0.0
            exit_reason = ""

            # Priority 1: Gap-down stop
            if day_open < pos_stop:
                exit_ref_price = day_open
                exit_eff_price = cost.effective_exit_price(exit_ref_price)
                exit_reason = EXIT_STOP_GAP
                exit_triggered = True
                pending_trend_exit = False

            # Priority 2: Intraday stop (low touched or breached stop)
            elif day_low <= pos_stop:
                exit_ref_price = pos_stop
                exit_eff_price = cost.effective_exit_price(exit_ref_price)
                exit_reason = EXIT_STOP_LOSS
                exit_triggered = True
                pending_trend_exit = False

            # Priority 3: Deferred trend exit from prior close
            elif pending_trend_exit:
                exit_ref_price = day_open
                exit_eff_price = cost.effective_exit_price(exit_ref_price)
                exit_reason = EXIT_TREND
                exit_triggered = True
                pending_trend_exit = False

            # Priority 4: End of data
            elif i == n - 1:
                exit_ref_price = day_close
                exit_eff_price = cost.effective_exit_price(exit_ref_price)
                exit_reason = EXIT_END_OF_DATA
                exit_triggered = True
                pending_trend_exit = False

            if exit_triggered:
                exit_commission = cost.exit_commission(exit_eff_price, pos_quantity)
                entry_commission = cost.entry_commission(pos_entry_price, pos_quantity)
                gross_pnl = (exit_eff_price - pos_entry_price) * pos_quantity
                total_cost = entry_commission + exit_commission
                net_pnl = gross_pnl - total_cost
                return_pct = net_pnl / (pos_entry_price * pos_quantity) \
                    if pos_entry_price * pos_quantity != 0 else 0.0
                r_multiple = net_pnl / pos_risk_budget \
                    if pos_risk_budget != 0 else 0.0
                holding = _calendar_days(pos_entry_date, date_str)

                cash = cash + (exit_eff_price * pos_quantity) - exit_commission
                trade_id_counter += 1

                result.trades.append(TradeRecord(
                    trade_id=trade_id_counter,
                    symbol=config.symbol,
                    signal_date=pos_signal_date,
                    entry_date=pos_entry_date,
                    entry_reference_price=pos_entry_reference,
                    entry_price=pos_entry_price,
                    initial_stop=pos_stop,
                    atr_at_signal=pos_atr,
                    quantity=pos_quantity,
                    risk_budget=pos_risk_budget,
                    exit_date=date_str,
                    exit_reference_price=exit_ref_price,
                    exit_price=exit_eff_price,
                    exit_reason=exit_reason,
                    gross_pnl=gross_pnl,
                    transaction_cost=total_cost,
                    net_pnl=net_pnl,
                    return_pct=return_pct,
                    r_multiple=r_multiple,
                    holding_days=holding,
                ))

                in_position = False
                pos_quantity = 0
                current_equity = cash  # now flat

            else:
                # No exit — check if trend exit should be queued
                if (not pending_trend_exit
                        and not pd.isna(day_ema20)
                        and day_close < float(day_ema20)):
                    pending_trend_exit = True

        # ----------------------------------------------------------------
        # ENTRY
        # ----------------------------------------------------------------
        if not in_position and day_signal == SIGNAL_LONG:
            entry_result = _attempt_entry(
                i=i, n=n, df=df,
                date_str=date_str, signal_row=row,
                cash=cash, current_equity=current_equity,
                config=config, cost=cost,
            )
            if entry_result is not None:
                (cash,
                 pos_signal_date, pos_entry_date,
                 pos_entry_reference, pos_entry_price,
                 pos_stop, pos_atr, pos_quantity, pos_risk_budget) = entry_result
                in_position = True
                pending_trend_exit = False
            else:
                reason, detail = _skip_reason(
                    i=i, n=n, df=df,
                    signal_row=row,
                    cash=cash, current_equity=current_equity,
                    config=config, cost=cost,
                )
                result.skipped_signals.append(SkippedSignal(
                    signal_date=date_str, reason=reason, detail=detail
                ))

        elif in_position and day_signal == SIGNAL_LONG:
            # Already in a position — skip this signal
            result.skipped_signals.append(SkippedSignal(
                signal_date=date_str,
                reason=SKIP_IN_POSITION,
                detail="Position already open; no pyramiding.",
            ))

        # ----------------------------------------------------------------
        # EQUITY CURVE (end-of-day snapshot)
        # ----------------------------------------------------------------
        eod_mv = pos_quantity * day_close if in_position else 0.0
        result.equity_curve.append(EquityRow(
            date=date_str,
            cash=round(cash, 6),
            position_quantity=pos_quantity,
            position_market_value=round(eod_mv, 6),
            equity=round(cash + eod_mv, 6),
        ))

    return result


# ---------------------------------------------------------------------------
# Entry helper
# ---------------------------------------------------------------------------


def _attempt_entry(
    i: int,
    n: int,
    df: pd.DataFrame,
    date_str: str,
    signal_row: pd.Series,
    cash: float,
    current_equity: float,
    config: BacktestConfig,
    cost: CostModel,
) -> Optional[tuple]:
    """
    Attempt to open a position on the next trading day.

    Returns a tuple of updated position state on success, or None if the
    trade must be skipped.

    This function only looks at row T+1 open to determine the entry price.
    It does NOT use T+1 high, low, or close.
    """
    # No next day
    if i + 1 >= n:
        return None

    signal_atr = signal_row["atr14"]
    if pd.isna(signal_atr) or float(signal_atr) <= 0:
        return None

    next_row = df.iloc[i + 1]
    ref_entry = float(next_row["open"])           # T+1 open only
    eff_entry = cost.effective_entry_price(ref_entry)
    signal_atr_f = float(signal_atr)

    stop_price = eff_entry - config.atr_multiplier * signal_atr_f
    risk_per_share = eff_entry - stop_price       # always > 0

    risk_budget = current_equity * config.risk_per_trade
    quantity = int(math.floor(risk_budget / risk_per_share))

    # Capital constraint
    max_affordable = int(math.floor(cash / eff_entry))
    quantity = min(quantity, max_affordable)

    if quantity <= 0:
        return None

    entry_commission = cost.entry_commission(eff_entry, quantity)
    new_cash = cash - eff_entry * quantity - entry_commission

    return (
        new_cash,
        date_str,                  # pos_signal_date
        str(next_row["date"]),     # pos_entry_date
        ref_entry,                 # pos_entry_reference
        eff_entry,                 # pos_entry_price
        stop_price,                # pos_stop
        signal_atr_f,              # pos_atr
        quantity,                  # pos_quantity
        risk_budget,               # pos_risk_budget
    )


def _skip_reason(
    i: int,
    n: int,
    df: pd.DataFrame,
    signal_row: pd.Series,
    cash: float,
    current_equity: float,
    config: BacktestConfig,
    cost: CostModel,
) -> tuple[str, str]:
    """Return (reason_code, detail_string) for a skipped entry signal."""
    if i + 1 >= n:
        return SKIP_NO_NEXT_DAY, "Signal on last day; no next trading day."

    signal_atr = signal_row["atr14"]
    if pd.isna(signal_atr) or float(signal_atr) <= 0:
        return SKIP_ZERO_ATR, f"atr14={signal_atr!r} on signal day is invalid."

    next_row = df.iloc[i + 1]
    ref_entry = float(next_row["open"])
    eff_entry = cost.effective_entry_price(ref_entry)
    stop_price = eff_entry - config.atr_multiplier * float(signal_atr)
    risk_per_share = eff_entry - stop_price

    risk_budget = current_equity * config.risk_per_trade
    qty = int(math.floor(risk_budget / risk_per_share)) if risk_per_share > 0 else 0
    max_aff = int(math.floor(cash / eff_entry)) if eff_entry > 0 else 0
    final_qty = min(qty, max_aff)

    return (
        SKIP_ZERO_QTY,
        f"qty_risk={qty}, qty_affordable={max_aff} → final={final_qty}.",
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_input(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"run_backtest: missing required columns: {missing}"
        )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _calendar_days(start: str, end: str) -> int:
    """Calendar days between two YYYY-MM-DD strings."""
    try:
        return max(0, (pd.Timestamp(end) - pd.Timestamp(start)).days)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# CSV loader convenience
# ---------------------------------------------------------------------------


def backtest_from_csv(
    features_csv: str,
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """
    Load itc_features.csv and run the backtest.

    Parameters
    ----------
    features_csv : str
        Path to the Sprint 2 features CSV.
    config : BacktestConfig, optional

    Returns
    -------
    BacktestResult
    """
    df = pd.read_csv(features_csv)
    df = df.sort_values("date", ascending=True).reset_index(drop=True)
    return run_backtest(df, config)
