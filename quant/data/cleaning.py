"""
quant/data/cleaning.py
----------------------
Deterministic cleaning pipeline for QuantEdge Sprint 1.

Responsibility:
  - Accept the raw DataFrame from ingestion.py.
  - Apply a deterministic sequence of cleaning steps.
  - Produce a canonical DataFrame with the schema:
        date, symbol, open, high, low, close, volume
  - Also carry a reference column `change_pct_src` (parsed from source
    "Change %") for use by validation.py — this column is NOT written
    to the final processed CSV.
  - Emit a CleaningResult with every issue discovered.

Cleaning rules:
  1.  Strip leading/trailing whitespace from all string fields.
  2.  Replace empty strings with NaN.
  3.  Parse Date (MM/DD/YYYY) → datetime.date.
  4.  Parse Price, Open, High, Low → float.
  5.  Parse Vol. → int via K/M/B multiplier (see parse_volume).
  6.  Parse Change % → float (reference only, not in canonical output).
  7.  Detect exact duplicate rows (before any transformation).
  8.  Detect duplicate dates (after date parsing).
  9.  Sort ascending by date.
  10. Rename to canonical column names.
  11. Add symbol = "ITC".

DO NOT fabricate, interpolate, or invent values.
DO NOT silently drop rows — report every removal with a reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default symbol (used when clean() is called without an explicit symbol argument).
# Sprint 5: symbol is now a runtime parameter, not a module-level constant.
_DEFAULT_SYMBOL = "ITC"

# Canonical output columns (without the reference change_pct_src).
CANONICAL_COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume"]

# Source → canonical rename map.
_RENAME_MAP = {
    "Date": "date",
    "Price": "close",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Vol.": "volume",
}

# Volume suffix multipliers.
_VOL_MULTIPLIERS: dict[str, int] = {
    "K": 1_000,
    "M": 1_000_000,
    "B": 1_000_000_000,
}

# Regex for volume strings: optional sign, numeric part, optional suffix.
_VOL_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*([KMBkmb])?\s*$")

# Regex for percentage strings: optional sign, numeric part, % sign.
_PCT_RE = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*%\s*$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CleaningIssue:
    """A single issue discovered during cleaning."""

    row_index: Optional[int]   # 0-based original row index; None = global issue
    field: Optional[str]       # Column name; None = whole-row issue
    raw_value: Optional[str]   # The raw value that caused the issue
    reason: str                # Human-readable explanation
    action: str                # "reported" | "removed"


@dataclass
class CleaningResult:
    """Summary produced by the cleaning step."""

    original_row_count: int
    duplicate_exact_count: int
    duplicate_date_count: int
    removed_row_count: int
    final_row_count: int
    issues: list[CleaningIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_issue(
        self,
        reason: str,
        action: str,
        row_index: Optional[int] = None,
        field: Optional[str] = None,
        raw_value: Optional[str] = None,
    ) -> None:
        self.issues.append(
            CleaningIssue(
                row_index=row_index,
                field=field,
                raw_value=raw_value,
                reason=reason,
                action=action,
            )
        )


# ---------------------------------------------------------------------------
# Pure parsing helpers (importable and testable independently)
# ---------------------------------------------------------------------------


def parse_volume(raw: str) -> Optional[float]:
    """
    Convert a volume string to a numeric value.

    Supported formats:
        "21.48M"  → 21_480_000.0
        "5.78M"   → 5_780_000.0
        "431.85M" → 431_850_000.0
        "1.5K"    → 1_500.0
        "1.2B"    → 1_200_000_000.0
        "12345"   → 12_345.0
        ""        → None
        "-"       → None
        "N/A"     → None

    Returns None for unrecognisable or missing values.

    Parameters
    ----------
    raw : str
        The raw volume string from the source CSV.

    Returns
    -------
    float | None
        Parsed numeric volume, or None if unparseable / missing.
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if s in ("", "-", "N/A", "n/a", "NA", "na", "null", "NULL"):
        return None

    m = _VOL_RE.match(s)
    if m is None:
        return None

    numeric_part = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    multiplier = _VOL_MULTIPLIERS.get(suffix, 1)
    return numeric_part * multiplier


