"""
quant/data/ingestion.py
-----------------------
Raw CSV loader for QuantEdge Sprint 1.

Responsibility:
  - Read the raw ITC CSV from disk.
  - Apply ZERO transformations (all values remain as raw strings).
  - Return a DataFrame plus an IngestionResult metadata object.

Do NOT clean, parse, or coerce types here.
Cleaning is the responsibility of quant.data.cleaning.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Expected raw column names exactly as they appear in the source file.
EXPECTED_RAW_COLUMNS: list[str] = [
    "Date",
    "Price",
    "Open",
    "High",
    "Low",
    "Vol.",
    "Change %",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class IngestionResult:
    """Metadata produced by the ingestion step."""

    source_path: str
    source_filename: str
    raw_row_count: int
    raw_columns: list[str]
    unexpected_columns: list[str]
    missing_expected_columns: list[str]
    file_sha256: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when there are no hard errors."""
        return len(self.errors) == 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256_of_file(path: Path) -> str:
    """Return the hex SHA-256 digest of a file without loading it all into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_raw_csv(path: str | os.PathLike) -> tuple[pd.DataFrame, IngestionResult]:
    """
    Load the raw ITC CSV from *path* without any transformation.

    Parameters
    ----------
    path:
        Absolute or relative path to the source CSV file.

    Returns
    -------
    df : pd.DataFrame
        Raw DataFrame with all values as strings (dtype=object).
    result : IngestionResult
        Metadata about the ingestion step.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file is empty or cannot be parsed as CSV.
    """
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Raw CSV not found: {src}")

    # Compute file hash BEFORE reading so we can confirm the file is unchanged later.
    file_hash = _sha256_of_file(src)

    # Read everything as strings to preserve exact source values.
    # quoting=csv.QUOTE_ALL is the source convention, pandas handles it automatically.
    try:
        df = pd.read_csv(
            src,
            dtype=str,          # all columns as raw strings
            keep_default_na=False,  # do NOT silently convert "" to NaN here
            skipinitialspace=True,
        )
    except Exception as exc:
        raise ValueError(f"Failed to parse CSV at {src}: {exc}") from exc

    if df.empty:
        raise ValueError(f"CSV at {src} is empty (no data rows).")

    raw_columns: list[str] = list(df.columns)
    raw_row_count: int = len(df)

    unexpected = [c for c in raw_columns if c not in EXPECTED_RAW_COLUMNS]
    missing = [c for c in EXPECTED_RAW_COLUMNS if c not in raw_columns]

    warnings: list[str] = []
    errors: list[str] = []

    if unexpected:
        warnings.append(f"Unexpected columns in source: {unexpected}")
    if missing:
        errors.append(f"Missing expected columns in source: {missing}")

    result = IngestionResult(
        source_path=str(src),
        source_filename=src.name,
        raw_row_count=raw_row_count,
        raw_columns=raw_columns,
        unexpected_columns=unexpected,
        missing_expected_columns=missing,
        file_sha256=file_hash,
        warnings=warnings,
        errors=errors,
    )

    return df, result


def verify_source_unchanged(path: str | os.PathLike, expected_sha256: str) -> bool:
    """
    Return True if the file at *path* still has the same SHA-256 as *expected_sha256*.

    Use this after the pipeline completes to confirm the raw file was not modified.
    """
    src = Path(path).resolve()
    current = _sha256_of_file(src)
    return current == expected_sha256
