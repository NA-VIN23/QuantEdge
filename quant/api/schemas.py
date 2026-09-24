"""
quant/api/schemas.py
--------------------
Pydantic response models for the QuantEdge Research API.

All models are read-only representations of Sprint 1-3 outputs.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Stock / OHLCV
# ---------------------------------------------------------------------------

class OHLCVRow(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class FeatureRow(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    ema20: Optional[float]
    ema50: Optional[float]
    sma20: Optional[float]
    sma50: Optional[float]
    atr14: Optional[float]
    avg_volume_20: Optional[float]
    volume_ratio: Optional[float]
    momentum_5: Optional[float]
    momentum_20: Optional[float]
    trend_condition: bool
    price_condition: bool
    breakout_condition: bool
    volume_condition: bool
    signal: str


class StockMeta(BaseModel):
    symbol: str
    date_min: str
    date_max: str
    row_count: int
    columns: list[str]


class StockListItem(BaseModel):
    """One entry in the GET /api/stocks response."""
    symbol: str
    description: str


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------

class BacktestSummary(BaseModel):
    initial_capital: float
    final_equity: float
    total_net_pnl: float
    total_return_pct: float
    num_signals_total: int
    num_signals_executed: int
    num_signals_skipped: int
    num_trades: int
    num_wins: int
    num_losses: int
    win_rate: Optional[float]
    avg_net_pnl: Optional[float]
    avg_win_pnl: Optional[float]
    avg_loss_pnl: Optional[float]
    profit_factor: Optional[float]
    max_drawdown_pct: float
    avg_holding_days: Optional[float]
    exposure_pct: float
    best_trade_net_pnl: Optional[float]
    worst_trade_net_pnl: Optional[float]
    exit_reason_counts: dict[str, int]
    skip_reason_counts: dict[str, int]
    backtest_config: dict[str, Any]


class TradeRow(BaseModel):
    trade_id: int
    symbol: str
    signal_date: str
    entry_date: str
    entry_reference_price: float
    entry_price: float
    initial_stop: float
    atr_at_signal: float
    quantity: int
    risk_budget: float
    exit_date: str
    exit_reference_price: float
    exit_price: float
    exit_reason: str
    gross_pnl: float
    transaction_cost: float
    net_pnl: float
    return_pct: float
    r_multiple: float
    holding_days: int


class EquityCurveRow(BaseModel):
    date: str
    cash: float
    position_quantity: int
    position_market_value: float
    equity: float


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

class OverviewResponse(BaseModel):
    dataset: StockMeta
    strategy_name: str
    num_signals: int
    backtest: BacktestSummary


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

class DataQualityReport(BaseModel):
    source_filename: str
    symbol: str
    original_row_count: int
    final_row_count: int
    removed_row_count: int
    date_min: str
    date_max: str
    missing_counts: dict[str, int]
    duplicate_exact_count: int
    duplicate_date_count: int
    invalid_ohlc_count: int
    invalid_volume_count: int
    zero_volume_count: int
    negative_volume_count: int
    invalid_date_count: int
    non_monotonic_date_count: int
    change_pct_mismatch_count: int
    cleaning_issue_count: int
    status: str
    generated_at: str
