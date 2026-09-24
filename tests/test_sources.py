"""
tests/test_sources.py
---------------------
Unit tests for quant.data.sources.

Tests use synthetic CSV files in a temp directory.
No real market data is required.
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from quant.data.sources.base import BaseSource, SourceMetadata
from quant.data.sources.csv_source import InvestingComSource, INVESTING_COM_COLUMNS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_investing_csv(path: Path, rows: list[dict], extra_col: bool = False) -> None:
    """Write a valid Investing.com-format CSV."""
    fieldnames = list(INVESTING_COM_COLUMNS)
    if extra_col:
        fieldnames.append("ExtraCol")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _minimal_rows(n: int = 3, symbol: str = "TEST") -> list[dict]:
    return [
        {
            "Date": f"05/{(i+1):02d}/2024",
            "Price": "100.00",
            "Open": "99.00",
            "High": "101.00",
            "Low": "98.00",
            "Vol.": "1.5M",
            "Change %": "1.00%",
        }
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# InvestingComSource
# ---------------------------------------------------------------------------


class TestInvestingComSource:

    def test_source_name(self):
        src = InvestingComSource()
        assert src.source_name == "InvestingCom"

    def test_load_valid_csv(self, tmp_path):
        csv_path = tmp_path / "TEST.csv"
        _write_investing_csv(csv_path, _minimal_rows(5))
        src = InvestingComSource()
        df, meta = src.load(csv_path, symbol="TEST")

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 5
        # All values are strings (no type coercion applied).
        # In pandas 3+, string columns may show as 'str' dtype (not 'object').
        # The key invariant: no column should be numeric.
        for col in df.columns:
            assert not pd.api.types.is_numeric_dtype(df[col]), \
                f"Column '{col}' should be string, not numeric"

    def test_metadata_populated(self, tmp_path):
        csv_path = tmp_path / "ITC.csv"
        _write_investing_csv(csv_path, _minimal_rows(3))
        src = InvestingComSource()
        _, meta = src.load(csv_path, symbol="ITC")

        assert meta.source_name == "InvestingCom"
        assert meta.symbol == "ITC"
        assert meta.raw_row_count == 3
        assert meta.source_file == "ITC.csv"
        assert len(meta.raw_file_hash) == 64  # SHA-256 hex

    def test_file_not_found_raises(self, tmp_path):
        src = InvestingComSource()
        with pytest.raises(FileNotFoundError):
            src.load(tmp_path / "nonexistent.csv", symbol="TEST")

    def test_empty_file_raises(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text("")
        src = InvestingComSource()
        with pytest.raises(ValueError, match="empty"):
            src.load(csv_path, symbol="TEST")

    def test_missing_required_column_raises(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        # Write CSV missing "Vol." column
        with open(csv_path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["Date", "Price", "Open", "High", "Low", "Change %"])
            writer.writeheader()
            writer.writerow({"Date": "01/01/2024", "Price": "100", "Open": "99",
                             "High": "101", "Low": "98", "Change %": "1%"})
        src = InvestingComSource()
        with pytest.raises(ValueError, match="Missing expected columns"):
            src.load(csv_path, symbol="TEST")

    def test_extra_columns_do_not_raise(self, tmp_path):
        """Extra columns in source are allowed (only required columns are checked)."""
        csv_path = tmp_path / "extra.csv"
        _write_investing_csv(csv_path, _minimal_rows(2), extra_col=True)
        src = InvestingComSource()
        df, meta = src.load(csv_path, symbol="TEST")
        assert len(df) == 2

    def test_returns_raw_strings(self, tmp_path):
        """Source must NOT parse or coerce types."""
        csv_path = tmp_path / "TEST.csv"
        rows = [{"Date": "05/01/2024", "Price": "1,234.56", "Open": "1,200.00",
                 "High": "1,250.00", "Low": "1,195.00", "Vol.": "2.5M", "Change %": "2.00%"}]
        _write_investing_csv(csv_path, rows)
        src = InvestingComSource()
        df, _ = src.load(csv_path, symbol="TEST")
        # Raw value preserved — commas not stripped
        assert df.iloc[0]["Price"] == "1,234.56"

    def test_symbol_stored_in_metadata(self, tmp_path):
        csv_path = tmp_path / "RELIANCE.csv"
        _write_investing_csv(csv_path, _minimal_rows(1))
        src = InvestingComSource()
        _, meta = src.load(csv_path, symbol="RELIANCE")
        assert meta.symbol == "RELIANCE"

    def test_is_subclass_of_base_source(self):
        assert issubclass(InvestingComSource, BaseSource)
