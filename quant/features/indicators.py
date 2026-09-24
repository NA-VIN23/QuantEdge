"""
quant/features/indicators.py
-----------------------------
Pure technical indicator functions for QuantEdge Sprint 2.

Responsibility:
  - Accept a pandas Series or DataFrame as input.
  - Return a pandas Series containing the computed indicator.
  - Apply ZERO side effects — all functions are pure and stateless.
  - Use ONLY data available at or before each bar's timestamp (no lookahead).

Indicators implemented:
  ema(close, span)          → Exponential Moving Average
  sma(close, window)        → Simple Moving Average
  true_range(high, low, close) → True Range series
  atr_wilder(high, low, close, period) → Wilder's smoothed ATR
  avg_volume(volume, window) → Rolling mean volume
  volume_ratio(volume, avg_vol) → volume / avg_volume (NaN-safe)
  momentum(close, period)   → (close / close.shift(period)) - 1
  compute_all_features(df)  → DataFrame with all feature columns added

==============================================================
LOOKAHEAD POLICY
==============================================================
Every indicator is computed using only data at or before row T.
  - rolling() uses window of size N ending at T
  - ewm() uses history up to T
  - shift(N) accesses T-N (past data)
  - No forward-fill or backfill is applied
  - NaN is emitted where insufficient history exists

==============================================================
ATR CONVENTION — Wilder's Smoothed ATR (RMA)
==============================================================
Standard formula used in TradingView, MetaTrader, standard charting:

  TR[0]  = high[0] - low[0]          (no previous close on first bar)
  TR[t]  = max(
               high[t] - low[t],
               |high[t] - close[t-1]|,
               |low[t]  - close[t-1]|
           )

  ATR[N-1] = mean(TR[0..N-1])        (seed: simple average of first N TRs)
  ATR[t]   = (ATR[t-1] × (N-1) + TR[t]) / N    for t >= N

  This is equivalent to:  atr.ewm(alpha=1/N, adjust=False).mean()
  applied to the TR series, seeded with the simple mean of the first N values.

  Rows 0 to N-2 → NaN (insufficient history to form a complete ATR).
  Row N-1       → first valid ATR (simple mean of first N TRs).

==============================================================
EMA CONVENTION
==============================================================
  Uses pandas ewm(span=N, adjust=False).mean()

  This is equivalent to: alpha = 2 / (N + 1), initialized at first observation.
  Values are produced from row 0 — the first ~N rows carry less statistical
  weight but are mathematically valid and are NOT suppressed.

  This is the standard "EMA" as used in most financial software.

==============================================================
WARM-UP PERIODS (first valid row index, 0-based)
==============================================================
  ema20        : row 0   (statistically meaningful after ~20 rows)
  ema50        : row 0   (statistically meaningful after ~50 rows)
  sma20        : row 19  (requires min_periods=20)
  sma50        : row 49  (requires min_periods=50)
  atr14        : row 13  (first complete 14-bar ATR)
  avg_volume_20: row 19  (requires min_periods=20)
  volume_ratio : row 19  (denominator requires avg_volume_20)
  momentum_5   : row 5   (requires close.shift(5))
  momentum_20  : row 20  (requires close.shift(20))
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Expected input columns from itc_daily_clean.csv.
REQUIRED_INPUT_COLUMNS: list[str] = [
    "date", "symbol", "open", "high", "low", "close", "volume"
]

# Names of all feature columns produced by compute_all_features().
FEATURE_COLUMNS: list[str] = [
    "ema20",
    "ema50",
    "sma20",
    "sma50",
    "atr14",
    "avg_volume_20",
    "volume_ratio",
    "momentum_5",
    "momentum_20",
]


# ---------------------------------------------------------------------------
# Individual indicator functions
# ---------------------------------------------------------------------------


def ema(close: pd.Series, span: int) -> pd.Series:
    """
    Exponential Moving Average using Wilder/EMA convention.

    Uses pandas ewm(span=span, adjust=False), which is equivalent to:
        alpha = 2 / (span + 1)
    initialized at the first observation (no warm-up NaN suppression).

    Parameters
    ----------
    close : pd.Series
        Close price series, sorted chronologically ascending.
    span : int
        EMA span (e.g. 20 or 50). Must be >= 1.

    Returns
    -------
    pd.Series
        EMA values aligned to the same index as *close*.
        Values in the first ~span rows have less statistical weight
        but are not set to NaN.
    """
    if span < 1:
        raise ValueError(f"EMA span must be >= 1, got {span}")
    return close.ewm(span=span, adjust=False).mean()


def sma(close: pd.Series, window: int) -> pd.Series:
    """
    Simple Moving Average.

    NaN for rows where fewer than *window* observations are available.

    Parameters
    ----------
    close : pd.Series
        Close price series, sorted chronologically ascending.
    window : int
        Rolling window size. Must be >= 1.

    Returns
    -------
    pd.Series
        SMA values aligned to the same index as *close*.
        First (window - 1) rows are NaN.
    """
    if window < 1:
        raise ValueError(f"SMA window must be >= 1, got {window}")
    return close.rolling(window=window, min_periods=window).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """
    True Range series.

    Formula:
        TR[0]  = high[0] - low[0]    (no previous close on first bar)
        TR[t]  = max(
                     high[t] - low[t],
                     |high[t] - close[t-1]|,
                     |low[t]  - close[t-1]|
                 )

    Parameters
    ----------
    high, low, close : pd.Series
        OHLC series, sorted chronologically ascending, sharing the same index.

    Returns
    -------
    pd.Series
        True Range values aligned to the same index.
        Row 0 uses the simplified formula (no prior close).
        All subsequent rows use the full three-component formula.
    """
    prev_close = close.shift(1)

    hl = high - low
    hpc = (high - prev_close).abs()
    lpc = (low - prev_close).abs()

    # For the first row, prev_close is NaN, so hpc and lpc are NaN.
    # Use high - low for row 0 by filling via combine.
    tr = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)

    # Row 0: prev_close is NaN → hpc, lpc are NaN → max still NaN.
    # Replace row 0 with the basic high - low.
    tr.iloc[0] = hl.iloc[0]

    return tr


def atr_wilder(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Average True Range using Wilder's smoothing method (RMA).

    Seeding:
        ATR[period-1] = mean(TR[0..period-1])
    Subsequent:
        ATR[t] = (ATR[t-1] * (period - 1) + TR[t]) / period

    This is equivalent to:
        ewm(alpha=1/period, adjust=False)
    applied to TR, but with the first value set to the simple mean
    of the first *period* TRs (not the first TR alone).

    Parameters
    ----------
    high, low, close : pd.Series
        OHLC series, sorted chronologically ascending, sharing the same index.
    period : int
        ATR period. Typically 14.

    Returns
    -------
    pd.Series
        ATR values aligned to the same index.
        Rows 0 to (period - 2) → NaN.
        Row (period - 1) → first valid ATR (simple mean of first *period* TRs).
    """
    if period < 1:
        raise ValueError(f"ATR period must be >= 1, got {period}")

    tr = true_range(high, low, close)
    n = len(tr)
    atr_values = np.full(n, np.nan)

    if n < period:
        # Not enough data to compute even a single ATR value.
        return pd.Series(atr_values, index=close.index, name="atr14")

    # Seed: simple average of first *period* TR values.
    atr_values[period - 1] = tr.iloc[:period].mean()

    # Wilder's smoothing: RMA
    alpha = 1.0 / period
    for i in range(period, n):
        atr_values[i] = atr_values[i - 1] * (1.0 - alpha) + tr.iloc[i] * alpha

    return pd.Series(atr_values, index=close.index, name="atr14")


