"""
quant/api/routes/backtests.py
------------------------------
Sprint 5: Generalized backtest endpoints.

GET /api/backtests/{symbol}        -> backtest summary
GET /api/backtests/{symbol}/trades -> trade ledger
GET /api/backtests/{symbol}/equity -> equity curve
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, HTTPException

from quant.api.schemas import BacktestSummary, TradeRow, EquityCurveRow
from quant.data.registry import (
    get_backtest_dir,
    VALID_SYMBOLS,
)

router = APIRouter(tags=["backtests"])


def _validate_symbol(symbol: str) -> Path:
    """
    Validate symbol and return its backtest directory.

    Raises 404 for unknown symbols, 503 if backtest data not found.
    """
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' is not recognised. Known symbols: {sorted(VALID_SYMBOLS)}.",
        )
    bt_dir = get_backtest_dir(symbol)
    if not bt_dir.exists() or not (bt_dir / "summary.json").exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Backtest data for '{symbol}' not found. "
                f"Run 'python -m quant.backtest --symbol {symbol}' first."
            ),
        )
    return bt_dir


@router.get("/backtests/{symbol}", response_model=BacktestSummary)
def get_backtest_summary(symbol: str) -> BacktestSummary:
    """Return the backtest performance summary for a symbol."""
    bt_dir = _validate_symbol(symbol)
    path = bt_dir / "summary.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return BacktestSummary(**data)


@router.get("/backtests/{symbol}/trades", response_model=list[TradeRow])
def get_backtest_trades(symbol: str) -> list[TradeRow]:
    """Return all executed historical trades for a symbol."""
    bt_dir = _validate_symbol(symbol)
    path = bt_dir / "trades.csv"
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"trades.csv not found for {symbol}.")
    df = pd.read_csv(path)
    rows = []
    for _, r in df.iterrows():
        rows.append(TradeRow(
            trade_id=int(r["trade_id"]),
            symbol=str(r["symbol"]),
            signal_date=str(r["signal_date"]),
            entry_date=str(r["entry_date"]),
            entry_reference_price=float(r["entry_reference_price"]),
            entry_price=float(r["entry_price"]),
            initial_stop=float(r["initial_stop"]),
            atr_at_signal=float(r["atr_at_signal"]),
            quantity=int(r["quantity"]),
            risk_budget=float(r["risk_budget"]),
            exit_date=str(r["exit_date"]),
            exit_reference_price=float(r["exit_reference_price"]),
            exit_price=float(r["exit_price"]),
            exit_reason=str(r["exit_reason"]),
            gross_pnl=float(r["gross_pnl"]),
            transaction_cost=float(r["transaction_cost"]),
            net_pnl=float(r["net_pnl"]),
            return_pct=float(r["return_pct"]),
            r_multiple=float(r["r_multiple"]),
            holding_days=int(r["holding_days"]),
        ))
    return rows


@router.get("/backtests/{symbol}/equity", response_model=list[EquityCurveRow])
def get_equity_curve(symbol: str) -> list[EquityCurveRow]:
    """Return the full daily equity curve for a symbol."""
    bt_dir = _validate_symbol(symbol)
    path = bt_dir / "equity_curve.csv"
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"equity_curve.csv not found for {symbol}.")
    df = pd.read_csv(path)
    return [
        EquityCurveRow(
            date=str(r["date"]),
            cash=float(r["cash"]),
            position_quantity=int(r["position_quantity"]),
            position_market_value=float(r["position_market_value"]),
            equity=float(r["equity"]),
        )
        for _, r in df.iterrows()
    ]
