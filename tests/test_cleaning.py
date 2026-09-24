"""
tests/test_cleaning.py
-----------------------
Unit tests for quant.data.cleaning.

All tests use small synthetic DataFrames — no dependency on the ITC dataset.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from quant.data.cleaning import (
    CANONICAL_COLUMNS,
    clean,
    parse_change_pct,
    parse_date,
    parse_price,
    parse_volume,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_df(rows: list[dict]) -> pd.DataFrame:
    """Build a raw (all-string) DataFrame as ingestion.py would return."""
    return pd.DataFrame(rows).astype(str).replace("nan", np.nan)


def _default_row(**overrides) -> dict:
    """Return a valid raw ITC-style row dict, with optional overrides."""
    row = {
        "Date": "05/29/2025",
        "Price": "418.75",
        "Open": "422.00",
        "High": "422.80",
        "Low": "416.60",
        "Vol.": "21.48M",
        "Change %": "-0.35%",
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# parse_volume tests
# ---------------------------------------------------------------------------


class TestParseVolume:

    def test_M_suffix(self):
        assert parse_volume("21.48M") == pytest.approx(21_480_000)

    def test_M_suffix_large(self):
        assert parse_volume("431.85M") == pytest.approx(431_850_000)

    def test_M_suffix_small(self):
        assert parse_volume("5.78M") == pytest.approx(5_780_000)

    def test_K_suffix(self):
        assert parse_volume("1.5K") == pytest.approx(1_500)

    def test_B_suffix(self):
        assert parse_volume("1.2B") == pytest.approx(1_200_000_000)

    def test_lowercase_suffix(self):
        assert parse_volume("3.5m") == pytest.approx(3_500_000)

    def test_no_suffix_integer(self):
        assert parse_volume("12345") == pytest.approx(12_345)

    def test_no_suffix_float(self):
        assert parse_volume("9999.0") == pytest.approx(9_999)

    def test_empty_string_returns_none(self):
        assert parse_volume("") is None

    def test_dash_returns_none(self):
        assert parse_volume("-") is None

    def test_na_returns_none(self):
        assert parse_volume("N/A") is None

    def test_whitespace_stripped(self):
        assert parse_volume("  10.00M  ") == pytest.approx(10_000_000)

    def test_garbage_returns_none(self):
        assert parse_volume("abc") is None

    def test_non_string_returns_none(self):
        assert parse_volume(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_change_pct tests
# ---------------------------------------------------------------------------


class TestParseChangePct:

    def test_negative_pct(self):
        result = parse_change_pct("-0.35%")
        assert result == pytest.approx(-0.0035)

    def test_positive_pct(self):
        result = parse_change_pct("2.39%")
        assert result == pytest.approx(0.0239)

    def test_zero_pct(self):
        assert parse_change_pct("0.00%") == pytest.approx(0.0)

    def test_empty_string_returns_none(self):
        assert parse_change_pct("") is None

    def test_dash_returns_none(self):
        assert parse_change_pct("-") is None

    def test_non_string_returns_none(self):
        assert parse_change_pct(None) is None  # type: ignore[arg-type]

    def test_no_percent_sign_returns_none(self):
        assert parse_change_pct("2.39") is None


# ---------------------------------------------------------------------------
# parse_date tests
# ---------------------------------------------------------------------------


class TestParseDate:

    def test_valid_date_mm_dd_yyyy(self):
        result = parse_date("05/29/2025")
        assert result is not None
        assert result.year == 2025
        assert result.month == 5
        assert result.day == 29

    def test_start_of_dataset(self):
        result = parse_date("04/01/2005")
        assert result is not None
        assert result.year == 2005
        assert result.month == 4
        assert result.day == 1

    def test_empty_string_returns_none(self):
        assert parse_date("") is None

    def test_wrong_format_returns_none(self):
        # YYYY-MM-DD format — not MM/DD/YYYY
        assert parse_date("2025-05-29") is None

    def test_garbage_returns_none(self):
        assert parse_date("not-a-date") is None

    def test_non_string_returns_none(self):
        assert parse_date(None) is None  # type: ignore[arg-type]

    def test_strips_whitespace(self):
        result = parse_date("  05/29/2025  ")
        assert result is not None
        assert result.month == 5


# ---------------------------------------------------------------------------
# parse_price tests
# ---------------------------------------------------------------------------


class TestParsePrice:

    def test_simple_float(self):
        assert parse_price("418.75") == pytest.approx(418.75)

    def test_integer_string(self):
        assert parse_price("100") == pytest.approx(100.0)

    def test_comma_separated(self):
        # e.g. "1,234.56" style
        assert parse_price("1,234.56") == pytest.approx(1234.56)

    def test_empty_string_returns_none(self):
        assert parse_price("") is None

    def test_dash_returns_none(self):
        assert parse_price("-") is None

    def test_garbage_returns_none(self):
        assert parse_price("abc") is None

    def test_non_string_returns_none(self):
        assert parse_price(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# clean() integration tests
# ---------------------------------------------------------------------------


class TestClean:

    def test_canonical_column_names(self):
        """Output DataFrame must have exactly the canonical columns plus change_pct_src."""
        df = _make_raw_df([_default_row()])
        df_clean, _ = clean(df)
        for col in CANONICAL_COLUMNS:
            assert col in df_clean.columns, f"Missing canonical column: {col}"

    def test_symbol_set_to_ITC(self):
        df = _make_raw_df([_default_row()])
        df_clean, _ = clean(df)
        assert (df_clean["symbol"] == "ITC").all()

    def test_volume_is_numeric(self):
        """Volume column must contain numeric values (not strings)."""
        df = _make_raw_df([_default_row(**{"Vol.": "21.48M"})])
        df_clean, _ = clean(df)
        assert pd.api.types.is_numeric_dtype(df_clean["volume"])
        assert df_clean["volume"].iloc[0] == pytest.approx(21_480_000)

    def test_price_maps_to_close(self):
        """Source 'Price' column must become 'close' in canonical output."""
        df = _make_raw_df([_default_row(**{"Price": "418.75"})])
        df_clean, _ = clean(df)
        assert "close" in df_clean.columns
        assert df_clean["close"].iloc[0] == pytest.approx(418.75)

    def test_date_sorted_ascending(self):
        """Output must be sorted chronologically ascending."""
        rows = [
            _default_row(**{"Date": "05/29/2025", "Price": "418.75"}),
            _default_row(**{"Date": "04/01/2005", "Price": "29.89"}),
            _default_row(**{"Date": "01/15/2015", "Price": "200.00"}),
        ]
        df = _make_raw_df(rows)
        df_clean, _ = clean(df)
        dates = pd.to_datetime(df_clean["date"])
        assert (dates.diff().dropna() > pd.Timedelta(0)).all(), (
            "Dates are not strictly ascending after cleaning."
        )

    def test_exact_duplicate_detected_and_removed(self):
        """Exact duplicate rows are removed and reported in CleaningResult."""
        row = _default_row()
        df = _make_raw_df([row, row])  # two identical rows
        df_clean, result = clean(df)
        assert result.duplicate_exact_count == 1
        assert result.removed_row_count >= 1
        # Only one row should remain.
        assert len(df_clean) == 1

    def test_duplicate_date_detected_and_removed(self):
        """Rows with the same parsed date are detected and deduplicated."""
        row1 = _default_row(**{"Price": "418.75"})
        row2 = _default_row(**{"Price": "420.00"})  # different price, same date
        df = _make_raw_df([row1, row2])
        df_clean, result = clean(df)
        assert result.duplicate_date_count >= 1
        # Only one row per date should remain.
        assert len(df_clean["date"].unique()) == len(df_clean)

    def test_missing_volume_becomes_nan(self):
        """Empty volume string becomes NaN (not an error string)."""
        df = _make_raw_df([_default_row(**{"Vol.": ""})])
        df_clean, _ = clean(df)
        assert pd.isna(df_clean["volume"].iloc[0])

    def test_missing_ohlc_becomes_nan(self):
        """Empty OHLC string becomes NaN."""
        df = _make_raw_df([_default_row(**{"Open": "", "High": "", "Low": ""})])
        df_clean, _ = clean(df)
        assert pd.isna(df_clean["open"].iloc[0])
        assert pd.isna(df_clean["high"].iloc[0])
        assert pd.isna(df_clean["low"].iloc[0])

    def test_invalid_records_reported_not_silently_dropped(self):
        """Rows with unparseable values are reported in issues, not silently dropped."""
        df = _make_raw_df([_default_row(**{"Vol.": "GARBAGE_VOLUME"})])
        df_clean, result = clean(df)
        # The row should still be present in output (not silently dropped).
        assert len(df_clean) == 1
        # But an issue should be reported for the bad volume.
        vol_issues = [
            i for i in result.issues
            if i.field == "Vol." and "Unparseable" in i.reason
        ]
        assert len(vol_issues) >= 1

    def test_reproducible_output(self):
        """Running clean() twice on the same input produces identical output."""
        rows = [_default_row(**{"Date": f"0{i+1}/01/2020"}) for i in range(3)]
        df = _make_raw_df(rows)
        df1, _ = clean(df.copy())
        df2, _ = clean(df.copy())
        pd.testing.assert_frame_equal(df1, df2)

    def test_whitespace_stripped_from_fields(self):
        """Leading/trailing whitespace in raw values is stripped."""
        df = _make_raw_df([_default_row(**{"Price": "  418.75  ", "Vol.": "  21.48M  "})])
        df_clean, _ = clean(df)
        assert df_clean["close"].iloc[0] == pytest.approx(418.75)
        assert df_clean["volume"].iloc[0] == pytest.approx(21_480_000)

    def test_change_pct_src_reference_column_present(self):
        """The reference column change_pct_src must be present in the clean output."""
        df = _make_raw_df([_default_row()])
        df_clean, _ = clean(df)
        assert "change_pct_src" in df_clean.columns

    def test_raw_dataframe_not_mutated(self):
        """clean() must not modify the original raw DataFrame."""
        df = _make_raw_df([_default_row()])
        original_cols = list(df.columns)
        original_values = df["Price"].copy()
        clean(df)
        assert list(df.columns) == original_cols
        pd.testing.assert_series_equal(df["Price"], original_values)
