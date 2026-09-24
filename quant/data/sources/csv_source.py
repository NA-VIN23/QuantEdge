"""
quant/data/sources/csv_source.py
---------------------------------
InvestingComSource — loads historical OHLCV data in the Investing.com
CSV export format.

Investing.com column layout (as seen in ITC Stock Price History.csv):
    Date, Price, Open, High, Low, Vol., Change %

This source:
  - Reads the file as raw strings (no type coercion).
  - Validates that the expected columns are present.
  - Does NOT clean, parse, or rename columns.
  - Returns provenance metadata.

Cleaning and renaming are the responsibility of quant.data.cleaning.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pandas as pd

from quant.data.sources.base import BaseSource, SourceMetadata


# Expected column names in the Investing.com format.
INVESTING_COM_COLUMNS: list[str] = [
    "Date",
    "Price",
    "Open",
    "High",
    "Low",
    "Vol.",
    "Change %",
]


class InvestingComSource(BaseSource):
    """
    Data source for Investing.com CSV export format.

    This is the format used by the ITC historical dataset obtained from
    Investing.com. Each row contains: Date, Price (close), Open, High,
    Low, Vol. (volume with K/M/B suffix), Change %.

    Usage
    -----
    ::

        source = InvestingComSource()
        df, metadata = source.load(Path("data/raw/stocks/ITC.csv"), symbol="ITC")
    """

    source_name: ClassVar[str] = "InvestingCom"

    # Rename map from Investing.com column names to canonical names.
    # This is informational here — actual renaming is done in cleaning.py.
    COLUMN_MAP: ClassVar[dict[str, str]] = {
        "Date": "date",
        "Price": "close",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Vol.": "volume",
        "Change %": "change_pct_src",
    }

    def load(
        self,
        raw_path: Path,
        symbol: str,
    ) -> tuple[pd.DataFrame, SourceMetadata]:
        """
        Load raw data from an Investing.com-format CSV file.

        Parameters
        ----------
        raw_path : Path
            Path to the source CSV file.
        symbol : str
            The equity symbol (e.g. "ITC") this file represents.

        Returns
        -------
        df : pd.DataFrame
            Raw DataFrame, all columns as strings, columns exactly as in source.
        metadata : SourceMetadata
        """
        path = Path(raw_path).resolve()
        if not path.exists():
            raise FileNotFoundError(
                f"[InvestingComSource] Raw CSV not found: {path}"
            )

        # Hash before reading (proves file was not modified by our code).
        file_hash = self._sha256(path)

        try:
            df = pd.read_csv(
                path,
                dtype=str,
                keep_default_na=False,
                skipinitialspace=True,
            )
        except Exception as exc:
            raise ValueError(
                f"[InvestingComSource] Failed to parse CSV at {path}: {exc}"
            ) from exc

        if df.empty:
            raise ValueError(
                f"[InvestingComSource] CSV at {path} is empty (no data rows)."
            )

        # Validate expected columns are present.
        missing = [c for c in INVESTING_COM_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(
                f"[InvestingComSource] Missing expected columns in {path.name}: {missing}"
            )

        metadata = SourceMetadata(
            source_name=self.source_name,
            source_file=path.name,
            source_path=str(path),
            raw_file_hash=file_hash,
            raw_row_count=len(df),
            symbol=symbol,
        )

        return df, metadata
