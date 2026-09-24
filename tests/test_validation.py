"""
tests/test_validation.py
------------------------
Unit tests for quant.data.validation.

All tests use small synthetic DataFrames — no dependency on the ITC dataset.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from quant.data.cleaning import CleaningResult, CANONICAL_COLUMNS
from quant.data.validation import (
    CHANGE_PCT_TOLERANCE,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
    validate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clean_result(**overrides) -> CleaningResult:
    """Return a minimal CleaningResult with sensible defaults."""
    defaults = dict(
        original_row_count=5,
        duplicate_exact_count=0,
        duplicate_date_count=0,
        removed_row_count=0,
        final_row_count=5,
        issues=[],
        warnings=[],
        errors=[],
    )
    defaults.update(overrides)
    return CleaningResult(**defaults)


def _make_canonical_df(rows: list[dict]) -> pd.DataFrame:
    """Build a canonical-style DataFrame (as cleaning.clean() would return)."""
    df = pd.DataFrame(rows)
    # Ensure correct dtypes.
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ["open", "high", "low", "close", "volume", "change_pct_src"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "symbol" not in df.columns:
        df["symbol"] = "ITC"
    return df


def _valid_row(date_str: str = "2025-05-29", **overrides) -> dict:
    """Return a perfectly valid canonical row."""
    row = {
        "date": date_str,
        "symbol": "ITC",
        "open": 422.00,
        "high": 422.80,
        "low": 416.60,
        "close": 418.75,
        "volume": 21_480_000.0,
        "change_pct_src": -0.0035,
    }
    row.update(overrides)
    return row


def _two_valid_rows() -> pd.DataFrame:
    """Two consecutive valid rows suitable for Change % testing."""
    return _make_canonical_df([
        _valid_row("2025-05-28", close=433.90, change_pct_src=None),  # first — no prior
        _valid_row("2025-05-29", close=418.75, change_pct_src=(418.75 / 433.90) - 1),
    ])


# ---------------------------------------------------------------------------
# OHLC consistency tests
# ---------------------------------------------------------------------------


class TestOHLCConsistency:

    def test_valid_ohlc_produces_no_violations(self):
        df = _make_canonical_df([_valid_row()])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.invalid_ohlc_count == 0

    def test_high_less_than_low_detected(self):
        df = _make_canonical_df([_valid_row(high=400.00, low=430.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.invalid_ohlc_count >= 1
        rules = report.ohlc_violations[0].violated_rules
        assert any("high < low" in r for r in rules)

    def test_high_less_than_open_detected(self):
        df = _make_canonical_df([_valid_row(high=410.00, open=425.00, low=400.00, close=408.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        rules_flat = [r for v in report.ohlc_violations for r in v.violated_rules]
        assert any("high < open" in r for r in rules_flat)

    def test_high_less_than_close_detected(self):
        df = _make_canonical_df([_valid_row(high=410.00, close=425.00, open=400.00, low=398.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        rules_flat = [r for v in report.ohlc_violations for r in v.violated_rules]
        assert any("high < close" in r for r in rules_flat)

    def test_low_greater_than_open_detected(self):
        df = _make_canonical_df([_valid_row(low=430.00, open=420.00, high=440.00, close=435.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        rules_flat = [r for v in report.ohlc_violations for r in v.violated_rules]
        assert any("low > open" in r for r in rules_flat)

    def test_low_greater_than_close_detected(self):
        df = _make_canonical_df([_valid_row(low=430.00, close=420.00, open=440.00, high=445.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        rules_flat = [r for v in report.ohlc_violations for r in v.violated_rules]
        assert any("low > close" in r for r in rules_flat)

    def test_ohlc_violation_triggers_warning(self):
        df = _make_canonical_df([_valid_row(high=400.00, low=430.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert any("OHLC" in w for w in report.warnings)

    def test_nan_ohlc_row_skipped_by_ohlc_check(self):
        """A row with NaN in OHLC fields should not be flagged as a violation."""
        df = _make_canonical_df([_valid_row(open=np.nan)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.invalid_ohlc_count == 0


# ---------------------------------------------------------------------------
# Missing value tests
# ---------------------------------------------------------------------------


class TestMissingValues:

    def test_no_missing_values(self):
        df = _make_canonical_df([_valid_row()])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        for col in ["open", "high", "low", "close"]:
            assert report.missing_counts.get(col, -1) == 0

    def test_missing_close_counted(self):
        df = _make_canonical_df([_valid_row(close=np.nan)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.missing_counts["close"] == 1

    def test_missing_volume_counted(self):
        df = _make_canonical_df([_valid_row(volume=np.nan)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.missing_counts["volume"] == 1

    def test_missing_volume_counted_as_invalid_volume(self):
        df = _make_canonical_df([_valid_row(volume=np.nan)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.invalid_volume_count == 1


# ---------------------------------------------------------------------------
# Volume tests
# ---------------------------------------------------------------------------


class TestVolume:

    def test_zero_volume_flagged_as_error(self):
        df = _make_canonical_df([_valid_row(volume=0)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.zero_volume_count == 1
        assert any("zero volume" in e for e in report.errors)

    def test_negative_volume_flagged_as_error(self):
        df = _make_canonical_df([_valid_row(volume=-100)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.negative_volume_count == 1

    def test_valid_volume_no_errors(self):
        df = _make_canonical_df([_valid_row()])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.zero_volume_count == 0
        assert report.negative_volume_count == 0


# ---------------------------------------------------------------------------
# Monotonic date tests
# ---------------------------------------------------------------------------


class TestMonotonicDates:

    def test_ascending_dates_pass(self):
        df = _make_canonical_df([
            _valid_row("2025-01-01"),
            _valid_row("2025-01-02"),
            _valid_row("2025-01-03"),
        ])
        cr = _make_clean_result(final_row_count=3, original_row_count=3)
        report = validate(df, cr)
        assert report.non_monotonic_date_count == 0

    def test_non_monotonic_dates_detected(self):
        df = _make_canonical_df([
            _valid_row("2025-01-03"),
            _valid_row("2025-01-01"),  # out of order
            _valid_row("2025-01-05"),
        ])
        cr = _make_clean_result(final_row_count=3, original_row_count=3)
        report = validate(df, cr)
        assert report.non_monotonic_date_count > 0

    def test_repeated_date_detected_as_non_monotonic(self):
        df = _make_canonical_df([
            _valid_row("2025-01-01"),
            _valid_row("2025-01-01"),  # same date again
        ])
        cr = _make_clean_result(final_row_count=2, original_row_count=2)
        report = validate(df, cr)
        assert report.non_monotonic_date_count > 0


# ---------------------------------------------------------------------------
# Change % cross-validation tests
# ---------------------------------------------------------------------------


class TestChangePct:

    def test_matching_change_pct_produces_no_mismatch(self):
        """Exactly computed change% produces zero mismatches."""
        close_prev = 433.90
        close_curr = 418.75
        computed = (close_curr / close_prev) - 1
        df = _make_canonical_df([
            _valid_row("2025-05-28", close=close_prev, change_pct_src=None),
            _valid_row("2025-05-29", close=close_curr, change_pct_src=computed),
        ])
        cr = _make_clean_result(final_row_count=2, original_row_count=2)
        report = validate(df, cr)
        assert report.change_pct_mismatch_count == 0

    def test_large_mismatch_flagged(self):
        """A large discrepancy between computed and source Change % is flagged."""
        close_prev = 433.90
        close_curr = 418.75
        wrong_pct = 0.50  # wildly wrong
        df = _make_canonical_df([
            _valid_row("2025-05-28", close=close_prev, change_pct_src=None),
            _valid_row("2025-05-29", close=close_curr, change_pct_src=wrong_pct),
        ])
        cr = _make_clean_result(final_row_count=2, original_row_count=2)
        report = validate(df, cr)
        assert report.change_pct_mismatch_count >= 1

    def test_mismatch_within_tolerance_not_flagged(self):
        """Small floating-point difference within tolerance should not be flagged."""
        close_prev = 433.90
        close_curr = 418.75
        computed = (close_curr / close_prev) - 1
        # Add tiny noise within tolerance.
        noisy = computed + (CHANGE_PCT_TOLERANCE * 0.1)
        df = _make_canonical_df([
            _valid_row("2025-05-28", close=close_prev, change_pct_src=None),
            _valid_row("2025-05-29", close=close_curr, change_pct_src=noisy),
        ])
        cr = _make_clean_result(final_row_count=2, original_row_count=2)
        report = validate(df, cr)
        assert report.change_pct_mismatch_count == 0

    def test_missing_change_pct_src_column_skips(self):
        """If change_pct_src is absent, cross-validation is skipped gracefully."""
        df = _make_canonical_df([_valid_row()])
        if "change_pct_src" in df.columns:
            df = df.drop(columns=["change_pct_src"])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.change_pct_skipped is True


# ---------------------------------------------------------------------------
# Canonical column tests
# ---------------------------------------------------------------------------


class TestCanonicalColumns:

    def test_all_canonical_columns_present(self):
        df = _make_canonical_df([_valid_row()])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.missing_canonical_columns == []

    def test_missing_column_flagged(self):
        df = _make_canonical_df([_valid_row()])
        df = df.drop(columns=["volume"])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert "volume" in report.missing_canonical_columns


# ---------------------------------------------------------------------------
# Overall status tests
# ---------------------------------------------------------------------------


class TestOverallStatus:

    def test_clean_data_is_pass(self):
        """Perfectly clean data with exact Change % should produce PASS."""
        # Use self-consistent OHLC values: high is the max of O/H/C, low is the min.
        close_prev = 433.90
        close_curr = 418.75
        computed = (close_curr / close_prev) - 1
        df = _make_canonical_df([
            _valid_row(
                "2025-05-28",
                open=430.00, high=436.00, low=428.00, close=close_prev,
                change_pct_src=None,
            ),
            _valid_row(
                "2025-05-29",
                open=422.00, high=423.00, low=416.00, close=close_curr,
                change_pct_src=computed,
            ),
        ])
        cr = _make_clean_result(final_row_count=2, original_row_count=2)
        report = validate(df, cr)
        assert report.status == STATUS_PASS, (
            f"Expected PASS; got {report.status}. "
            f"Errors: {report.errors}, Warnings: {report.warnings}, "
            f"OHLC violations: {report.ohlc_violations}"
        )

    def test_ohlc_violation_causes_fail(self):
        df = _make_canonical_df([_valid_row(high=400.00, low=430.00)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.status == STATUS_FAIL


    def test_missing_volume_causes_warning(self):
        """Missing (NaN) volume is a warning, not a hard error."""
        close_prev = 433.90
        close_curr = 418.75
        computed = (close_curr / close_prev) - 1
        df = _make_canonical_df([
            _valid_row(
                "2025-05-28",
                open=430.00, high=436.00, low=428.00, close=close_prev,
                change_pct_src=None, volume=np.nan,
            ),
            _valid_row(
                "2025-05-29",
                open=422.00, high=423.00, low=416.00, close=close_curr,
                change_pct_src=computed, volume=np.nan,
            ),
        ])
        cr = _make_clean_result(final_row_count=2, original_row_count=2)
        report = validate(df, cr)
        assert report.status == STATUS_WARNING, (
            f"Expected WARNING; got {report.status}. "
            f"Errors: {report.errors}, Warnings: {report.warnings}"
        )

    def test_zero_volume_causes_fail(self):
        df = _make_canonical_df([_valid_row(volume=0)])
        cr = _make_clean_result(final_row_count=1, original_row_count=1)
        report = validate(df, cr)
        assert report.status == STATUS_FAIL

    def test_cleaning_errors_cause_fail(self):
        df = _make_canonical_df([_valid_row()])
        cr = _make_clean_result(
            final_row_count=1, original_row_count=1,
            errors=["A critical cleaning error occurred."]
        )
        report = validate(df, cr)
        assert report.status == STATUS_FAIL

    def test_duplicate_counts_propagated(self):
        df = _make_canonical_df([_valid_row()])
        cr = _make_clean_result(
            final_row_count=1, original_row_count=3,
            duplicate_exact_count=1,
            duplicate_date_count=1,
            removed_row_count=2,
        )
        report = validate(df, cr)
        assert report.duplicate_exact_count == 1
        assert report.duplicate_date_count == 1
        assert report.removed_row_count == 2
