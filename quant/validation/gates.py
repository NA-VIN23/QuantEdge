"""
quant/validation/gates.py
--------------------------
Integrity gates for Sprint 6 validation.

Programmatic assertions that verify correctness of validation results
before they are written to output files.

A failing gate raises ValidationIntegrityError with an exact message
identifying the gate, the window index, and the violated condition.

==============================================================
GATES
==============================================================

1. NO_OVERLAP        — max(dev_end) < min(test_start) per window
2. CHRONOLOGICAL     — windows are in strictly ascending test_start order
3. SYMBOL_ISOLATION  — all windows carry the expected symbol
4. VALID_METRICS     — final_equity >= 0, win_rate in [0,1], max_dd <= 0
5. SENSITIVITY_BASELINE — at least one is_baseline=True result exists
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from quant.validation.sensitivity import SensitivityResult
from quant.validation.walk_forward import WalkForwardSummary


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class ValidationIntegrityError(Exception):
    """Raised when a validation integrity gate fails."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_integrity_gates(
    summary: WalkForwardSummary,
    sensitivity_results: list[SensitivityResult],
    baseline_metrics: Optional[dict] = None,
) -> None:
    """
    Run all integrity gates. Raises ValidationIntegrityError on first failure.

    Parameters
    ----------
    summary : WalkForwardSummary
        Walk-forward results from run_walk_forward().
    sensitivity_results : list[SensitivityResult]
        Sensitivity results from run_sensitivity().
    baseline_metrics : dict, optional
        Full-dataset backtest metrics. Used for sensitivity baseline gate.

    Raises
    ------
    ValidationIntegrityError
        On the first gate that fails.
    """
    _gate_no_dev_test_overlap(summary)
    _gate_chronological_ordering(summary)
    _gate_symbol_isolation(summary)
    _gate_valid_metrics(summary)
    _gate_sensitivity_baseline(sensitivity_results, baseline_metrics)


# ---------------------------------------------------------------------------
# Individual gates
# ---------------------------------------------------------------------------


def _gate_no_dev_test_overlap(summary: WalkForwardSummary) -> None:
    """
    Gate NO_OVERLAP: dev_end must be strictly before test_start in every window.
    max(dev_dates) < min(test_dates) for each window pair.
    """
    for w in summary.windows:
        if w.status == "INSUFFICIENT_DATA":
            continue
        if not w.dev_end or not w.test_start:
            continue
        dev_end_ts = pd.Timestamp(w.dev_end)
        test_start_ts = pd.Timestamp(w.test_start)
        if dev_end_ts >= test_start_ts:
            raise ValidationIntegrityError(
                f"Gate NO_OVERLAP failed for window {w.window_index}: "
                f"dev_end={w.dev_end!r} >= test_start={w.test_start!r}. "
                "Development and test windows must not overlap."
            )


def _gate_chronological_ordering(summary: WalkForwardSummary) -> None:
    """
    Gate CHRONOLOGICAL: each window's test_start must be strictly
    greater than the previous window's test_start.
    """
    prev_test_start: Optional[pd.Timestamp] = None
    for w in summary.windows:
        if w.status == "INSUFFICIENT_DATA" or not w.test_start:
            continue
        ts = pd.Timestamp(w.test_start)
        if prev_test_start is not None and ts <= prev_test_start:
            raise ValidationIntegrityError(
                f"Gate CHRONOLOGICAL failed at window {w.window_index}: "
                f"test_start={w.test_start!r} is not strictly after "
                f"previous test_start={str(prev_test_start.date())!r}."
            )
        prev_test_start = ts


def _gate_symbol_isolation(summary: WalkForwardSummary) -> None:
    """
    Gate SYMBOL_ISOLATION: every window must carry the summary's symbol.
    """
    for w in summary.windows:
        if w.symbol != summary.symbol:
            raise ValidationIntegrityError(
                f"Gate SYMBOL_ISOLATION failed at window {w.window_index}: "
                f"window symbol={w.symbol!r} != summary symbol={summary.symbol!r}."
            )


def _gate_valid_metrics(summary: WalkForwardSummary) -> None:
    """
    Gate VALID_METRICS: numeric sanity checks on all OK/ZERO_TRADES windows.

    - final_equity >= 0
    - win_rate in [0, 1] when not None
    - max_drawdown_pct <= 0 (drawdown is expressed as a negative percentage)
    """
    for w in summary.windows:
        if w.status not in ("OK", "ZERO_TRADES"):
            continue

        if w.final_equity < 0:
            raise ValidationIntegrityError(
                f"Gate VALID_METRICS failed at window {w.window_index}: "
                f"final_equity={w.final_equity} < 0."
            )

        if w.win_rate is not None and not (0.0 <= w.win_rate <= 1.0):
            raise ValidationIntegrityError(
                f"Gate VALID_METRICS failed at window {w.window_index}: "
                f"win_rate={w.win_rate} outside [0, 1]."
            )

        if w.max_drawdown_pct > 0.0:
            raise ValidationIntegrityError(
                f"Gate VALID_METRICS failed at window {w.window_index}: "
                f"max_drawdown_pct={w.max_drawdown_pct} > 0 "
                "(max drawdown must be 0 or negative)."
            )


def _gate_sensitivity_baseline(
    sensitivity_results: list[SensitivityResult],
    baseline_metrics: Optional[dict],
) -> None:
    """
    Gate SENSITIVITY_BASELINE:
    - At least one SensitivityResult must have is_baseline=True.
    - If baseline_metrics are provided, the risk_per_trade baseline
      entry must have the same num_trades as the full-dataset result.
    """
    baseline_entries = [r for r in sensitivity_results if r.is_baseline]
    if not baseline_entries:
        raise ValidationIntegrityError(
            "Gate SENSITIVITY_BASELINE failed: no result with is_baseline=True "
            "found in sensitivity_results."
        )

    if baseline_metrics is not None:
        expected_trades = baseline_metrics.get("num_trades")
        if expected_trades is not None:
            risk_baseline = [
                r for r in baseline_entries
                if r.param_name == "risk_per_trade"
            ]
            if risk_baseline:
                rb = risk_baseline[0]
                if rb.num_trades != expected_trades:
                    raise ValidationIntegrityError(
                        f"Gate SENSITIVITY_BASELINE failed: sensitivity baseline "
                        f"(risk_per_trade) produced num_trades={rb.num_trades} "
                        f"but full-dataset baseline has num_trades={expected_trades}. "
                        "Sensitivity baseline must reproduce the full-dataset result."
                    )
