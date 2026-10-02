# QuantEdge

**Historical Quantitative Research Platform — Sprints 1–6**

> This application is a **historical quantitative research interface**.
> It does not execute real trades, connect to any broker, or predict future returns.

---

## Sprint Roadmap

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 1 | Data Foundation | ✅ Complete |
| Sprint 2 | Quant / Feature Engine + Strategy | ✅ Complete |
| Sprint 3 | Backtesting Engine | ✅ Complete |
| Sprint 4 | Web Product | ✅ Complete |
| Sprint 5 | NSE / Multi-stock Data | ✅ Complete |
| Sprint 6 | Validation / Walk-forward Testing | ✅ Complete |
| Sprint 7 | AI Research | Planned |
| Sprint 8 | Paper Trading | Planned |

---

## Architecture

```
QuantEdge/
├── Data/
│   ├── raw/
│   │   ├── ITC Stock Price History.csv  ← Real ITC daily data (2005–2025, 5,000 rows)
│   │   └── stocks/
│   │       └── README.md               ← Instructions for placing new equity CSVs
│   ├── processed/
│   │   ├── stocks/                     ← Per-symbol canonical & feature outputs
│   │   │   ├── ITC.csv                 ← Canonical OHLCV (5,000 rows)
│   │   │   └── ITC_features.csv        ← Features + signals (5,000 rows)
│   │   ├── itc_daily_clean.csv         ← Backward-compatible legacy copy
│   │   └── itc_features.csv            ← Backward-compatible legacy copy
│   ├── backtests/
│   │   ├── ITC/                        ← Per-symbol backtest outputs
│   │   │   ├── summary.json            ← Key metrics (return, win rate, drawdown)
│   │   │   ├── trades.csv              ← 70-trade execution ledger
│   │   │   ├── equity_curve.csv        ← 5,000-row daily equity curve
│   │   │   └── report.md               ← Human-readable simulation report
│   │   └── itc_trend_momentum/         ← Backward-compatible legacy copy
│   └── reports/
│       ├── stocks/
│       │   ├── ITC_data_quality.json   ← Validation report JSON
│       │   └── ITC_data_quality.md     ← Validation report Markdown
│       ├── itc_data_quality.json       ← Backward-compatible legacy copy
│       └── itc_data_quality.md         ← Backward-compatible legacy copy
│
├── data/
│   └── validation/                     ← Walk-forward & robustness validation outputs
│       ├── ITC_splits.json             ← Chronological train/test window metadata
│       ├── ITC_walkforward.json        ← Per-window strategy & buy-and-hold metrics
│       ├── ITC_sensitivity.json        ← 11-config parameter sensitivity table
│       └── ITC_summary.json            ← Headline results & integrity gate audit
│
├── docs/
│   ├── sprint-2-quant-engine.md        ← Sprint 2 quant feature & strategy documentation
│   └── sprint-6-validation.md          ← Sprint 6 walk-forward & robustness audit report
│
├── quant/
│   ├── data/                           ← Data layer: ingestion, cleaning, validation, registry
│   │   ├── sources/                    ← Source abstraction (BaseSource, InvestingComSource)
│   │   ├── ingestion.py                ← Raw CSV loader and SHA-256 integrity verifier
│   │   ├── cleaning.py                 ← Deterministic cleaning & canonical normalization
│   │   ├── validation.py               ← OHLC consistency, volume, date monotonicity checks
│   │   ├── registry.py                 ← Symbol registry and path resolvers
│   │   └── pipeline.py                 ← Data CLI orchestrator (--symbol / --symbols)
│   ├── features/                       ← Feature engineering
│   │   ├── indicators.py               ← Pure mathematical indicators (EMA, SMA, ATR, Volume)
│   │   └── pipeline.py                 ← Feature CLI orchestrator (--symbol / --symbols)
│   ├── strategies/                     ← Trading strategies
│   │   └── trend_momentum.py           ← Daily Trend-Momentum Breakout logic
│   ├── backtest/                       ← Historical backtesting engine
│   │   ├── engine.py                   ← Lookahead-free execution, stops, exits, position sizing
│   │   ├── costs.py                    ← Commission (0.05%) and slippage (0.05%) models
│   │   ├── metrics.py                  ← Performance calculation (Sharpe, Drawdown, Profit Factor)
│   │   └── pipeline.py                 ← Backtest CLI orchestrator (--symbol / --symbols)
│   ├── validation/                     ← Walk-forward validation & robustness testing (Sprint 6)
│   │   ├── splitter.py                 ← Chronological expanding-window data splitter
│   │   ├── walk_forward.py             ← Walk-forward test engine (zero parameter fitting)
│   │   ├── benchmark.py                ← Buy-and-hold benchmark (same costs & constraints)
│   │   ├── sensitivity.py              ← 11-config parameter sensitivity variations
│   │   ├── gates.py                    ← 5 programmatic integrity & lookahead gates
│   │   ├── report.py                   ← Validation report generator (JSON & Markdown)
│   │   └── __main__.py                 ← CLI: python -m quant.validation --symbol ITC
│   └── api/                            ← FastAPI read-only research API
│       ├── main.py                     ← App entry point and CORS configuration
│       ├── schemas.py                  ← Pydantic response models
│       └── routes/                     ← stocks, backtests, data_quality, overview
│
├── frontend/                           ← React 19 + TypeScript + Vite web product
│   ├── src/
│   │   ├── App.tsx                     ← Parameterized routes (/stocks/:symbol, etc.)
│   │   ├── types/index.ts              ← TypeScript interfaces
│   │   ├── services/api.ts             ← Parameterized API client
│   │   ├── components/                 ← Layout, UI (StockSelector), Recharts graphs
│   │   └── pages/                      ← Overview, StockAnalysis, BacktestLab, TradeJournal, DataCenter
│   └── __tests__/                      ← Vitest frontend test suites
│
└── tests/                              ← Python test suite (294 tests)
    └── test_walk_forward.py            ← 21 validation & integrity tests (Sprint 6)
```

