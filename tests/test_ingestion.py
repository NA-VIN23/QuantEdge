"""
tests/test_ingestion.py
-----------------------
Unit tests for quant.data.ingestion.

Tests use small synthetic CSV files written to a temporary directory.
None of these tests depend on the full ITC dataset.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from quant.data.ingestion import (
    EXPECTED_RAW_COLUMNS,
    IngestionResult,
    load_raw_csv,
    verify_source_unchanged,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    """Write a list of dicts to a CSV file."""
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _minimal_csv_row() -> dict:
    return {
        "Date": "05/29/2025",
        "Price": "418.75",
        "Open": "422.00",
        "High": "422.80",
        "Low": "416.60",
        "Vol.": "21.48M",
        "Change %": "-0.35%",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadRawCsv:

    def test_loads_valid_file(self, tmp_path: Path) -> None:
        """Happy-path: well-formed CSV loads successfully."""
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        df, result = load_raw_csv(p)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    def test_returns_ingestion_result(self, tmp_path: Path) -> None:
        """load_raw_csv must return an IngestionResult."""
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, result = load_raw_csv(p)
        assert isinstance(result, IngestionResult)

    def test_all_values_are_strings(self, tmp_path: Path) -> None:
        """Raw ingestion must NOT coerce any column to numeric.

        pandas 3.x may return StringDtype (dtype.name == 'str') rather than
        object dtype for string columns. Either is acceptable — what matters
        is that no column is numeric.
        """
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        df, _ = load_raw_csv(p)
        for col in df.columns:
            dtype_name = str(df[col].dtype)
            assert "int" not in dtype_name and "float" not in dtype_name, (
                f"Column '{col}' should remain as a string type, got {df[col].dtype}"
            )


    def test_expected_columns_detected(self, tmp_path: Path) -> None:
        """All expected columns should be detected; no unexpected columns."""
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, result = load_raw_csv(p)
        assert result.missing_expected_columns == []
        assert result.unexpected_columns == []
        assert result.ok is True

    def test_detects_unexpected_column(self, tmp_path: Path) -> None:
        """Extra columns in the source are surfaced as warnings."""
        row = {**_minimal_csv_row(), "ExtraCol": "something"}
        p = tmp_path / "test.csv"
        _write_csv(p, [row])
        _, result = load_raw_csv(p)
        assert "ExtraCol" in result.unexpected_columns
        assert len(result.warnings) > 0

    def test_detects_missing_expected_column(self, tmp_path: Path) -> None:
        """Missing expected columns are surfaced as errors."""
        row = _minimal_csv_row()
        del row["Vol."]
        p = tmp_path / "test.csv"
        _write_csv(p, [row])
        _, result = load_raw_csv(p)
        assert "Vol." in result.missing_expected_columns
        assert result.ok is False

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError raised for a missing path."""
        with pytest.raises(FileNotFoundError):
            load_raw_csv(tmp_path / "nonexistent.csv")

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        """ValueError raised for an empty CSV (no data rows)."""
        p = tmp_path / "empty.csv"
        # Write header only (no data rows).
        p.write_text("Date,Price,Open,High,Low,Vol.,Change %\n", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_raw_csv(p)

    def test_raw_row_count(self, tmp_path: Path) -> None:
        """raw_row_count matches the number of data rows in the file."""
        rows = [_minimal_csv_row() for _ in range(5)]
        p = tmp_path / "test.csv"
        _write_csv(p, rows)
        _, result = load_raw_csv(p)
        assert result.raw_row_count == 5

    def test_source_path_recorded(self, tmp_path: Path) -> None:
        """source_path and source_filename are set correctly."""
        p = tmp_path / "my_data.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, result = load_raw_csv(p)
        assert result.source_filename == "my_data.csv"
        assert str(p.resolve()) == result.source_path

    def test_sha256_computed(self, tmp_path: Path) -> None:
        """file_sha256 is a 64-character hex string."""
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, result = load_raw_csv(p)
        assert len(result.file_sha256) == 64
        assert all(c in "0123456789abcdef" for c in result.file_sha256)

    def test_sha256_changes_when_file_changes(self, tmp_path: Path) -> None:
        """SHA-256 must change if the file contents change."""
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, r1 = load_raw_csv(p)
        # Append a character to change the file.
        p.write_text(p.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        _, r2 = load_raw_csv(p)
        # The SHA-256 should be different (unless the file happened to be identical, which it won't be).
        # (We can't assert r1.file_sha256 != r2.file_sha256 reliably because the extra newline might
        # produce the same hash in degenerate cases — but in practice with CSV content it won't.)
        # Instead, verify that verify_source_unchanged detects the change.
        assert not verify_source_unchanged(p, r1.file_sha256)


class TestVerifySourceUnchanged:

    def test_returns_true_for_unchanged_file(self, tmp_path: Path) -> None:
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, result = load_raw_csv(p)
        assert verify_source_unchanged(p, result.file_sha256) is True

    def test_returns_false_for_changed_file(self, tmp_path: Path) -> None:
        p = tmp_path / "test.csv"
        _write_csv(p, [_minimal_csv_row()])
        _, result = load_raw_csv(p)
        # Modify the file.
        p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
        assert verify_source_unchanged(p, result.file_sha256) is False
