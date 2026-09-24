"""
quant/api/routes/stocks.py
--------------------------
Sprint 5: Generalized stock data endpoints.

GET /api/stocks                     -> list of available symbols
GET /api/stocks/{symbol}            -> OHLCV rows
GET /api/stocks/{symbol}/features   -> feature + signal rows
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from quant.api.schemas import OHLCVRow, FeatureRow, StockMeta, StockListItem
from quant.data.registry import (
    get_processed_path,
    get_features_path,
    get_available_symbols,
    get_symbol_config,
    SYMBOL_REGISTRY,
    VALID_SYMBOLS,
)

router = APIRouter(tags=["stocks"])


def _nan_to_none(val):
    """Convert float NaN to None for JSON serialisation."""
    if isinstance(val, float) and math.isnan(val):
        return None
    return val


def _validate_symbol(symbol: str) -> None:
    """
    Validate a symbol against the registry and check data exists.

    Raises
    ------
    HTTPException 404
        If symbol is not in the registry.
    HTTPException 503
        If symbol is registered but has no processed data on disk.
    """
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' is not recognised. Known symbols: {sorted(VALID_SYMBOLS)}.",
        )
    processed = get_processed_path(symbol)
    if not processed.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Data for symbol '{symbol}' is not available. "
                f"Run 'python -m quant.data.pipeline --symbol {symbol}' to ingest data."
            ),
        )


@router.get("/stocks", response_model=list[StockListItem])
def list_stocks() -> list[StockListItem]:
    """
    Return the list of symbols with processed data available on disk.

    Only symbols that have been processed through the data pipeline
    will appear in this list. Symbols defined in the registry but
    without data files are excluded.
    """
    available = get_available_symbols()
    result = []
    for sym in available:
        cfg = get_symbol_config(sym)
        result.append(StockListItem(symbol=sym, description=cfg.description))
    return result


@router.get("/stocks/{symbol}", response_model=list[OHLCVRow])
def get_stock_ohlcv(
    symbol: str,
    from_date: Optional[str] = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    to_date:   Optional[str] = Query(None, alias="to",   description="End date YYYY-MM-DD"),
) -> list[OHLCVRow]:
    """
    Return OHLCV rows for a specific symbol.
    Optional ?from=YYYY-MM-DD&to=YYYY-MM-DD date filters.
    """
    symbol = symbol.upper()
    _validate_symbol(symbol)

    processed_path = get_processed_path(symbol)
    try:
        df = pd.read_csv(processed_path)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read data for {symbol}: {exc}")

    if from_date:
        df = df[df["date"] >= from_date]
    if to_date:
        df = df[df["date"] <= to_date]

    return [
        OHLCVRow(
            date=str(row["date"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for _, row in df.iterrows()
    ]


@router.get("/stocks/{symbol}/features", response_model=list[FeatureRow])
def get_stock_features(
    symbol: str,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date:   Optional[str] = Query(None, alias="to"),
) -> list[FeatureRow]:
    """
    Return feature + signal rows for a specific symbol.
    """
    symbol = symbol.upper()
    _validate_symbol(symbol)

    features_path = get_features_path(symbol)
    if not features_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Feature data for '{symbol}' not found. "
                f"Run 'python -m quant.features.pipeline --symbol {symbol}' first."
            ),
        )

    try:
        df = pd.read_csv(features_path)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read features for {symbol}: {exc}")

    if from_date:
        df = df[df["date"] >= from_date]
    if to_date:
        df = df[df["date"] <= to_date]

    rows = []
    for _, r in df.iterrows():
        rows.append(FeatureRow(
            date=str(r["date"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            ema20=_nan_to_none(r["ema20"]),
            ema50=_nan_to_none(r["ema50"]),
            sma20=_nan_to_none(r.get("sma20")),
            sma50=_nan_to_none(r.get("sma50")),
            atr14=_nan_to_none(r.get("atr14")),
            avg_volume_20=_nan_to_none(r.get("avg_volume_20")),
            volume_ratio=_nan_to_none(r.get("volume_ratio")),
            momentum_5=_nan_to_none(r.get("momentum_5")),
            momentum_20=_nan_to_none(r.get("momentum_20")),
            trend_condition=bool(r["trend_condition"]),
            price_condition=bool(r["price_condition"]),
            breakout_condition=bool(r["breakout_condition"]),
            volume_condition=bool(r["volume_condition"]),
            signal=str(r["signal"]),
        ))
    return rows
