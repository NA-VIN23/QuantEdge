"""
quant/validation/__main__.py
------------------------------
CLI entry point for Sprint 6 Walk-Forward Validation.

Usage
-----
::

    python -m quant.validation --symbol ITC
    python -m quant.validation --symbol ITC --initial-dev-years 3 --step-months 6 --test-months 6

Steps executed
--------------
1. Load pre-computed features CSV for the symbol.
2. Run full-dataset baseline backtest (ITC regression check).
3. Run full-dataset buy-and-hold benchmark.
4. Run walk-forward validation (expanding dev window, fixed test window).
5. Run sensitivity analysis (11 parameter configurations).
6. Run all integrity gates.
7. Write output files to data/validation/ and docs/.
"""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from quant.backtest.engine import BacktestConfig, run_backtest
from quant.backtest.metrics import compute_metrics
from quant.data.registry import get_available_symbols, get_features_path
from quant.validation.benchmark import run_buy_hold
from quant.validation.gates import ValidationIntegrityError, run_integrity_gates
from quant.validation.report import build_validation_report
from quant.validation.sensitivity import run_sensitivity
from quant.validation.walk_forward import run_walk_forward


def main(argv=None) -> int:
    args = _parse_args(argv)
    symbol = args.symbol.upper()

    # --- Check symbol availability ---
    available = get_available_symbols()
    if symbol not in available:
        print(
            f"[!!] Symbol '{symbol}' has no processed data on disk.\n"
            f"     Available: {available}\n"
            f"     Run: python -m quant.data.pipeline --symbol {symbol}"
        )
        return 1

    features_path = get_features_path(symbol)
    print("=" * 60)
    print(f"QuantEdge - Sprint 6 Walk-Forward Validation  [{symbol}]")
    print("=" * 60)

    # --- Step 1: Load features CSV ---
    print(f"\n[1/6] Loading features: {features_path}")
    df = pd.read_csv(features_path)
    df = df.sort_values("date", ascending=True).reset_index(drop=True)
    first_date = df["date"].iloc[0]
    last_date = df["date"].iloc[-1]
    print(f"      Rows: {len(df)}  ({first_date} to {last_date})")

    base_config = BacktestConfig(symbol=symbol)

    # --- Step 2: Full-dataset baseline ---
    print("\n[2/6] Running full-dataset baseline backtest...")
    baseline_result = run_backtest(df, base_config)
    baseline_metrics = compute_metrics(baseline_result)
    print(f"      Trades:        {baseline_metrics['num_trades']}")
    print(f"      Return:        {baseline_metrics['total_return_pct']:.2f}%")
    print(f"      Final equity:  INR {baseline_metrics['final_equity']:,.2f}")
    print(f"      Max drawdown:  {baseline_metrics['max_drawdown_pct']:.2f}%")

    # --- Step 3: Full-dataset buy-and-hold ---
    bh_full = run_buy_hold(
        df=df,
        initial_capital=base_config.initial_capital,
        cost_model=base_config.cost_model,
    )
    print(f"      B&H return:    {bh_full['total_return_pct']:.2f}%")

    # --- Step 4: Walk-forward validation ---
    print(
        f"\n[3/6] Running walk-forward validation "
        f"(initial_dev_years={args.initial_dev_years}, "
        f"step={args.step_months}m, test={args.test_months}m)..."
    )
    summary = run_walk_forward(
        df=df,
        symbol=symbol,
        config=base_config,
        initial_dev_years=args.initial_dev_years,
        step_months=args.step_months,
        test_months=args.test_months,
    )
    print(f"      Total windows:              {summary.total_windows}")
    print(f"      OK windows (with trades):   {summary.ok_windows}")
    print(f"      Zero-trade windows:         {summary.zero_trade_windows}")
    print(f"      Insufficient-data windows:  {summary.insufficient_data_windows}")

    # --- Step 5: Sensitivity analysis ---
    print("\n[4/6] Running sensitivity analysis...")
    sensitivity_results = run_sensitivity(df=df, symbol=symbol, base_config=base_config)
    print(f"      Configurations tested: {len(sensitivity_results)}")

    # --- Step 6: Integrity gates ---
    print("\n[5/6] Running integrity gates...")
    gate_status = "PASSED"
    gate_errors: list[str] = []
    try:
        run_integrity_gates(
            summary=summary,
            sensitivity_results=sensitivity_results,
            baseline_metrics=baseline_metrics,
        )
        print("      All gates PASSED [OK]")
    except ValidationIntegrityError as exc:
        gate_status = "FAILED"
        gate_errors.append(str(exc))
        print(f"      Gate FAILED: {exc}")

    # --- Step 7: Write output files ---
    print("\n[6/6] Writing output files...")
    written = build_validation_report(
        symbol=symbol,
        summary=summary,
        sensitivity_results=sensitivity_results,
        baseline_metrics=baseline_metrics,
        bh_full=bh_full,
        gate_status=gate_status,
        gate_errors=gate_errors,
    )
    for name, path in written.items():
        print(f"      {name:<15} -> {path}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"Sprint 6 validation complete [{symbol}].")
    print(f"  Integrity gates: {gate_status}")
    print(f"  Walk-forward windows: {summary.total_windows} total, "
          f"{summary.ok_windows} OK")
    print(f"  Sensitivity configs: {len(sensitivity_results)}")
    print("=" * 60)

    return 0 if gate_status == "PASSED" else 1


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="QuantEdge Sprint 6 — Walk-Forward Validation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--symbol", type=str, default="ITC",
        help="NSE symbol to validate.",
    )
    p.add_argument(
        "--initial-dev-years", type=int, default=3,
        help="Minimum development years before first unseen window.",
    )
    p.add_argument(
        "--step-months", type=int, default=6,
        help="Walk-forward step size (months).",
    )
    p.add_argument(
        "--test-months", type=int, default=6,
        help="Unseen test window size (months).",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
