# Sprint 2 — Quant/Feature Engine Reference

## Overview

Sprint 2 builds the technical feature engine and the first deterministic
strategy on top of the Sprint 1 canonical OHLCV dataset.

**Input:** `data/processed/itc_daily_clean.csv` (Sprint 1 output, never modified)

**Output:** `data/processed/itc_features.csv`

**Entry point:** `python -m quant.features.pipeline`

---

## Lookahead Policy

> **Every feature at row T uses only data available at or before T.**

- `rolling(N)` windows look backward only
- `ewm(span=N, adjust=False)` initializes at the first observation and looks backward
- `shift(N)` accesses row T−N (past data)
- No `fillna`, `ffill`, or `bfill` is applied to indicator values
- NaN is emitted where insufficient history exists

Tests in `tests/test_indicators.py` and `tests/test_strategy.py` explicitly verify
that mutating future rows does not change any earlier feature or signal value.

---

## Feature Definitions

### EMA20 / EMA50 — Exponential Moving Average

| Property | Value |
|----------|-------|
| Column | `ema20`, `ema50` |
| Formula | `close.ewm(span=N, adjust=False).mean()` |
| Convention | alpha = 2/(N+1); initialized at first close |
| First valid row | Row 0 (values exist from first bar; statistically meaningful after ~N bars) |
| NaN rows | None |

**Note:** EMA produces a value on every row by design. The first ~N rows have less
statistical weight because fewer observations have been incorporated, but they are
mathematically valid and are NOT suppressed.

---

### SMA20 / SMA50 — Simple Moving Average

| Property | Value |
|----------|-------|
| Column | `sma20`, `sma50` |
| Formula | `close.rolling(N, min_periods=N).mean()` |
| First valid row | Row 19 (SMA20), Row 49 (SMA50) |
| NaN rows | 0–18 (SMA20), 0–48 (SMA50) |

---

### ATR14 — Average True Range (Wilder's Method)

| Property | Value |
|----------|-------|
| Column | `atr14` |
| Period | 14 bars |
| First valid row | Row 13 |
| NaN rows | 0–12 |

**True Range formula:**

```
TR[0]  = high[0] - low[0]                              (no previous close on first bar)
TR[t]  = max(
             high[t] - low[t],
             |high[t] - close[t-1]|,
             |low[t]  - close[t-1]|
         )
```

**Wilder's smoothed ATR (RMA):**

```
ATR[13] = mean(TR[0], TR[1], ..., TR[13])              (simple average — seed)
ATR[t]  = (ATR[t-1] × 13 + TR[t]) / 14               (Wilder smoothing, t ≥ 14)
```

This is the standard Wilder ATR used in TradingView, MetaTrader, and most charting
platforms. It is equivalent to `ewm(alpha=1/14, adjust=False)` seeded at the simple
mean of the first 14 TRs (not at the first TR alone).

---

### Average Volume 20

| Property | Value |
|----------|-------|
| Column | `avg_volume_20` |
| Formula | `volume.rolling(20, min_periods=20).mean()` |
| First valid row | Row 19 |
| NaN rows | 0–18 |

---

### Volume Ratio

| Property | Value |
|----------|-------|
| Column | `volume_ratio` |
| Formula | `volume / avg_volume_20` |
| Zero-denominator | NaN (safe) |
| NaN rows | 0–18 (propagated from avg_volume_20) |

---

### Momentum 5 / Momentum 20

| Property | Value |
|----------|-------|
| Column | `momentum_5`, `momentum_20` |
| Formula | `(close / close.shift(N)) - 1` |
| Interpretation | Percentage price change over N trading days |
| NaN rows | 0–4 (momentum_5), 0–19 (momentum_20) |

---

## Warm-up Summary

| Feature | First valid row (0-based) | NaN rows |
|---------|--------------------------|----------|
| `ema20` | 0 | 0 |
| `ema50` | 0 | 0 |
| `sma20` | 19 | 0–18 (19 rows) |
| `sma50` | 49 | 0–48 (49 rows) |
| `atr14` | 13 | 0–12 (13 rows) |
| `avg_volume_20` | 19 | 0–18 (19 rows) |
| `volume_ratio` | 19 | 0–18 (19 rows) |
| `momentum_5` | 5 | 0–4 (5 rows) |
| `momentum_20` | 20 | 0–19 (20 rows) |

---

## Strategy: Daily Trend-Momentum Breakout

### Signal Values

| Value | Meaning |
|-------|---------|
| `LONG` | All four conditions satisfied on this trading day |
| `NO_SIGNAL` | One or more conditions not satisfied |

**No trade simulation is performed.** `LONG` means the strategy conditions
were met historically. Entry/exit/P&L simulation belongs to Sprint 3.

### Four Conditions

**Condition 1 — Trend alignment (`trend_condition`)**
```
ema20 > ema50
```
Short-term trend is above long-term trend.

**Condition 2 — Price above trend (`price_condition`)**
```
close > ema20
```
Price is above the short-term trend.

**Condition 3 — 20-day breakout (`breakout_condition`)**
```
close > rolling_max(close, 20).shift(1)
```
Today's close exceeds the **highest close of the previous 20 trading days**.

> **Critical:** `.shift(1)` is applied **after** the rolling window.
> Today's close is **never** included in its own breakout comparison.
> This is enforced by the implementation and verified by tests.

First valid signal: row 21 (20 prior rows for the window + 1 shift).

**Condition 4 — Volume surge (`volume_condition`)**
```
volume_ratio > 1.5
```
Today's volume is more than 1.5× its 20-day rolling average.

### Signal Logic

```python
signal = "LONG" if (
    trend_condition AND
    price_condition AND
    breakout_condition AND
    volume_condition
) else "NO_SIGNAL"
```

NaN in any feature input → the corresponding condition is `False` → `NO_SIGNAL`.

---

## Output Dataset Schema

`data/processed/itc_features.csv` — column order:

```
date, symbol, open, high, low, close, volume,
ema20, ema50, sma20, sma50, atr14,
avg_volume_20, volume_ratio, momentum_5, momentum_20,
trend_condition, price_condition, breakout_condition, volume_condition,
signal
```

Row count equals the Sprint 1 input (5,000 rows for ITC). No rows are
dropped due to warm-up NaN.

---

## Deferred to Later Sprints

| Item | Sprint |
|------|--------|
| Entry price, exit price, stop-loss | Sprint 3 |
| P&L, equity curve, drawdown | Sprint 3 |
| Additional indicators (RSI, MACD, Bollinger Bands) | Sprint 6+ |
| Walk-forward / out-of-sample validation | Sprint 6 |
| Multi-stock feature generation | Sprint 5 |
| Strategy parameter optimization | Sprint 6 |
| AI-driven signals | Sprint 7 |