def parse_change_pct(raw: str) -> Optional[float]:
    """
    Parse a percentage string to a decimal fraction.

    "−0.35%"  → −0.0035
    "2.39%"   → 0.0239
    ""        → None

    Parameters
    ----------
    raw : str
        The raw Change % string from the source CSV.

    Returns
    -------
    float | None
        Parsed fractional value, or None if unparseable / missing.
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if s in ("", "-", "N/A", "n/a"):
        return None

    m = _PCT_RE.match(s)
    if m is None:
        return None

    return float(m.group(1)) / 100.0


def parse_date(raw: str) -> Optional[pd.Timestamp]:
    """
    Parse a date string in MM/DD/YYYY format.

    Parameters
    ----------
    raw : str
        The raw Date string from the source CSV.

    Returns
    -------
    pd.Timestamp | None
        Parsed timestamp (date only), or None if unparseable / missing.
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        return pd.to_datetime(s, format="%m/%d/%Y")
    except Exception:
        return None


def parse_price(raw: str) -> Optional[float]:
    """
    Parse a price/OHLC string to float.

    Strips commas (e.g. "1,234.56" → 1234.56).

    Parameters
    ----------
    raw : str
        The raw price string from the source CSV.

    Returns
    -------
    float | None
        Parsed float, or None if unparseable / missing.
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip().replace(",", "")
    if s in ("", "-", "N/A", "n/a"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------


def clean(df_raw: pd.DataFrame, symbol: str = _DEFAULT_SYMBOL) -> tuple[pd.DataFrame, CleaningResult]:
    """
    Apply the full deterministic cleaning sequence to the raw DataFrame.

    Parameters
    ----------
    df_raw : pd.DataFrame
        Raw DataFrame as returned by ingestion.load_raw_csv (all string dtype).
    symbol : str, optional
        The equity symbol to embed in the canonical ``symbol`` column.
        Defaults to "ITC" for backward compatibility with Sprint 1-4 code.

    Returns
    -------
    df_clean : pd.DataFrame
        Canonical DataFrame with columns:
            date, symbol, open, high, low, close, volume
        Plus a reference column `change_pct_src` (float, decimal fraction).
        Sorted ascending by date.
    result : CleaningResult
        Full record of issues discovered during cleaning.
    """
    result = CleaningResult(
        original_row_count=len(df_raw),
        duplicate_exact_count=0,
        duplicate_date_count=0,
        removed_row_count=0,
        final_row_count=0,
    )

    # Work on a copy; never mutate the raw DataFrame.
    df = df_raw.copy()

    # ------------------------------------------------------------------
    # Step 1: Strip whitespace from all string fields.
    # ------------------------------------------------------------------
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    # ------------------------------------------------------------------
    # Step 2: Replace empty strings with NaN.
    # ------------------------------------------------------------------
    df.replace("", np.nan, inplace=True)

    # ------------------------------------------------------------------
    # Step 3: Detect exact duplicate rows (on raw strings, before parsing).
    # ------------------------------------------------------------------
    exact_dup_mask = df.duplicated(keep="first")
    exact_dup_count = int(exact_dup_mask.sum())
    result.duplicate_exact_count = exact_dup_count

    if exact_dup_count > 0:
        dup_indices = df.index[exact_dup_mask].tolist()
        result.add_issue(
            reason=f"{exact_dup_count} exact duplicate row(s) detected; keeping first occurrence.",
            action="removed",
            row_index=None,
            field=None,
            raw_value=str(dup_indices[:10]),  # show up to 10 indices
        )
        for idx in dup_indices:
            result.add_issue(
                reason="Exact duplicate row — removed (keeping first occurrence).",
                action="removed",
                row_index=int(idx),
                field=None,
                raw_value=str(df.loc[idx].to_dict()),
            )
        df = df[~exact_dup_mask].copy()
        result.removed_row_count += exact_dup_count

    # ------------------------------------------------------------------
    # Step 4: Parse each column.
    # ------------------------------------------------------------------

    # Date
    raw_dates = df["Date"] if "Date" in df.columns else pd.Series(dtype=str)
    df["_date_parsed"] = raw_dates.apply(
        lambda v: parse_date(v) if pd.notna(v) else None
    )
    bad_date_mask = df["_date_parsed"].isna() & df["Date"].notna()
    for idx in df.index[bad_date_mask]:
        result.add_issue(
            reason=f"Unparseable date value; cannot determine chronological position.",
            action="reported",
            row_index=int(idx),
            field="Date",
            raw_value=str(df.at[idx, "Date"]),
        )

    # OHLC prices
    for src_col, label in [
        ("Price", "close"),
        ("Open", "open"),
        ("High", "high"),
        ("Low", "low"),
    ]:
        if src_col not in df.columns:
            result.errors.append(f"Expected column '{src_col}' not found in raw data.")
            continue
        parsed_col = f"_{label}_parsed"
        df[parsed_col] = df[src_col].apply(
            lambda v: parse_price(v) if pd.notna(v) else None
        )
        bad_mask = df[parsed_col].isna() & df[src_col].notna()
        for idx in df.index[bad_mask]:
            result.add_issue(
                reason=f"Unparseable {label} value.",
                action="reported",
                row_index=int(idx),
                field=src_col,
                raw_value=str(df.at[idx, src_col]),
            )

    # Volume
    if "Vol." in df.columns:
        df["_volume_parsed"] = df["Vol."].apply(
            lambda v: parse_volume(v) if pd.notna(v) else None
        )
        bad_vol_mask = df["_volume_parsed"].isna() & df["Vol."].notna()
        for idx in df.index[bad_vol_mask]:
            result.add_issue(
                reason="Unparseable or unrecognised volume string.",
                action="reported",
                row_index=int(idx),
                field="Vol.",
                raw_value=str(df.at[idx, "Vol."]),
            )
    else:
        df["_volume_parsed"] = np.nan
        result.warnings.append("Column 'Vol.' not found in raw data; volume will be NaN.")

    # Change % (reference only)
    if "Change %" in df.columns:
        df["_change_pct_parsed"] = df["Change %"].apply(
            lambda v: parse_change_pct(v) if pd.notna(v) else None
        )
        bad_pct_mask = df["_change_pct_parsed"].isna() & df["Change %"].notna()
        for idx in df.index[bad_pct_mask]:
            result.add_issue(
                reason="Unparseable Change % string.",
                action="reported",
                row_index=int(idx),
                field="Change %",
                raw_value=str(df.at[idx, "Change %"]),
            )
    else:
        df["_change_pct_parsed"] = np.nan
        result.warnings.append(
            "Column 'Change %' not found; Change % cross-validation will be skipped."
        )

    # ------------------------------------------------------------------
    # Step 5: Detect duplicate dates (after parsing).
    # ------------------------------------------------------------------
    valid_date_mask = df["_date_parsed"].notna()
    date_counts = df.loc[valid_date_mask, "_date_parsed"].value_counts()
    dup_dates = date_counts[date_counts > 1].index.tolist()
    result.duplicate_date_count = len(dup_dates)
    for dt in dup_dates:
        dup_rows = df.index[df["_date_parsed"] == dt].tolist()
        result.add_issue(
            reason=f"Duplicate date {dt.date()} appears {date_counts[dt]} times "
                   f"at source rows {dup_rows}. Keeping first occurrence.",
            action="removed",
            row_index=None,
            field="Date",
            raw_value=str(dt.date()),
        )
        # Keep first occurrence of each duplicate date.
        keep_idx = dup_rows[0]
        remove_idxs = dup_rows[1:]
        for idx in remove_idxs:
            result.add_issue(
                reason=f"Duplicate date {dt.date()} — removed (keeping row {keep_idx}).",
                action="removed",
                row_index=int(idx),
                field="Date",
                raw_value=str(dt.date()),
            )
            result.removed_row_count += 1

    if dup_dates:
        # Remove later-index duplicates of duplicate dates.
        df = df.sort_values("_date_parsed").drop_duplicates(
            subset=["_date_parsed"], keep="first"
        )

    # ------------------------------------------------------------------
    # Step 6: Sort ascending by date.
    # ------------------------------------------------------------------
    df = df.sort_values("_date_parsed", ascending=True, na_position="last").reset_index(
        drop=True
    )

    # ------------------------------------------------------------------
    # Step 7: Build canonical DataFrame.
    # ------------------------------------------------------------------
    canonical = pd.DataFrame()
    canonical["date"] = df["_date_parsed"].dt.date  # python date objects
    canonical["symbol"] = symbol
    canonical["open"] = df["_open_parsed"].astype(float)
    canonical["high"] = df["_high_parsed"].astype(float)
    canonical["low"] = df["_low_parsed"].astype(float)
    canonical["close"] = df["_close_parsed"].astype(float)
    # Volume stored as float (Int64-compatible) to allow NaN.
    canonical["volume"] = df["_volume_parsed"]
    # Reference column — NOT written to canonical CSV output.
    canonical["change_pct_src"] = df["_change_pct_parsed"]

    result.final_row_count = len(canonical)
    return canonical, result
