"""
quant/backtest/pipeline.py
--------------------------
Sprint 5: Generalized backtesting pipeline for QuantEdge.

Sprint 3 legacy: zero-arg call still works for ITC backward compat.

Entry points (via __main__.py):
    python -m quant.backtest                      # ITC (legacy)
    python -m quant.backtest --symbol ITC
    python -m quant.backtest --symbols ITC RELIANCE TCS

Sequence (per symbol):
    1. Load Data/processed/stocks/{SYMBOL}_features.csv
    2. Run the backtest engine
    3. Compute performance metrics
    4. Write output files to Data/backtests/{SYMBOL}/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from quant.backtest.costs import CostModel
from quant.backtest.engine import (
    BacktestConfig,
    BacktestResult,
    backtest_from_csv,
    TradeRecord,
)
from quant.backtest.metrics import compute_metrics
from quant.data.registry import (
    get_features_path,
    get_backtest_dir,
    SYMBOL_REGISTRY,
)


# ---------------------------------------------------------------------------
# Legacy ITC paths (Sprint 3 backward compat)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent

FEATURES_CSV = PROJECT_ROOT / "Data" / "processed" / "itc_features.csv"
OUTPUT_DIR   = PROJECT_ROOT / "Data" / "backtests" / "itc_trend_momentum"


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_trades_csv(trades: list[TradeRecord], path: Path) -> None:
    """Write the trade ledger to CSV."""
    if not trades:
        cols = [
            "trade_id", "symbol", "signal_date", "entry_date",
            "entry_reference_price", "entry_price", "initial_stop",
            "atr_at_signal", "quantity", "risk_budget",
            "exit_date", "exit_reference_price", "exit_price", "exit_reason",
            "gross_pnl", "transaction_cost", "net_pnl",
            "return_pct", "r_multiple", "holding_days",
        ]
        pd.DataFrame(columns=cols).to_csv(path, index=False)
        return

    rows = []
    for t in trades:
        rows.append({
            "trade_id": t.trade_id,
            "symbol": t.symbol,
            "signal_date": t.signal_date,
            "entry_date": t.entry_date,
            "entry_reference_price": round(t.entry_reference_price, 4),
            "entry_price": round(t.entry_price, 4),
            "initial_stop": round(t.initial_stop, 4),
            "atr_at_signal": round(t.atr_at_signal, 6),
            "quantity": t.quantity,
            "risk_budget": round(t.risk_budget, 4),
            "exit_date": t.exit_date,
            "exit_reference_price": round(t.exit_reference_price, 4),
            "exit_price": round(t.exit_price, 4),
            "exit_reason": t.exit_reason,
            "gross_pnl": round(t.gross_pnl, 4),
            "transaction_cost": round(t.transaction_cost, 4),
            "net_pnl": round(t.net_pnl, 4),
            "return_pct": round(t.return_pct * 100, 4),
            "r_multiple": round(t.r_multiple, 4),
            "holding_days": t.holding_days,
        })
    pd.DataFrame(rows).to_csv(path, index=False)


def write_equity_csv(result: BacktestResult, path: Path) -> None:
    """Write the daily equity curve to CSV."""
    rows = []
    for e in result.equity_curve:
        rows.append({
            "date": e.date,
            "cash": round(e.cash, 4),
            "position_quantity": e.position_quantity,
            "position_market_value": round(e.position_market_value, 4),
            "equity": round(e.equity, 4),
        })
    pd.DataFrame(rows).to_csv(path, index=False)


def write_summary_json(metrics: dict, path: Path) -> None:
    """Write the performance metrics to JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)


def write_report_md(
    metrics: dict,
    result: BacktestResult,
    symbol: str,
    path: Path,
) -> None:
    """Write the human-readable Markdown report."""

    def _fmt(v, fmt=".2f"):
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:{fmt}}"
        return str(v)

    cfg = result.config
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# QuantEdge -- Backtest Report [{symbol}]",
        "",
        f"**Generated:** {now}",
        "",
        "> [!CAUTION]",
        "> This is a **historical simulation only**. Past simulation results do NOT",
        "> guarantee future performance. This report does NOT constitute investment advice.",
        "",
        "---",
        "",
        "## 1. Dataset",
        "",
        f"- **Symbol:** {symbol}",
        f"- **Source:** `Data/processed/stocks/{symbol}_features.csv`",
        f"- **Date range:** {result.equity_curve[0].date if result.equity_curve else 'N/A'}"
        f" to {result.equity_curve[-1].date if result.equity_curve else 'N/A'}",
        f"- **Total trading days:** {len(result.equity_curve)}",
        "",
        "---",
        "",
        "## 2. Strategy",
        "",
        "**Daily Trend-Momentum Breakout** (Sprint 2)",
        "",
        "| # | Condition | Rule |",
        "|---|-----------|------|",
        "| 1 | Trend | `ema20 > ema50` |",
        "| 2 | Price | `close > ema20` |",
        "| 3 | Breakout | `close > rolling_max(close, 20).shift(1)` |",
        "| 4 | Volume | `volume_ratio > 1.5` |",
        "",
        "---",
        "",
        "## 3. Performance Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Initial capital | Rs.{metrics['initial_capital']:,.2f} |",
        f"| Final equity | Rs.{metrics['final_equity']:,.2f} |",
        f"| Total net P&L | Rs.{metrics['total_net_pnl']:,.2f} |",
        f"| Total return | {_fmt(metrics['total_return_pct'])}% |",
        f"| Executed trades | {metrics['num_signals_executed']} |",
        f"| Winning trades | {metrics['num_wins']} |",
        f"| Losing trades | {metrics['num_losses']} |",
        f"| Win rate | {_fmt(metrics['win_rate'] * 100 if metrics['win_rate'] is not None else None)}% |",
        f"| Profit factor | {_fmt(metrics['profit_factor'])} |",
        f"| Max drawdown | {_fmt(metrics['max_drawdown_pct'])}% |",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public pipeline function
