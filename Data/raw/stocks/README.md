# QuantEdge — Raw Stock Data

This directory (`Data/raw/stocks/`) stores raw historical CSV files for
NSE equities in **Investing.com export format**.

## Currently Available

| Symbol | File | Status |
|--------|------|--------|
| ITC    | `../ITC Stock Price History.csv` | REAL DATA (legacy path) |

## Adding a New Symbol

1. Download the historical data CSV from [Investing.com](https://investing.com).
   - Navigate to the stock page (e.g. Reliance Industries)
   - Click "Historical Data" tab
   - Set date range and click "Download"

2. Place the file here as `{SYMBOL}.csv`, e.g.:
   - `RELIANCE.csv`
   - `TCS.csv`
   - `INFY.csv`
   - `HDFCBANK.csv`

3. Verify the file has the expected columns:
   ```
   Date, Price, Open, High, Low, Vol., Change %
   ```

4. Run the pipeline:
   ```bash
   python -m quant.data.pipeline --symbol RELIANCE
   python -m quant.features.pipeline --symbol RELIANCE
   python -m quant.backtest --symbol RELIANCE
   ```

5. The symbol will then appear automatically in `GET /api/stocks` and the UI.

## Important

- **DO NOT fabricate or modify historical price data.**
- **DO NOT commit real market data files to git** (add to .gitignore).
- Data files should be treated as proprietary research inputs.

## Supported Symbols (registry)

The following symbols are defined in `quant/data/registry.py`.
They will only appear in the application when their data files are present.

- ITC (ITC Ltd)
- RELIANCE (Reliance Industries Ltd)
- TCS (Tata Consultancy Services Ltd)
- INFY (Infosys Ltd)
- HDFCBANK (HDFC Bank Ltd)