---

## Setup

### Python dependencies

```bash
pip install -r requirements.txt
```

### Node.js dependencies (frontend)

```bash
cd frontend
npm install
```

---

## Running the Pipelines

QuantEdge provides single-symbol and multi-symbol CLI entry points for every pipeline stage:

### 1. Data Foundation (Ingest, Clean, Validate)

```bash
# Single symbol
python -m quant.data.pipeline --symbol ITC

# Multiple symbols
python -m quant.data.pipeline --symbols ITC RELIANCE TCS
```

Outputs: `Data/processed/stocks/{SYMBOL}.csv`, `Data/reports/stocks/{SYMBOL}_data_quality.json`

### 2. Feature Engine (Indicators & Signals)

```bash
# Single symbol
python -m quant.features.pipeline --symbol ITC

# Multiple symbols
python -m quant.features.pipeline --symbols ITC RELIANCE TCS
```

Outputs: `Data/processed/stocks/{SYMBOL}_features.csv`

### 3. Backtesting Engine (Simulation & Performance)

```bash
# Single symbol
python -m quant.backtest --symbol ITC

# Multiple symbols
python -m quant.backtest --symbols ITC RELIANCE TCS
```

Outputs: `Data/backtests/{SYMBOL}/` (`summary.json`, `trades.csv`, `equity_curve.csv`, `report.md`)

### 4. Walk-Forward Validation & Robustness (Sprint 6)

```bash
# Run chronological walk-forward, buy-and-hold benchmark, and sensitivity analysis
python -m quant.validation --symbol ITC

# Optional arguments
python -m quant.validation --symbol ITC --initial-dev-years 3 --step-months 6 --test-months 6
```

Outputs:
- `data/validation/{SYMBOL}_splits.json`: Chronological window metadata (dev & unseen test ranges)
- `data/validation/{SYMBOL}_walkforward.json`: Per-window strategy & buy-and-hold benchmark metrics
- `data/validation/{SYMBOL}_sensitivity.json`: 11-config parameter sensitivity table
- `data/validation/{SYMBOL}_summary.json`: Headline numbers and 5 programmatic integrity gate results
- `docs/sprint-6-validation.md`: Comprehensive human-readable validation report

---

## Starting the Web Application

Two terminal windows are required:

### Terminal 1 — FastAPI backend (port 8000)

```bash
python -m uvicorn quant.api.main:app --reload --port 8000
```

API documentation: http://localhost:8000/api/docs

### Terminal 2 — Vite frontend (port 5173)

```bash
cd frontend
npm run dev
```

Application URL: **http://localhost:5173**

---

## Routes & Screens

| Route | Screen | Description |
|-------|--------|-------------|
| `/` | Research Overview | High-level dataset summary, strategy overview, and equity curve |
| `/stocks/:symbol` | Stock Analysis | Interactive price chart, technical overlays (EMA/SMA), volume, signals |
| `/backtest/:symbol` | Backtest Lab | Strategy rules, risk parameters, KPIs, exit breakdown |
| `/trades/:symbol` | Trade Journal | Filterable, sortable 70-trade execution ledger with trade modal |
| `/data/:symbol` | Data Center | Data provenance, validation audit status, and pipeline architecture |

