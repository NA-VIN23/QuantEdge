"""
quant/strategies/trend_momentum.py
------------------------------------
Daily Trend-Momentum Breakout strategy for QuantEdge Sprint 2.

Responsibility:
  - Accept the feature-enriched DataFrame (output of compute_all_features).
  - Apply exactly four deterministic conditions.
  - Emit a signal column: LONG | NO_SIGNAL.
  - Emit four diagnostic boolean columns (one per condition).

==============================================================
STRATEGY: Daily Trend-Momentum Breakout
==============================================================

A LONG signal is generated ONLY when ALL four conditions are true:

  Condition 1 — Trend alignment:
      ema20 > ema50
      (short-term trend above long-term trend)

  Condition 2 — Price above trend:
      close > ema20
      (price is above the short-term trend)

  Condition 3 — 20-day breakout:
      close > rolling_max(close, 20).shift(1)
      (today's close exceeds the highest close of the PREVIOUS 20 trading days)

      IMPORTANT: shift(1) is applied AFTER the rolling window.
      This means today's close is NEVER included in its own breakout
      comparison. Only the prior 20 days are considered.

      NaN for rows 0..20 (insufficient prior history for the shifted window).

  Condition 4 — Volume surge:
      volume_ratio > 1.5
      (today's volume is more than 1.5× its 20-day rolling average)

Signal:
  signal = "LONG"      if all four conditions are True
  signal = "NO_SIGNAL" otherwise (including any NaN condition)

==============================================================
WHAT THIS SPRINT DOES NOT DO
==============================================================
  - Does NOT determine entry price
  - Does NOT determine exit price
  - Does NOT simulate stop-losses
  - Does NOT calculate P&L
  - Does NOT size positions
  - Does NOT execute trades

  A LONG signal means: "on this historical day, all four
  conditions of the strategy were satisfied." Nothing more.
  Trade simulation belongs to Sprint 3.

==============================================================
DIAGNOSTIC COLUMNS
==============================================================
  trend_condition    : bool — condition 1 result
  price_condition    : bool — condition 2 result
  breakout_condition : bool — condition 3 result
  volume_condition   : bool — condition 4 result

  NaN in any input feature → the corresponding condition is False
  (no signal can be generated on a row with missing data).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGNAL_LONG = "LONG"
SIGNAL_NONE = "NO_SIGNAL"

# Volume surge multiplier threshold.
VOLUME_SURGE_THRESHOLD: float = 1.5

# Breakout lookback period (in trading days).
BREAKOUT_PERIOD: int = 20

# Required feature columns for strategy application.
REQUIRED_FEATURE_COLUMNS: list[str] = [
    "close",
    "ema20",
    "ema50",
    "avg_volume_20",
    "volume_ratio",
]

# Diagnostic condition column names.
CONDITION_COLUMNS: list[str] = [
    "trend_condition",
    "price_condition",
    "breakout_condition",
    "volume_condition",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_previous_20d_high(close: pd.Series) -> pd.Series:
    """
    Compute the highest close of the PREVIOUS 20 trading days.

    Implementation:
        rolling_max = close.rolling(window=20, min_periods=20).max()
        previous_20d_high = rolling_max.shift(1)

    The shift(1) is applied AFTER the rolling window, so today's close
    is NEVER part of its own breakout comparison.

    First 20 rows (index 0..19): rolling window is not yet complete → NaN.
    Row 20 (after shift): first valid previous-20-day high (max of rows 0..19).

    Parameters
    ----------
    close : pd.Series
        Close price series, sorted chronologically ascending.

    Returns
    -------
    pd.Series
        Previous 20-day rolling max, same index as *close*.
        Rows 0..20 → NaN.
    """
    rolling_max = close.rolling(window=BREAKOUT_PERIOD, min_periods=BREAKOUT_PERIOD).max()
    return rolling_max.shift(1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the Daily Trend-Momentum Breakout strategy to a feature DataFrame.

    The input DataFrame must contain the feature columns produced by
    quant.features.indicators.compute_all_features().

    This function does NOT modify the input DataFrame. It returns a new
    DataFrame containing all existing columns plus four diagnostic condition
    columns and the signal column.

    Parameters
    ----------
    df : pd.DataFrame
        Feature-enriched OHLCV DataFrame (output of compute_all_features).
        Must be sorted chronologically ascending.

    Returns
    -------
    pd.DataFrame
        New DataFrame with original + feature columns plus:
            trend_condition    (bool)
            price_condition    (bool)
            breakout_condition (bool)
            volume_condition   (bool)
            signal             (str: "LONG" or "NO_SIGNAL")

    Raises
    ------
    ValueError
        If any required feature column is missing.
    """
    missing = [c for c in REQUIRED_FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"apply_strategy: missing required feature columns: {missing}"
        )

    # Work on a copy — never mutate the caller's DataFrame.
    out = df.copy()

    close = out["close"]
    ema20 = out["ema20"]
    ema50 = out["ema50"]
    volume_ratio_col = out["volume_ratio"]

    # ------------------------------------------------------------------
    # Condition 1: Trend alignment — ema20 > ema50
    # ------------------------------------------------------------------
    # fillna(False): NaN in ema20/ema50 → condition False (no signal)
    out["trend_condition"] = (ema20 > ema50).fillna(False)

    # ------------------------------------------------------------------
    # Condition 2: Price above short-term trend — close > ema20
    # ------------------------------------------------------------------
    out["price_condition"] = (close > ema20).fillna(False)

    # ------------------------------------------------------------------
    # Condition 3: 20-day breakout
    #   close > max(close over PREVIOUS 20 trading days)
    #   Note: shift(1) ensures today is excluded from its own comparison.
    # ------------------------------------------------------------------
    prev_20d_high = _compute_previous_20d_high(close)
    # NaN in prev_20d_high (insufficient history) → condition False
    out["breakout_condition"] = (close > prev_20d_high).fillna(False)

    # ------------------------------------------------------------------
    # Condition 4: Volume surge — volume_ratio > 1.5
    # ------------------------------------------------------------------
    out["volume_condition"] = (volume_ratio_col > VOLUME_SURGE_THRESHOLD).fillna(False)

    # ------------------------------------------------------------------
    # Final signal: LONG only when all four conditions are True
    # ------------------------------------------------------------------
    all_conditions = (
        out["trend_condition"]
        & out["price_condition"]
        & out["breakout_condition"]
        & out["volume_condition"]
    )
    out["signal"] = all_conditions.map({True: SIGNAL_LONG, False: SIGNAL_NONE})

    return out