def avg_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Rolling mean volume.

    NaN for rows where fewer than *window* volume observations are available.

    Parameters
    ----------
    volume : pd.Series
        Volume series, sorted chronologically ascending.
    window : int
        Rolling window size. Default 20.

    Returns
    -------
    pd.Series
        Rolling mean volume, same index as *volume*.
        First (window - 1) rows are NaN.
    """
    if window < 1:
        raise ValueError(f"avg_volume window must be >= 1, got {window}")
    return volume.rolling(window=window, min_periods=window).mean()


def volume_ratio(volume: pd.Series, avg_vol: pd.Series) -> pd.Series:
    """
    Volume ratio: current volume divided by its rolling average.

    formula:
        volume_ratio = volume / avg_volume_20

    NaN-safe: if avg_vol is NaN or zero for a row, volume_ratio is NaN for that row.

    Parameters
    ----------
    volume : pd.Series
        Current bar volume.
    avg_vol : pd.Series
        Rolling average volume (e.g. output of avg_volume()).

    Returns
    -------
    pd.Series
        Volume ratio, same index as *volume*. NaN where avg_vol is 0 or NaN.
    """
    # Replace zero denominators with NaN to avoid ZeroDivisionError.
    safe_denom = avg_vol.replace(0, np.nan)
    return volume / safe_denom


def momentum(close: pd.Series, period: int) -> pd.Series:
    """
    Price momentum over *period* bars.

    formula:
        momentum = (close[t] / close[t - period]) - 1

    Equivalent to percentage price change over *period* bars.
    First *period* rows are NaN (insufficient history).

    Parameters
    ----------
    close : pd.Series
        Close price series, sorted chronologically ascending.
    period : int
        Lookback period. Must be >= 1.

    Returns
    -------
    pd.Series
        Momentum values, same index as *close*.
        First *period* rows are NaN.
    """
    if period < 1:
        raise ValueError(f"Momentum period must be >= 1, got {period}")
    return (close / close.shift(period)) - 1.0


# ---------------------------------------------------------------------------
# Composite feature computation
# ---------------------------------------------------------------------------


def compute_all_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all Sprint 2 technical features and attach them to the DataFrame.

    This function does NOT modify the input DataFrame. It returns a new
    DataFrame containing the original columns plus all feature columns.

    The input DataFrame must:
      - Be sorted chronologically ascending by date (Sprint 1 guarantees this).
      - Contain columns: date, symbol, open, high, low, close, volume.

    Lookahead guarantee:
      All features use only data at or before the current row's timestamp.
      No forward-fill, backfill, or future data references are used.

    Parameters
    ----------
    df : pd.DataFrame
        Canonical OHLCV DataFrame from Sprint 1 (itc_daily_clean.csv).

    Returns
    -------
    pd.DataFrame
        New DataFrame with original columns plus feature columns.
        Feature columns have NaN where insufficient history exists.
        Row count equals input row count.

    Raises
    ------
    ValueError
        If any required input column is missing.
    """
    missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"compute_all_features: missing required columns: {missing}"
        )

    # Work on a copy — never mutate the caller's DataFrame.
    out = df.copy()

    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]

    # --- EMA ---
    out["ema20"] = ema(close, span=20)
    out["ema50"] = ema(close, span=50)

    # --- SMA ---
    out["sma20"] = sma(close, window=20)
    out["sma50"] = sma(close, window=50)

    # --- ATR ---
    out["atr14"] = atr_wilder(high, low, close, period=14)

    # --- Volume ---
    avg_vol = avg_volume(volume, window=20)
    out["avg_volume_20"] = avg_vol
    out["volume_ratio"] = volume_ratio(volume, avg_vol)

    # --- Momentum ---
    out["momentum_5"] = momentum(close, period=5)
    out["momentum_20"] = momentum(close, period=20)

    return out
