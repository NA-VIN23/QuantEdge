"""
quant/data/validation.py
------------------------
Explicit validation checks for QuantEdge Sprint 1.

Responsibility:
  - Accept the canonical DataFrame from cleaning.py.
  - Run every data-quality check listed in the Sprint 1 spec.
  - Produce a ValidationReport (dict-serialisable) with:
        - per-check findings
        - warnings list
        - errors list
        - overall status: PASS | WARNING | FAIL

Validation checks implemented:
  1.  OHLC consistency: high >= low, high >= open, high >= close,
                         low <= open, low <= close
  2.  Missing values per canonical column
  3.  Volume > 0 (where not NaN)
  4.  Non-monotonic dates after sorting
  5.  Canonical column presence
  6.  Change % cross-validation:
        computed = (close[t] / close[t-1]) - 1
        vs source change_pct_src
        flags |computed - source| > CHANGE_PCT_TOLERANCE
  7.  Invalid volume (NaN where row is otherwise valid)
  8.  Summary counts from cleaning step

DO NOT modify any data values.
DO NOT invent financial assumptions to fix bad data.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date as date_type
from typing import Any

import numpy as np
import pandas as pd

from quant.data.cleaning import CleaningResult, CANONICAL_COLUMNS


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Tolerance for Change % cross-validation (0.5% in absolute percentage points).
CHANGE_PCT_TOLERANCE: float = 0.005

# Overall status levels.
STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class OHLCViolation:
    """A single OHLC consistency violation."""

    row_index: int
    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    violated_rules: list[str]


@dataclass
class ChangePctMismatch:
    """A single Change % cross-validation mismatch."""

    row_index: int
    date: str
    close_t: float
    close_t_minus_1: float
    computed_change_pct: float
    source_change_pct: float
    absolute_diff: float


@dataclass
class ValidationReport:
    """Full validation report for Sprint 1."""

    # Source metadata (filled in by pipeline.py)
    source_filename: str = ""
    symbol: str = "ITC"

    # Row counts
    original_row_count: int = 0
    final_row_count: int = 0
    removed_row_count: int = 0

    # Date info
    date_min: str = ""
    date_max: str = ""

    # Missing value counts per column
    missing_counts: dict[str, int] = field(default_factory=dict)

    # Duplicate info
    duplicate_exact_count: int = 0
    duplicate_date_count: int = 0

    # OHLC violations
    invalid_ohlc_count: int = 0
    ohlc_violations: list[OHLCViolation] = field(default_factory=list)

    # Volume
    invalid_volume_count: int = 0      # rows where volume is NaN (but row otherwise valid)
    zero_volume_count: int = 0         # rows where volume == 0
    negative_volume_count: int = 0     # rows where volume < 0

    # Date
    invalid_date_count: int = 0        # rows where date could not be parsed
    non_monotonic_date_count: int = 0  # rows where date order is not strictly ascending

    # Change % cross-validation
    change_pct_mismatches: list[ChangePctMismatch] = field(default_factory=list)
    change_pct_mismatch_count: int = 0
    change_pct_skipped: bool = False
    change_pct_skipped_reason: str = ""

    # Canonical column check
    unexpected_columns: list[str] = field(default_factory=list)
    missing_canonical_columns: list[str] = field(default_factory=list)

    # Cleaning issues forwarded
    cleaning_issue_count: int = 0
    cleaning_warnings: list[str] = field(default_factory=list)
    cleaning_errors: list[str] = field(default_factory=list)

    # Validation-level messages
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Overall
    status: str = STATUS_FAIL  # conservative default; overwritten at end


# ---------------------------------------------------------------------------
# Internal check functions
# ---------------------------------------------------------------------------


def _check_canonical_columns(
    df: pd.DataFrame, report: ValidationReport
) -> None:
    """Verify canonical column presence and flag unexpected extras."""
    actual = set(df.columns)
    expected = set(CANONICAL_COLUMNS)

    # change_pct_src is an internal reference column, not part of canonical output.
    # It may be present at this stage — treat it as expected.
    expected_with_ref = expected | {"change_pct_src"}

    unexpected = sorted(actual - expected_with_ref)
    missing = sorted(expected - actual)

    report.unexpected_columns = unexpected
    report.missing_canonical_columns = missing

    if missing:
        report.errors.append(f"Missing canonical columns: {missing}")
    if unexpected:
        report.warnings.append(f"Unexpected extra columns: {unexpected}")


def _check_missing_values(df: pd.DataFrame, report: ValidationReport) -> None:
    """Count missing values per canonical column."""
    for col in CANONICAL_COLUMNS:
        if col in df.columns:
            report.missing_counts[col] = int(df[col].isna().sum())
        else:
            report.missing_counts[col] = -1  # column absent


def _check_ohlc_consistency(df: pd.DataFrame, report: ValidationReport) -> None:
    """Check high >= low, high >= open, high >= close, low <= open, low <= close."""
    violations: list[OHLCViolation] = []

    required = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in required):
        report.warnings.append("Cannot run OHLC check: one or more OHLC columns missing.")
        return

    for idx, row in df.iterrows():
        o = row["open"]
        h = row["high"]
        lo = row["low"]
        c = row["close"]

        # Skip rows where any OHLC value is NaN.
        if any(pd.isna(v) for v in [o, h, lo, c]):
            continue

        broken: list[str] = []
        if not (h >= lo):
            broken.append("high < low")
        if not (h >= o):
            broken.append("high < open")
        if not (h >= c):
            broken.append("high < close")
        if not (lo <= o):
            broken.append("low > open")
        if not (lo <= c):
            broken.append("low > close")

        if broken:
            dt_val = row["date"]
            violations.append(
                OHLCViolation(
                    row_index=int(idx),
                    date=str(dt_val),
                    open=float(o),
                    high=float(h),
                    low=float(lo),
                    close=float(c),
                    violated_rules=broken,
                )
            )

    report.ohlc_violations = violations
    report.invalid_ohlc_count = len(violations)

    if violations:
        report.warnings.append(
            f"{len(violations)} row(s) violate OHLC consistency rules."
        )


def _check_volume(df: pd.DataFrame, report: ValidationReport) -> None:
    """Check volume > 0 for rows where volume is present."""
    if "volume" not in df.columns:
        report.warnings.append("Volume column missing; skipping volume checks.")
        return

    vol = df["volume"]
    nan_mask = vol.isna()
    zero_mask = (~nan_mask) & (vol == 0)
    neg_mask = (~nan_mask) & (vol < 0)

    report.invalid_volume_count = int(nan_mask.sum())
    report.zero_volume_count = int(zero_mask.sum())
    report.negative_volume_count = int(neg_mask.sum())

    if report.invalid_volume_count > 0:
        report.warnings.append(
            f"{report.invalid_volume_count} row(s) have missing (NaN) volume."
        )
    if report.zero_volume_count > 0:
        report.errors.append(
            f"{report.zero_volume_count} row(s) have zero volume."
        )
    if report.negative_volume_count > 0:
        report.errors.append(
            f"{report.negative_volume_count} row(s) have negative volume."
        )


def _check_monotonic_dates(df: pd.DataFrame, report: ValidationReport) -> None:
    """
    After sorting, verify that dates are strictly ascending (no repeats).
    Non-monotonic count should be 0 after cleaning removes duplicates.
    """
    if "date" not in df.columns:
        report.warnings.append("Date column missing; skipping monotonic check.")
        return

    dates = pd.to_datetime(df["date"], errors="coerce")
    diffs = dates.diff()
    non_mono = (diffs <= pd.Timedelta(0)) & diffs.notna()
    report.non_monotonic_date_count = int(non_mono.sum())

    if report.non_monotonic_date_count > 0:
        report.errors.append(
            f"{report.non_monotonic_date_count} row(s) are non-monotonic in date order."
        )


def _check_change_pct(df: pd.DataFrame, report: ValidationReport) -> None:
    """
    Cross-validate source Change % against computed daily returns.

    computed = (close[t] / close[t-1]) - 1
    source   = change_pct_src (decimal fraction)

    Flag rows where |computed - source| > CHANGE_PCT_TOLERANCE.
    """
    if "change_pct_src" not in df.columns:
        report.change_pct_skipped = True
        report.change_pct_skipped_reason = (
            "change_pct_src column not present in DataFrame."
        )
        return

    if "close" not in df.columns:
        report.change_pct_skipped = True
        report.change_pct_skipped_reason = "close column not present in DataFrame."
        return

    close = df["close"].astype(float)
    src_pct = df["change_pct_src"].astype(float)

    # Compute return series; first row has no previous close.
    computed = close.pct_change()  # (close[t] / close[t-1]) - 1

    mismatches: list[ChangePctMismatch] = []

    for idx in df.index[1:]:  # skip first row (no prior close)
        c_t = close.at[idx]
        c_prev_loc = df.index.get_loc(idx) - 1
        c_prev_idx = df.index[c_prev_loc]
        c_tm1 = close.at[c_prev_idx]
        comp = computed.at[idx]
        src = src_pct.at[idx]

        # Skip if either value is NaN.
        if pd.isna(comp) or pd.isna(src):
            continue

        diff = abs(comp - src)
        if diff > CHANGE_PCT_TOLERANCE:
            mismatches.append(
                ChangePctMismatch(
                    row_index=int(idx),
                    date=str(df.at[idx, "date"]),
                    close_t=float(c_t),
                    close_t_minus_1=float(c_tm1),
                    computed_change_pct=float(comp),
                    source_change_pct=float(src),
                    absolute_diff=float(diff),
                )
            )

    report.change_pct_mismatches = mismatches
    report.change_pct_mismatch_count = len(mismatches)

    if mismatches:
        report.warnings.append(
            f"{len(mismatches)} row(s) show Change % mismatch "
            f"(tolerance {CHANGE_PCT_TOLERANCE*100:.2f}%). "
            "The source Change % is a reference field; Close is authoritative."
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(
    df: pd.DataFrame,
    cleaning_result: CleaningResult,
    source_filename: str = "",
) -> ValidationReport:
    """
    Run all Sprint 1 validation checks on the canonical DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Canonical DataFrame (output of cleaning.clean, before dropping change_pct_src).
    cleaning_result : CleaningResult
        Summary from the cleaning step.
    source_filename : str
        Name of the original raw file (for report metadata).

    Returns
    -------
    ValidationReport
        Fully populated report with overall status.
    """
    report = ValidationReport(
        source_filename=source_filename,
        symbol="ITC",
        original_row_count=cleaning_result.original_row_count,
        final_row_count=cleaning_result.final_row_count,
        removed_row_count=cleaning_result.removed_row_count,
        duplicate_exact_count=cleaning_result.duplicate_exact_count,
        duplicate_date_count=cleaning_result.duplicate_date_count,
        cleaning_issue_count=len(cleaning_result.issues),
        cleaning_warnings=cleaning_result.warnings,
        cleaning_errors=cleaning_result.errors,
    )

    # Date range
    if "date" in df.columns and not df.empty:
        valid_dates = df["date"].dropna()
        if not valid_dates.empty:
            report.date_min = str(valid_dates.iloc[0])
            report.date_max = str(valid_dates.iloc[-1])

    # Run checks
    _check_canonical_columns(df, report)
    _check_missing_values(df, report)
    _check_ohlc_consistency(df, report)
    _check_volume(df, report)
    _check_monotonic_dates(df, report)
    _check_change_pct(df, report)

    # invalid_date_count: rows where date is NaN after cleaning
    if "date" in df.columns:
        report.invalid_date_count = int(df["date"].isna().sum())

    # ------------------------------------------------------------------
    # Determine overall status.
    # ------------------------------------------------------------------
    #
    # FAIL conditions (any of):
    #   - Hard cleaning errors
    #   - Missing canonical columns
    #   - OHLC violations
    #   - Non-monotonic dates
    #   - Zero or negative volume
    #   - Any validation-level errors
    #
    # WARNING conditions (no errors but any of):
    #   - Cleaning warnings
    #   - Missing volume rows
    #   - Change % mismatches
    #   - Validation-level warnings
    #
    # PASS: no errors, no warnings.
    # ------------------------------------------------------------------

    fail_conditions = (
        len(report.errors) > 0
        or len(cleaning_result.errors) > 0
        or len(report.missing_canonical_columns) > 0
        or report.invalid_ohlc_count > 0
        or report.non_monotonic_date_count > 0
        or report.zero_volume_count > 0
        or report.negative_volume_count > 0
    )

    warn_conditions = (
        len(report.warnings) > 0
        or len(cleaning_result.warnings) > 0
        or report.invalid_volume_count > 0
        or report.change_pct_mismatch_count > 0
    )

    if fail_conditions:
        report.status = STATUS_FAIL
    elif warn_conditions:
        report.status = STATUS_WARNING
    else:
        report.status = STATUS_PASS

    return report


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    """
    Convert a ValidationReport to a plain dict (JSON-serialisable).

    OHLCViolation and ChangePctMismatch dataclasses are flattened.
    """

    def _flatten(obj: Any) -> Any:
        if isinstance(obj, list):
            return [_flatten(i) for i in obj]
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _flatten(v) for k, v in asdict(obj).items()}
        return obj

    return _flatten(asdict(report))
