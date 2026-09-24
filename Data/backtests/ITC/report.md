# QuantEdge -- Backtest Report [ITC]

**Generated:** 2026-09-23 16:09:56

> [!CAUTION]
> This is a **historical simulation only**. Past simulation results do NOT
> guarantee future performance. This report does NOT constitute investment advice.

---

## 1. Dataset

- **Symbol:** ITC
- **Source:** `Data/processed/stocks/ITC_features.csv`
- **Date range:** 2005-04-01 to 2025-05-29
- **Total trading days:** 5000

---

## 2. Strategy

**Daily Trend-Momentum Breakout** (Sprint 2)

| # | Condition | Rule |
|---|-----------|------|
| 1 | Trend | `ema20 > ema50` |
| 2 | Price | `close > ema20` |
| 3 | Breakout | `close > rolling_max(close, 20).shift(1)` |
| 4 | Volume | `volume_ratio > 1.5` |

---

## 3. Performance Metrics

| Metric | Value |
|--------|-------|
| Initial capital | Rs.100,000.00 |
| Final equity | Rs.91,464.71 |
| Total net P&L | Rs.-8,535.29 |
| Total return | -8.54% |
| Executed trades | 70 |
| Winning trades | 23 |
| Losing trades | 47 |
| Win rate | 32.86% |
| Profit factor | 0.78 |
| Max drawdown | -25.14% |