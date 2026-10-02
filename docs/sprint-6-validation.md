# QuantEdge Sprint 6 — Validation Report [ITC]

**Generated:** 2026-09-28 11:51:28

> [!CAUTION]
> This is a **historical simulation only**. Past validation results do NOT
> guarantee future performance. This report does NOT constitute investment advice.

---

## 1. Integrity Gates

**Status:** ✅ PASSED

---

## 2. Full-Dataset Baseline (ITC Regression)

| Metric | Strategy | Buy-and-Hold |
|--------|----------|--------------|
| Initial capital | ₹100,000.00 | ₹100,000.00 |
| Final equity | ₹91,464.71 | ₹1,417,260.66 |
| Total return | -8.54% | 1317.26% |
| Trades executed | 70 | 1 |
| Win rate | 32.86% | N/A |
| Profit factor | 0.78 | N/A |
| Max drawdown | -25.14% | N/A |

---

## 3. Walk-Forward Validation Summary

- **Total windows generated:** 35
- **Windows with trades (OK):** 30
- **Windows with zero trades:** 4
- **Windows with insufficient data:** 1

- **Average strategy return per test window (OK windows):** -0.45%
- **Average buy-and-hold return per test window:** 8.51%
- **% of OK windows where strategy was profitable:** 26.7%

---

## 4. Walk-Forward Window Results

| Window | Test Start | Test End | Rows | Trades | Return % | B&H % | Excess % | Status |
|--------|------------|----------|------|--------|----------|-------|----------|--------|
| 0 | 2008-04-01 | 2008-10-01 | 126 | 1 | -1.02 | -7.68 | 6.66 | OK |
| 1 | 2008-10-01 | 2009-04-01 | 119 | 1 | -0.07 | -3.16 | 3.09 | OK |
| 2 | 2009-04-01 | 2009-10-01 | 124 | 2 | 1.03 | 25.38 | -24.35 | OK |
| 3 | 2009-10-01 | 2010-04-01 | 122 | 2 | -2.03 | 13.23 | -15.26 | OK |
| 4 | 2010-04-01 | 2010-10-01 | 129 | 4 | -1.04 | 35.09 | -36.13 | OK |
| 5 | 2010-10-01 | 2011-04-01 | 127 | 2 | -0.27 | 1.81 | -2.08 | OK |
| 6 | 2011-04-01 | 2011-09-30 | 125 | 3 | -1.56 | 8.55 | -10.11 | OK |
| 7 | 2011-10-03 | 2012-03-30 | 124 | 3 | -1.12 | 15.93 | -17.05 | OK |
| 8 | 2012-04-02 | 2012-10-01 | 127 | 2 | -2.06 | 19.90 | -21.96 | OK |
| 9 | 2012-10-01 | 2013-04-01 | 124 | 3 | -1.59 | 12.92 | -14.51 | OK |
| 10 | 2013-04-01 | 2013-10-01 | 127 | 3 | -1.27 | 10.77 | -12.04 | OK |
| 11 | 2013-10-01 | 2014-04-01 | 126 | 1 | 1.31 | 3.20 | -1.89 | OK |
| 12 | 2014-04-01 | 2014-10-01 | 124 | 1 | -0.49 | 2.79 | -3.28 | OK |
| 13 | 2014-10-01 | 2015-04-01 | 121 | 3 | -3.05 | -10.32 | 7.27 | OK |
| 14 | 2015-04-01 | 2015-10-01 | 126 | 0 | 0.00 | 0.69 | -0.69 | ZERO_TRADES |
| 15 | 2015-10-01 | 2016-04-01 | 123 | 0 | 0.00 | 2.54 | -2.54 | ZERO_TRADES |
| 16 | 2016-04-01 | 2016-09-30 | 124 | 2 | 0.33 | 11.41 | -11.09 | OK |
| 17 | 2016-10-03 | 2017-03-31 | 124 | 2 | -0.04 | 14.55 | -14.59 | OK |
| 18 | 2017-04-03 | 2017-09-29 | 124 | 3 | -2.02 | -8.84 | 6.82 | OK |
| 19 | 2017-10-03 | 2018-03-28 | 122 | 1 | -0.43 | -2.86 | 2.43 | OK |
| 20 | 2018-04-02 | 2018-10-01 | 126 | 2 | 1.69 | 15.34 | -13.66 | OK |
| 21 | 2018-10-01 | 2019-04-01 | 124 | 1 | -1.04 | -1.39 | 0.36 | OK |
| 22 | 2019-04-01 | 2019-10-01 | 123 | 1 | -1.04 | -14.00 | 12.95 | OK |
| 23 | 2019-10-01 | 2020-04-01 | 126 | 0 | 0.00 | -35.85 | 35.85 | ZERO_TRADES |
| 24 | 2020-04-01 | 2020-10-01 | 126 | 2 | -1.38 | -0.69 | -0.69 | OK |
| 25 | 2020-10-01 | 2021-04-01 | 125 | 4 | -4.02 | 25.83 | -29.85 | OK |
| 26 | 2021-04-01 | 2021-10-01 | 125 | 3 | -1.85 | 6.76 | -8.61 | OK |
| 27 | 2021-10-01 | 2022-04-01 | 125 | 2 | 0.43 | 7.47 | -7.04 | OK |
| 28 | 2022-04-01 | 2022-09-30 | 125 | 3 | 1.90 | 31.76 | -29.86 | OK |
| 29 | 2022-10-03 | 2023-03-31 | 124 | 1 | -0.29 | 8.77 | -9.05 | OK |
| 30 | 2023-04-03 | 2023-09-29 | 123 | 1 | 4.81 | 16.17 | -11.36 | OK |
| 31 | 2023-10-03 | 2024-04-01 | 124 | 1 | -0.33 | -3.43 | 3.10 | OK |
| 32 | 2024-04-01 | 2024-10-01 | 126 | 2 | 3.09 | 20.05 | -16.96 | OK |
| 33 | 2024-10-01 | 2025-04-01 | 125 | 0 | 0.00 | -17.14 | 17.14 | ZERO_TRADES |
| 34 | 2025-04-01 | 2025-05-29 | 39 | 0 | 0.00 | 0.00 | 0.00 | INSUFFICIENT_DATA |

