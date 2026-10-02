"""
quant/validation/sensitivity.py
--------------------------------
Limited sensitivity analysis for Sprint 6.

Runs the full-dataset backtest with small parameter variations around
the existing FIXED baseline configuration. This is NOT optimization —
it is a robustness check: if small parameter changes produce dramatically
different results, the strategy may be fragile; if results are stable,
the strategy is robust.

==============================================================
PARAMETERS VARIED (one at a time; all others held at baseline)
==============================================================

risk_per_trade  : 0.005, 0.010 (baseline), 0.015, 0.020
atr_multiplier  : 1.5, 2.0 (baseline), 2.5, 3.0
commission_rate : 0.0005 (baseline), 0.0010, 0.0020

Total: 11 configurations (including 3 baselines, one per parameter).

==============================================================
PARAMETERS NOT VARIED
==============================================================

The following are strategy-defining constants — varying them would
constitute strategy redesign, not robustness testing:

- EMA spans (20, 50)         — hardcoded in indicators.py
- Breakout period (20 days)  — BREAKOUT_PERIOD constant
- Volume threshold (1.5x)    — VOLUME_SURGE_THRESHOLD constant
- Entry / exit rules
- Initial capital (₹100,000)
- Slippage rate (0.05%)      — held constant while commission varies
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from quant.backtest.costs import CostModel
from quant.backtest.engine import BacktestConfig, run_backtest
from quant.backtest.metrics import compute_metrics


# ---------------------------------------------------------------------------
# Sensitivity parameter grid
# (param_name, param_value, is_baseline)
# ---------------------------------------------------------------------------

SENSITIVITY_GRID: list[tuple[str, float, bool]] = [
    # risk_per_trade variants
    ("risk_per_trade", 0.005,  False),
    ("risk_per_trade", 0.010,  True),   # baseline
    ("risk_per_trade", 0.015,  False),
    ("risk_per_trade", 0.020,  False),

    # atr_multiplier variants
    ("atr_multiplier", 1.5, False),
    ("atr_multiplier", 2.0, True),      # baseline
    ("atr_multiplier", 2.5, False),
    ("atr_multiplier", 3.0, False),

    # commission_rate variants (slippage held at baseline 0.0005)
    ("commission_rate", 0.0005, True),  # baseline
    ("commission_rate", 0.0010, False),
    ("commission_rate", 0.0020, False),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SensitivityResult:
    """Result for one sensitivity configuration."""

    param_name: str
    param_value: float
    is_baseline: bool

    # Full-dataset backtest metrics
    num_trades: int
    total_return_pct: float
    win_rate: Optional[float]
    profit_factor: Optional[float]
    max_drawdown_pct: float
    final_equity: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_sensitivity(
    df: pd.DataFrame,
    symbol: str = "ITC",
    base_config: Optional[BacktestConfig] = None,
) -> list[SensitivityResult]:
    """
    Run limited sensitivity analysis over the full-dataset backtest.

    Each configuration in SENSITIVITY_GRID varies exactly ONE parameter
    from the baseline. All other parameters are held at their baseline
    values. No optimization or parameter search is performed.

    Parameters
    ----------
    df : pd.DataFrame
        Full feature-enriched DataFrame, sorted chronologically.
    symbol : str
        NSE symbol name.
    base_config : BacktestConfig, optional
        Baseline configuration. Uses BacktestConfig defaults if None.

    Returns
    -------
    list[SensitivityResult]
        One result per entry in SENSITIVITY_GRID.
        The list is ordered exactly as SENSITIVITY_GRID.
    """
    if base_config is None:
        base_config = BacktestConfig(symbol=symbol)

    results: list[SensitivityResult] = []

    for param_name, param_value, is_baseline in SENSITIVITY_GRID:
        variant_config = _build_variant_config(base_config, param_name, param_value)

        result = run_backtest(df, variant_config)
        metrics = compute_metrics(result)

        results.append(SensitivityResult(
            param_name=param_name,
            param_value=param_value,
            is_baseline=is_baseline,
            num_trades=metrics["num_trades"],
            total_return_pct=round(metrics["total_return_pct"], 4),
            win_rate=metrics["win_rate"],
            profit_factor=metrics["profit_factor"],
            max_drawdown_pct=round(metrics["max_drawdown_pct"], 4),
            final_equity=round(metrics["final_equity"], 4),
        ))

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_variant_config(
    base: BacktestConfig,
    param_name: str,
    param_value: float,
) -> BacktestConfig:
    """
    Return a new BacktestConfig identical to *base* except for one parameter.

    BacktestConfig is frozen — this function never mutates the base config.
    """
    if param_name == "risk_per_trade":
        return BacktestConfig(
            initial_capital=base.initial_capital,
            risk_per_trade=param_value,
            atr_multiplier=base.atr_multiplier,
            cost_model=base.cost_model,
            symbol=base.symbol,
        )
    elif param_name == "atr_multiplier":
        return BacktestConfig(
            initial_capital=base.initial_capital,
            risk_per_trade=base.risk_per_trade,
            atr_multiplier=param_value,
            cost_model=base.cost_model,
            symbol=base.symbol,
        )
    elif param_name == "commission_rate":
        new_cost = CostModel(
            commission_rate=param_value,
            slippage_rate=base.cost_model.slippage_rate,  # slippage unchanged
        )
        return BacktestConfig(
            initial_capital=base.initial_capital,
            risk_per_trade=base.risk_per_trade,
            atr_multiplier=base.atr_multiplier,
            cost_model=new_cost,
            symbol=base.symbol,
        )
    else:
        raise ValueError(
            f"_build_variant_config: unknown sensitivity parameter {param_name!r}. "
            f"Valid: risk_per_trade, atr_multiplier, commission_rate."
        )
