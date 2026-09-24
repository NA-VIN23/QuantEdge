"""
quant/backtest/__main__.py
--------------------------
Enables: python -m quant.backtest

Sprint 5: Supports --symbol SYMBOL and --symbols SYM1 SYM2 ...
"""
import sys
from quant.backtest.pipeline import run_pipeline, _parse_args
from quant.backtest.costs import CostModel
from quant.backtest.engine import BacktestConfig

if __name__ == "__main__":
    args = _parse_args()

    if args.symbols:
        symbols = args.symbols
    elif args.symbol:
        symbols = [args.symbol]
    else:
        symbols = ["ITC"]  # legacy default

    cost = CostModel(
        commission_rate=args.commission,
        slippage_rate=args.slippage,
    )

    any_fail = False
    for sym in symbols:
        cfg = BacktestConfig(
            initial_capital=args.capital,
            risk_per_trade=args.risk_per_trade,
            atr_multiplier=args.atr_multiplier,
            cost_model=cost,
            symbol=sym,
        )
        try:
            run_pipeline(symbol=sym, config=cfg)
        except Exception as exc:
            print(f"\n[!!] Backtest failed for {sym}: {exc}")
            any_fail = True

    if any_fail:
        sys.exit(1)