---

## 5. Sensitivity Analysis

Small parameter variations around the baseline. No optimization. Results are presented as-is.

| Parameter | Value | Baseline? | Trades | Return % | Win Rate % | Profit Factor | Max DD % |
|-----------|-------|-----------|--------|----------|------------|---------------|----------|
| risk_per_trade | 0.005 |  | 70 | -4.19 | 32.86 | 0.79 | -13.38 |
| risk_per_trade | 0.01 | ✓ | 70 | -8.54 | 32.86 | 0.78 | -25.14 |
| risk_per_trade | 0.015 |  | 70 | -13.00 | 32.86 | 0.77 | -35.35 |
| risk_per_trade | 0.02 |  | 70 | -17.37 | 32.86 | 0.76 | -44.20 |
| atr_multiplier | 1.5 |  | 72 | -9.28 | 29.17 | 0.80 | -28.78 |
| atr_multiplier | 2.0 | ✓ | 70 | -8.54 | 32.86 | 0.78 | -25.14 |
| atr_multiplier | 2.5 |  | 70 | -7.55 | 32.86 | 0.76 | -21.67 |
| atr_multiplier | 3.0 |  | 70 | -5.76 | 32.86 | 0.78 | -17.94 |
| commission_rate | 0.0005 | ✓ | 70 | -8.54 | 32.86 | 0.78 | -25.14 |
| commission_rate | 0.001 |  | 70 | -9.94 | 32.86 | 0.74 | -26.04 |
| commission_rate | 0.002 |  | 70 | -12.67 | 30.00 | 0.69 | -27.81 |

---

## 6. Methodology Notes

- **Strategy:** Daily Trend-Momentum Breakout (rule-based, unchanged from Sprint 2).
- **Data split:** Development 2005–2017 / Validation 2018–2021 / Out-of-Sample 2022–2025.
- **Walk-forward:** Expanding development window, 6-month unseen test steps.
- **Feature handling:** Pre-computed `ITC_features.csv` (Approach A). All indicators are causal — truncation-invariance verified by automated tests.
- **Benchmark:** Buy-and-hold: buy at first-row open, sell at last-row close, same costs.
- **Parameters:** Fixed throughout. No parameter fitting or optimization.
- **Transaction costs:** Commission 0.05% + slippage 0.05% per side (both entry and exit).
- **Integrity gates:** 5 programmatic checks must all pass before results are published.

---

*End of Sprint 6 Validation Report.*
