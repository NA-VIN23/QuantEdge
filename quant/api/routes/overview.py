"""
quant/api/routes/overview.py
-----------------------------
Sprint 5: Updated overview endpoint supporting optional symbol query param.

GET /api/overview           -> ITC overview (default, backward compat)
GET /api/overview?symbol=X  -> Overview for symbol X
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from quant.api.schemas import OverviewResponse, StockMeta, BacktestSummary
from quant.data.registry import (
    get_features_path,
    get_backtest_dir,
    VALID_SYMBOLS,
    get_available_symbols,
)

router = APIRouter(tags=["overview"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    symbol: Optional[str] = Query(None, description="NSE symbol (defaults to ITC)"),
) -> OverviewResponse:
    """
    Merged snapshot of the current research state for one symbol.
    Defaults to ITC for backward compatibility.
    """
    sym = (symbol or "ITC").upper()

    if sym not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{sym}' is not recognised.",
        )

    features_path = get_features_path(sym)
    summary_path  = get_backtest_dir(sym) / "summary.json"

    try:
        feat = pd.read_csv(features_path, usecols=["date", "signal"])
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"Feature data for '{sym}' not found. Run the feature pipeline first.",
        )

    try:
        with open(summary_path, encoding="utf-8") as f:
            summary_raw = json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"Backtest data for '{sym}' not found. Run the backtest pipeline first.",
        )

    dataset = StockMeta(
        symbol=sym,
        date_min=str(feat["date"].min()),
        date_max=str(feat["date"].max()),
        row_count=len(feat),
        columns=list(pd.read_csv(features_path, nrows=0).columns),
    )

    num_signals = int((feat["signal"] == "LONG").sum())
    summary = BacktestSummary(**summary_raw)

    return OverviewResponse(
        dataset=dataset,
        strategy_name="Daily Trend-Momentum Breakout",
        num_signals=num_signals,
        backtest=summary,
    )
