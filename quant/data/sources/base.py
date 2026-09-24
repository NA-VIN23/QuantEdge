"""
quant/data/sources/base.py
---------------------------
Abstract base class for QuantEdge data sources.

A data source is responsible for:
  - Loading raw market data from a file or external system.
  - Returning a raw string DataFrame (no cleaning applied).
  - Providing provenance metadata.

A data source must NOT:
  - Clean, parse, or coerce types.
  - Apply validation.
  - Modify the raw file.

Cleaning is the responsibility of quant.data.cleaning.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Provenance metadata
# ---------------------------------------------------------------------------


@dataclass
class SourceMetadata:
    """Provenance information produced by a data source."""

    source_name: str       # Human-readable source name (e.g. "InvestingCom")
    source_file: str       # Filename (basename only, not full path)
    source_path: str       # Full resolved path
    raw_file_hash: str     # SHA-256 hex digest of the raw file
    raw_row_count: int     # Number of data rows (excluding header)
    symbol: str            # The equity symbol this data represents


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------


class BaseSource(ABC):
    """
    Abstract base class for all QuantEdge data sources.

    Subclasses must implement :meth:`load`, which reads raw data from
    a file path and returns a string DataFrame plus source metadata.

    The :attr:`source_name` class attribute must be set in every subclass.
    """

    source_name: str = "Unknown"

    @abstractmethod
    def load(
        self,
        raw_path: Path,
        symbol: str,
    ) -> tuple[pd.DataFrame, SourceMetadata]:
        """
        Load raw market data from *raw_path*.

        Parameters
        ----------
        raw_path : Path
            Path to the source file. Must exist.
        symbol : str
            The equity symbol (e.g. "ITC") this file represents.

        Returns
        -------
        df : pd.DataFrame
            Raw DataFrame with all values as strings (dtype=object).
            Column names are exactly as they appear in the source file.
        metadata : SourceMetadata
            Provenance information about the loaded data.

        Raises
        ------
        FileNotFoundError
            If *raw_path* does not exist.
        ValueError
            If the file is empty or cannot be parsed.
        """

    @staticmethod
    def _sha256(path: Path) -> str:
        """Return SHA-256 hex digest of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