---

## API Endpoints (All GET, Read-Only)

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Service liveness health check |
| `GET /api/stocks` | List of symbols with processed data available on disk |
| `GET /api/stocks/{symbol}` | Canonical OHLCV rows (`?from=YYYY-MM-DD&to=YYYY-MM-DD` optional) |
| `GET /api/stocks/{symbol}/features` | Features + signals rows (`?from=&to=` optional) |
| `GET /api/backtests/{symbol}` | Backtest performance metrics summary |
| `GET /api/backtests/{symbol}/trades` | Executed trade ledger for symbol |
| `GET /api/backtests/{symbol}/equity` | Full daily equity curve for symbol |
| `GET /api/data-quality/{symbol}` | Data validation report for symbol |
| `GET /api/overview` | Snapshot overview (`?symbol={symbol}` optional, defaults to ITC) |

*Path traversal protection: all symbol parameters are strictly validated against a known whitelist before any filesystem access.*

---

## Tests

### Python (pytest)

```bash
pytest tests/ -v
```

Expected: **294 passed** (10 test suites)
- `tests/test_backtest.py`: 50 passed
- `tests/test_cleaning.py`: 49 passed
- `tests/test_indicators.py`: 57 passed
- `tests/test_ingestion.py`: 14 passed
- `tests/test_strategy.py`: 34 passed
- `tests/test_validation.py`: 30 passed
- `tests/test_multistock.py`: 11 passed
- `tests/test_registry.py`: 18 passed
- `tests/test_sources.py`: 10 passed
- `tests/test_walk_forward.py`: 21 passed (Sprint 6 validation, lookahead gates & regression)

### Frontend (Vitest)

```bash
cd frontend
npm test
```

Expected: **28 passed** (4 test suites)
- `MetricCard.test.tsx`: 5 passed
- `StockSelector.test.tsx`: 6 passed
- `TradeTable.test.tsx`: 7 passed
- `Overview.test.tsx`: 10 passed

### Frontend Production Build

```bash
cd frontend
npm run build
```

Expected: `tsc -b && vite build` succeeds with 0 errors.

---

## Current Real-Data Situation

| Symbol | Status | Details |
|--------|--------|---------|
| **ITC** | **Real dataset available** | 5,000 daily bars (2005-04-01 to 2025-05-29) from Investing.com export |
| **RELIANCE** | Registered in `SYMBOL_REGISTRY` | Awaiting raw CSV file in `Data/raw/stocks/RELIANCE.csv` |
| **TCS** | Registered in `SYMBOL_REGISTRY` | Awaiting raw CSV file in `Data/raw/stocks/TCS.csv` |
| **INFY** | Registered in `SYMBOL_REGISTRY` | Awaiting raw CSV file in `Data/raw/stocks/INFY.csv` |
| **HDFCBANK** | Registered in `SYMBOL_REGISTRY` | Awaiting raw CSV file in `Data/raw/stocks/HDFCBANK.csv` |

*Note: QuantEdge enforces a strict zero-fabricated-data policy. No synthetic or mock data is ever presented as real market data.*

### ITC Historical Baseline Results

| Metric | Measured Baseline |
|--------|-------------------|
| Symbol | ITC |
| Date range | 2005-04-01 → 2025-05-29 |
| Rows | 5,000 |
| Strategy | Daily Trend-Momentum Breakout |
| Signals | 137 LONG |
| Trades executed | 70 |
| Initial capital | ₹1,00,000.00 |
| Final equity | ₹91,464.71 |
| Total return | **−8.54%** |
| Win rate | 32.9% (32.86%) |
| Profit factor | 0.777 |
| Max drawdown | −25.14% |
| Avg holding days | 21.84 days |

---

## Current Limitations

- Only one real historical stock dataset (`ITC`) is currently present on disk. Additional symbols can be added by placing their CSV in `Data/raw/stocks/` and executing the pipeline.
- Offline historical quantitative simulation only. No live market feed, real-time streaming, or broker execution.
- Strategy parameters are display-only and cannot be modified from the UI.
- Walk-forward testing and out-of-sample validation have been completed for available data (ITC, 35 windows, 11-config sensitivity analysis). Additional symbols will undergo validation as their historical datasets are added.
- Price chart utilizes Recharts line/area plots for close prices and moving averages rather than full OHLC candlestick glyphs.

---

## Important Disclaimer

**QuantEdge is a historical quantitative research interface.
It does not execute real trades, connect to any broker, predict future returns,
or provide investment advice. Past simulation results do not guarantee future performance.**
