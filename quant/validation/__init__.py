"""
quant/validation/__init__.py
------------------------------
Sprint 6 — Validation / Robustness package for QuantEdge.

Public API
----------
::

    from quant.validation.splitter      import chronological_splits, DataSplit
    from quant.validation.walk_forward  import run_walk_forward, WalkForwardSummary
    from quant.validation.benchmark     import run_buy_hold
    from quant.validation.sensitivity   import run_sensitivity, SENSITIVITY_GRID
    from quant.validation.gates         import run_integrity_gates, ValidationIntegrityError
    from quant.validation.report        import build_validation_report
"""

from quant.validation.splitter import (
    chronological_splits,
    DataSplit,
    slice_test_df,
    slice_dev_df,
)
from quant.validation.walk_forward import (
    run_walk_forward,
    WalkForwardSummary,
    WalkForwardWindow,
)
from quant.validation.benchmark import run_buy_hold
from quant.validation.sensitivity import (
    run_sensitivity,
    SENSITIVITY_GRID,
    SensitivityResult,
)
from quant.validation.gates import run_integrity_gates, ValidationIntegrityError
from quant.validation.report import build_validation_report

__all__ = [
    "chronological_splits",
    "DataSplit",
    "slice_test_df",
    "slice_dev_df",
    "run_walk_forward",
    "WalkForwardSummary",
    "WalkForwardWindow",
    "run_buy_hold",
    "run_sensitivity",
    "SENSITIVITY_GRID",
    "SensitivityResult",
    "run_integrity_gates",
    "ValidationIntegrityError",
    "build_validation_report",
]