# ---------------------------------------------------------------------------


def run_pipeline(
    symbol: str = "ITC",
    features_csv: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    config: Optional[BacktestConfig] = None,
) -> dict:
    """
    Full pipeline: load -> backtest -> metrics -> write outputs.

    Parameters
    ----------
    symbol : str
        NSE equity symbol. Defaults to "ITC".
    features_csv : Path, optional
        Override the input features CSV. Uses registry default if None.
    output_dir : Path, optional
        Override the output directory. Uses registry default if None.
    config : BacktestConfig, optional
        Engine configuration. Uses defaults if None.

    Returns
    -------
    dict
        The computed metrics dictionary.
    """
    # Resolve paths.
    if features_csv is None:
        features_csv = get_features_path(symbol)
    if output_dir is None:
        output_dir = get_backtest_dir(symbol)
    if config is None:
        config = BacktestConfig(symbol=symbol)

    print("=" * 60)
    print(f"QuantEdge -- Backtesting Engine  [{symbol}]")
    print("=" * 60)

    # 1. Load features
    print(f"\n[1/4] Loading: {features_csv}")
    if not features_csv.exists():
        print(f"  [!!] File not found: {features_csv}")
        print(f"  Run 'python -m quant.features.pipeline --symbol {symbol}' first.")
        sys.exit(1)

    result = backtest_from_csv(str(features_csv), config)
    print(f"      Rows processed : {len(result.equity_curve)}")
    print(f"      Signals found  : {len(result.trades) + len(result.skipped_signals)}")

    # 2. Compute metrics
    print("\n[2/4] Computing metrics...")
    metrics = compute_metrics(result)
    print(f"      Executed trades : {metrics['num_signals_executed']}")
    print(f"      Skipped signals : {metrics['num_signals_skipped']}")
    if metrics["win_rate"] is not None:
        print(f"      Win rate        : {metrics['win_rate']*100:.1f}%")
    else:
        print("      Win rate        : N/A")
    print(f"      Total return    : {metrics['total_return_pct']:.2f}%")
    print(f"      Max drawdown    : {metrics['max_drawdown_pct']:.2f}%")

    # 3. Write outputs
    print(f"\n[3/4] Writing outputs to: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    write_trades_csv(result.trades, output_dir / "trades.csv")
    write_equity_csv(result, output_dir / "equity_curve.csv")
    write_summary_json(metrics, output_dir / "summary.json")
    write_report_md(metrics, result, symbol, output_dir / "report.md")

    print("      trades.csv       written")
    print("      equity_curve.csv written")
    print("      summary.json     written")
    print("      report.md        written")

    # 4. Summary
    print("\n" + "=" * 60)
    print(f"Backtest complete [{symbol}].")
    print(f"  Initial capital : Rs.{metrics['initial_capital']:,.2f}")
    print(f"  Final equity    : Rs.{metrics['final_equity']:,.2f}")
    print(f"  Net P&L         : Rs.{metrics['total_net_pnl']:,.2f}")
    print(f"  Total return    : {metrics['total_return_pct']:.2f}%")
    print(f"  Trades executed : {metrics['num_signals_executed']}")
    if metrics["win_rate"] is not None:
        print(f"  Win rate        : {metrics['win_rate']*100:.1f}%")
    if metrics["profit_factor"] is not None:
        print(f"  Profit factor   : {metrics['profit_factor']:.3f}")
    print(f"  Max drawdown    : {metrics['max_drawdown_pct']:.2f}%")
    print("=" * 60)

    return metrics


# ---------------------------------------------------------------------------
# CLI argument parser (used by __main__.py)
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="QuantEdge Backtesting Engine -- run historical backtests.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--capital", type=float, default=100_000.0,
        help="Initial capital in INR.",
    )
    p.add_argument(
        "--risk-per-trade", type=float, default=0.01,
        help="Fraction of equity risked per trade (e.g. 0.01 = 1%%).",
    )
    p.add_argument(
        "--slippage", type=float, default=0.0005,
        help="Slippage rate per side (research default).",
    )
    p.add_argument(
        "--commission", type=float, default=0.0005,
        help="Commission rate per side (research default).",
    )
    p.add_argument(
        "--atr-multiplier", type=float, default=2.0,
        help="ATR multiplier for stop-loss calculation.",
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
