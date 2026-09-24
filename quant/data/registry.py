"""
quant/data/registry.py
-----------------------
Symbol registry for QuantEdge Sprint 5.

This module is the single source of truth for:
  - Which symbols are defined (SYMBOL_REGISTRY)
  - Where their raw source files live
  - Where their processed outputs are written
  - Which symbols have data actually available on disk

Usage
-----
::

    from quant.data.registry import get_raw_path, get_available_symbols

    path = get_raw_path("ITC")
    symbols = get_available_symbols()   # only symbols with processed data

Design
------
ITC retains its legacy file paths (itc_daily_clean.csv, etc.) for full
backward compatibility with Sprint 1-4 outputs and the existing API routes.
Additional symbols use the new Data/processed/stocks/ layout.

DO NOT add symbols with fabricated market data.
Only add symbols when real historical CSV files are available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent   # quant/data/registry.py -> ../../

DATA_ROOT = PROJECT_ROOT / "Data"


# ---------------------------------------------------------------------------
# SymbolConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolConfig:
    """Configuration for one NSE equity symbol."""

    symbol: str
    raw_file: str        # Filename under Data/raw/ or Data/raw/stocks/
    source: str          # Source name ("InvestingCom" etc.)
    description: str     # Human-readable label


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SYMBOL_REGISTRY: dict[str, SymbolConfig] = {
    "ITC": SymbolConfig(
        symbol="ITC",
        raw_file="ITC Stock Price History.csv",
        source="InvestingCom",
        description="ITC Ltd — NSE (ITC.NS)",
    ),
    # -----------------------------------------------------------------
    # The following symbols are defined in the registry but are NOT
    # currently available because real historical CSV data has not been
    # supplied. They will appear in the API / UI only when their raw
    # files are placed in Data/raw/stocks/ and the pipeline is run.
    #
    # To add a symbol:
    #   1. Obtain the Investing.com historical CSV for that symbol.
    #   2. Place it at Data/raw/stocks/{SYMBOL}.csv
    #   3. Run: python -m quant.data.pipeline --symbol {SYMBOL}
    #   4. Run: python -m quant.features.pipeline --symbol {SYMBOL}
    #   5. Run: python -m quant.backtest --symbol {SYMBOL}
    # -----------------------------------------------------------------
    "RELIANCE": SymbolConfig(
        symbol="RELIANCE",
        raw_file="RELIANCE.csv",
        source="InvestingCom",
        description="Reliance Industries Ltd — NSE (RELIANCE.NS)",
    ),
    "TCS": SymbolConfig(
        symbol="TCS",
        raw_file="TCS.csv",
        source="InvestingCom",
        description="Tata Consultancy Services Ltd — NSE (TCS.NS)",
    ),
    "INFY": SymbolConfig(
        symbol="INFY",
        raw_file="INFY.csv",
        source="InvestingCom",
        description="Infosys Ltd — NSE (INFY.NS)",
    ),
    "HDFCBANK": SymbolConfig(
        symbol="HDFCBANK",
        raw_file="HDFCBANK.csv",
        source="InvestingCom",
        description="HDFC Bank Ltd — NSE (HDFCBANK.NS)",
    ),
}

# The complete set of defined symbols (not all have data yet).
VALID_SYMBOLS: frozenset[str] = frozenset(SYMBOL_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_raw_path(symbol: str) -> Path:
    """
    Return the path to the raw source CSV for *symbol*.

    ITC uses the original legacy path for backward compatibility.
    All other symbols use Data/raw/stocks/{SYMBOL}.csv.

    Raises
    ------
    KeyError
        If *symbol* is not in the registry.
    """
    cfg = _require(symbol)
    if symbol == "ITC":
        # Legacy location — Sprint 1 original file.
        return DATA_ROOT / "raw" / cfg.raw_file
    return DATA_ROOT / "raw" / "stocks" / cfg.raw_file


def get_processed_path(symbol: str) -> Path:
    """
    Return the path to the canonical clean CSV for *symbol*.

    ITC writes to Data/processed/stocks/ITC.csv (the old itc_daily_clean.csv
    is kept untouched for Sprint 1-4 backward compat).

    Raises
    ------
    KeyError
        If *symbol* is not in the registry.
    """
    _require(symbol)
    return DATA_ROOT / "processed" / "stocks" / f"{symbol}.csv"


def get_features_path(symbol: str) -> Path:
    """
    Return the path to the feature-enriched CSV for *symbol*.

    Raises
    ------
    KeyError
        If *symbol* is not in the registry.
    """
    _require(symbol)
    return DATA_ROOT / "processed" / "stocks" / f"{symbol}_features.csv"


def get_backtest_dir(symbol: str) -> Path:
    """
    Return the backtest output directory for *symbol*.

    Raises
    ------
    KeyError
        If *symbol* is not in the registry.
    """
    _require(symbol)
    return DATA_ROOT / "backtests" / symbol


def get_quality_report_paths(symbol: str) -> tuple[Path, Path]:
    """
    Return (json_path, md_path) for the data quality report for *symbol*.

    Raises
    ------
    KeyError
        If *symbol* is not in the registry.
    """
    _require(symbol)
    base = DATA_ROOT / "reports" / "stocks"
    return base / f"{symbol}_data_quality.json", base / f"{symbol}_data_quality.md"


def get_available_symbols() -> list[str]:
    """
    Return the list of symbols whose processed CSV files exist on disk.

    Only these symbols appear in the API and UI.
    Returns an empty list if no processed data exists.
    The list is sorted alphabetically for determinism.
    """
    available = []
    for sym in sorted(SYMBOL_REGISTRY):
        processed = get_processed_path(sym)
        if processed.exists():
            available.append(sym)
    return available


def get_symbol_config(symbol: str) -> SymbolConfig:
    """
    Return the SymbolConfig for *symbol*.

    Raises
    ------
    KeyError
        If *symbol* is not in the registry.
    """
    return _require(symbol)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require(symbol: str) -> SymbolConfig:
    if symbol not in SYMBOL_REGISTRY:
        raise KeyError(
            f"Symbol '{symbol}' is not in the QuantEdge registry. "
            f"Known symbols: {sorted(SYMBOL_REGISTRY)}."
        )
    return SYMBOL_REGISTRY[symbol]
