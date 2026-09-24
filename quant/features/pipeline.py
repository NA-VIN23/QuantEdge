"""
quant/features/pipeline.py
---------------------------
Sprint 5: Generalized feature engineering pipeline for QuantEdge.

Sprint 2 legacy: zero-arg call still works for ITC backward compat.

Entry points:
    python -m quant.features.pipeline                      # ITC (legacy)
    python -m quant.features.pipeline --symbol ITC
    python -m quant.features.pipeline --symbols ITC RELIANCE TCS

Sequence (per symbol):
    1. Load Data/processed/stocks/{SYMBOL}.csv
    2. Validate expected input columns
    3. Sort by date (defensive)
    4. Compute all technical features (indicators.py)
    5. Apply strategy signals (trend_momentum.py)
    6. Write Data/processed/stocks/{SYMBOL}_features.csv

The same indicator formulas and strategy rules are applied to every symbol.
No symbol-specific logic exists in this pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

from quant.features.indicators import (
    REQUIRED_INPUT_COLUMNS,
    FEATURE_COLUMNS,
    compute_all_features,
)
from quant.strategies.trend_momentum import (
    apply_strategy,
    CONDITION_COLUMNS,
    SIGNAL_LONG,
    SIGNAL_NONE,
)
from quant.data.registry import (
    get_processed_path,
    get_features_path,
    SYMBOL_REGISTRY,
)


# ---------------------------------------------------------------------------
# Legacy ITC paths (Sprint 2 backward compat — NOT used by new pipeline)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent

CLEAN_CSV    = PROJECT_ROOT / "Data" / "processed" / "itc_daily_clean.csv"
FEATURES_CSV = PROJECT_ROOT / "Data" / "processed" / "itc_features.csv"


# ---------------------------------------------------------------------------
# Column ordering for output CSV
# ---------------------------------------------------------------------------

OUTPUT_COLUMNS: list[str] = (
    REQUIRED_INPUT_COLUMNS
    + FEATURE_COLUMNS
    + CONDITION_COLUMNS
    + ["signal"]
)


# ---------------------------------------------------------------------------
# Public pipeline function
# ---------------------------------------------------------------------------


def run_pipeline(
    symbol: str = "ITC",
    clean_csv: Optional[Path] = None,
    features_csv: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Execute the feature pipeline for one symbol.

    Parameters
    ----------
    symbol : str
        NSE equity symbol. Defaults to "ITC".
    clean_csv : Path, optional
        Override the input canonical CSV path. Uses registry default if None.
    features_csv : Path, optional
        Override the output features CSV path. Uses registry default if None.

    Returns
    -------
    pd.DataFrame
        The complete feature DataFrame written to disk.
    """
    # Resolve paths.
    if clean_csv is None:
        clean_csv = get_processed_path(symbol)
    if features_csv is None:
        features_csv = get_features_path(symbol)

    print("=" * 60)
    print(f"QuantEdge -- Feature Pipeline  [{symbol}]")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load canonical CSV
    # ------------------------------------------------------------------
    print(f"\n[1/4] Loading: {clean_csv}")
    if not clean_csv.exists():
        print(f"  [!!] File not found: {clean_csv}")
        print(f"  Run 'python -m quant.data.pipeline --symbol {symbol}' first.")
        sys.exit(1)

    df = pd.read_csv(clean_csv, parse_dates=["date"])
    print(f"      Rows loaded : {len(df)}")
    print(f"      Columns     : {list(df.columns)}")

    # ------------------------------------------------------------------
    # 2. Validate input columns
    # ------------------------------------------------------------------
    missing_cols = [c for c in REQUIRED_INPUT_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"  [!!] Missing required columns: {missing_cols}")
        sys.exit(1)

    # Confirm symbol in the data matches what was requested.
    if "symbol" in df.columns:
        actual_symbols = df["symbol"].unique().tolist()
        if len(actual_symbols) > 1:
            print(f"  [!!] Multiple symbols in input: {actual_symbols}. Expected only {symbol}.")
            sys.exit(1)

    # ------------------------------------------------------------------
    # 3. Sort by date (defensive)
    # ------------------------------------------------------------------
    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 4. Compute features
    # ------------------------------------------------------------------
    print("\n[2/4] Computing features...")
    df_features = compute_all_features(df)
    print(f"      Features added: {FEATURE_COLUMNS}")

    # ------------------------------------------------------------------
    # 5. Apply strategy
    # ------------------------------------------------------------------
    print("\n[3/4] Applying strategy: Daily Trend-Momentum Breakout...")
    df_signals = apply_strategy(df_features)

    long_count = int((df_signals["signal"] == SIGNAL_LONG).sum())
    none_count = int((df_signals["signal"] == SIGNAL_NONE).sum())
    print(f"      LONG signals   : {long_count}")
    print(f"      NO_SIGNAL rows : {none_count}")

    if long_count > 0:
        first_long = df_signals.loc[df_signals["signal"] == SIGNAL_LONG, "date"].iloc[0]
        last_long  = df_signals.loc[df_signals["signal"] == SIGNAL_LONG, "date"].iloc[-1]
        print(f"      First LONG     : {first_long}")
        print(f"      Last LONG      : {last_long}")

    # ------------------------------------------------------------------
    # 6. Write output CSV
    # ------------------------------------------------------------------
    print(f"\n[4/4] Writing -> {features_csv}")
    features_csv.parent.mkdir(parents=True, exist_ok=True)

    df_out = df_signals[OUTPUT_COLUMNS].copy()
    df_out.to_csv(features_csv, index=False)
    print(f"      Rows written : {len(df_out)}")
    print(f"      Columns      : {len(df_out.columns)}")

    print("\n" + "=" * 60)
    print(f"Feature pipeline complete [{symbol}].")
    print("=" * 60)

    return df_out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="QuantEdge Feature Pipeline -- compute indicators and strategy signals.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--symbol",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Process a single symbol (e.g. ITC).",
    )
    group.add_argument(
        "--symbols",
        nargs="+",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Process multiple symbols (e.g. ITC RELIANCE TCS).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.symbols:
        symbols = args.symbols
    elif args.symbol:
        symbols = [args.symbol]
    else:
        symbols = ["ITC"]  # legacy default

    for sym in symbols:
        try:
            run_pipeline(symbol=sym)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"\n[!!] Feature pipeline failed for {sym}: {exc}")
            sys.exit(1)
