# QuantEdge — Backtest Report

**Generated:** 2026-09-21 18:59:26

> [!CAUTION]
> This is a **historical simulation only**. Past simulation results do NOT
> guarantee future performance. This report does NOT constitute investment
> advice. The strategy parameters have NOT been optimised or validated
> out-of-sample. Results are highly sensitive to the execution assumptions
> documented below.

---

## 1. Dataset

- **Symbol:** ITC
- **Source:** `data/processed/itc_features.csv` (Sprint 2 output)
- **Date range:** 2005-04-01 → 2025-05-29
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

## 3. Execution Assumptions

| Assumption | Value |
|------------|-------|
| Entry | Next trading day's OPEN after signal |
| Lookahead | None — signal day T uses only data through T |
| Position type | Long only |
| Concurrent positions | Maximum 1 |
| Pyramiding | Disabled |

---

## 4. Risk Assumptions

| Parameter | Value |
|-----------|-------|
| Initial capital | ₹100,000 |
| Risk per trade | 1.0% of equity |
| ATR multiplier | 2.0× |
| Stop type | Initial hard stop (ATR-based) |

---

## 5. Cost Assumptions

> [!NOTE]
> These are **research defaults** — not claims about actual broker charges.
> Real NSE transaction costs include brokerage, STT, exchange charges, GST,
> SEBI fees, and stamp duty. These defaults should be updated before any
> production use.

| Parameter | Value |
|-----------|-------|
| Commission rate | 0.0500% per side |
| Slippage rate | 0.0500% per side |
| Application | Entry and exit, both sides |

---

## 6. Exit Rules

| Priority | Rule | Execution |
|----------|------|-----------|
| 1 | Gap-down stop (open < stop) | Exit at open → `STOP_GAP` |
| 2 | Intraday stop (low ≤ stop) | Exit at stop price → `STOP_LOSS` |
| 3 | Trend exit (close < EMA20) | Exit next day's open → `TREND_EXIT` |
| 4 | End of data | Exit at final close → `END_OF_DATA` |

---

## 7. Trade Statistics

| Metric | Value |
|--------|-------|
| Total LONG signals | 137 |
| Executed trades | 70 |
| Skipped signals | 67 |
| Winning trades | 23 |
| Losing trades | 47 |
| Win rate | 32.86% |
| Avg net P&L / trade | ₹-121.93 |
| Avg winning trade | ₹1293.59 |
| Avg losing trade | ₹-814.64 |
| Best trade | ₹4190.37 |
| Worst trade | ₹-1097.83 |
| Avg holding period | 21.84 days |

### Exit Reason Distribution

| Exit Reason | Count |
|-------------|-------|
| STOP_LOSS | 33 |
| TREND_EXIT | 37 |

---

## 8. Performance Metrics

| Metric | Value |
|--------|-------|
| Initial capital | ₹100,000.00 |
| Final equity | ₹91,464.71 |
| Total net P&L | ₹-8,535.29 |
| Total return | -8.54% |
| Profit factor | 0.78 |
| Exposure | 22.22% of trading days |

---

## 9. Drawdown

| Metric | Value |
|--------|-------|
| Maximum drawdown | -25.14% |

Maximum drawdown is calculated from the daily equity curve using the
standard peak-to-trough formula:
```
running_peak = cumulative max of equity
dd = (equity - running_peak) / running_peak
max_drawdown = min(dd) × 100%
```

---

## 10. Important Caveats

1. **This is a historical simulation.** It does not predict future returns.
2. **Survivorship bias is not controlled.** Only ITC data is used; it survived to 2025.
3. **Execution assumptions are simplified.** Real fills depend on order book depth,
   market impact, circuit breakers, and trading halts.
4. **Cost model uses research defaults.** Real NSE costs differ by broker and order type.
5. **No parameter optimization was performed.** The strategy parameters are exactly
   those defined in Sprint 2. Any apparent performance has not been validated
   out-of-sample.
6. **No benchmark comparison.** Sprint 3 does not include a buy-and-hold comparison.
   This will be added in Sprint 5 when NIFTY50 data is available.
7. **Single stock only.** Sprint 3 uses ITC exclusively. Multi-stock analysis is Sprint 5.
8. **Slippage and commissions are estimates.** The actual market impact of the
   simulated trades is unknown.

---

## 11. Reproduction

```bash
# Re-run this exact backtest
python -m quant.backtest

# With custom parameters
python -m quant.backtest --capital 100000 --risk-per-trade 0.01 \
    --slippage 0.0005 --commission 0.0005
```