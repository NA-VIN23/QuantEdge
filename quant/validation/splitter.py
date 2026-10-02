"""
quant/validation/splitter.py
----------------------------
Chronological data splitter for Sprint 6 walk-forward validation.

Creates expanding-development / fixed-test-size windows from a
feature-enriched DataFrame. Never shuffles. Never allows future
data to influence a past decision.

Terminology (Sprint 6):
  Development window  → all historical data before a cutoff date
  Unseen test window  → the immediately following fixed-size period

==============================================================
TRUNCATION-INVARIANCE GUARANTEE
==============================================================

This module only slices the pre-computed features DataFrame.
It never recomputes indicators or signals. Because all indicators
in compute_all_features() are causal (depend only on data at or
before each row's date), slicing the DataFrame to a test window
[test_start, test_end] produces feature values that are identical
to those that would have been computed had only that sub-range of
data existed. No future rows can alter past feature values.

Formal property verified by tests/test_walk_forward.py:
    features(full_dataset).at[T] == features(data_through_T).at[T]

==============================================================
CHRONOLOGICAL ORDERING GUARANTEE
==============================================================

assert df['date'].is_monotonic_increasing is called before any
slice operation. Any violation raises immediately.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_INITIAL_DEV_YEARS: int = 3
DEFAULT_STEP_MONTHS: int = 6
DEFAULT_TEST_MONTHS: int = 6
DEFAULT_MIN_TEST_ROWS: int = 50


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DataSplit:
    """Metadata for one walk-forward window pair."""

    window_index: int
    symbol: str

    # Development period
    dev_start: str   # YYYY-MM-DD (first actual date in development slice)
    dev_end: str     # YYYY-MM-DD (last actual date in development slice)
    dev_rows: int

    # Unseen test period
    test_start: str  # YYYY-MM-DD (first actual date in test slice)
    test_end: str    # YYYY-MM-DD (last actual date in test slice)
    test_rows: int

    status: str = "OK"  # OK | INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def chronological_splits(
    df: pd.DataFrame,
    symbol: str = "ITC",
    initial_dev_years: int = DEFAULT_INITIAL_DEV_YEARS,
    step_months: int = DEFAULT_STEP_MONTHS,
    test_months: int = DEFAULT_TEST_MONTHS,
    min_test_rows: int = DEFAULT_MIN_TEST_ROWS,
) -> list[DataSplit]:
    """
    Generate expanding-development / fixed-test walk-forward splits.

    Parameters
    ----------
    df : pd.DataFrame
        Feature-enriched DataFrame. Must be sorted chronologically
        ascending and contain a 'date' column (string or Timestamp).
    symbol : str
        Symbol name — stored in metadata only.
    initial_dev_years : int
        Minimum years of development data before the first unseen window.
    step_months : int
        How many months forward each successive window advances.
    test_months : int
        Duration (in months) of each unseen test window.
    min_test_rows : int
        Minimum row count for a test window to be labelled "OK".
        Windows below this threshold are labelled "INSUFFICIENT_DATA".

    Returns
    -------
    list[DataSplit]
        Chronologically ordered list of window metadata. Both OK and
        INSUFFICIENT_DATA windows are returned; callers filter as needed.

    Raises
    ------
    ValueError
        If 'date' column is missing or the DataFrame is not sorted
        chronologically ascending.

    Notes
    -----
    - The development window EXPANDS on each step (not rolling).
    - Features are NOT recomputed inside this function.
    - reset_index(drop=True) is called on the working copy before slicing.
    """
    if "date" not in df.columns:
        raise ValueError("splitter: DataFrame must contain a 'date' column.")

    df = df.copy().reset_index(drop=True)
    dates = pd.to_datetime(df["date"]).reset_index(drop=True)

    if not dates.is_monotonic_increasing:
        raise ValueError(
            "splitter: DataFrame is not sorted chronologically ascending. "
            "Sort by 'date' before calling chronological_splits()."
        )

    if len(df) == 0:
        return []

    dataset_start = dates.iloc[0]
    dataset_end = dates.iloc[-1]

    # First development cutoff = dataset_start + initial_dev_years.
    current_dev_end = dataset_start + pd.DateOffset(years=initial_dev_years)

    splits: list[DataSplit] = []
    window_index = 0

    while True:
        test_start_ts = current_dev_end
        test_end_ts = test_start_ts + pd.DateOffset(months=test_months)

        # Stop when the test window would begin at or after the last date.
        if test_start_ts >= dataset_end:
            break

        # Clamp test_end to dataset_end.
        if test_end_ts > dataset_end:
            test_end_ts = dataset_end

        # --- Development slice: rows with date < test_start ---
        dev_mask = dates < test_start_ts
        dev_rows_count = int(dev_mask.sum())
        dev_start_str = str(dates[dev_mask].iloc[0].date()) if dev_rows_count > 0 else ""
        dev_end_str = str(dates[dev_mask].iloc[-1].date()) if dev_rows_count > 0 else ""

        # --- Test slice: rows with date in [test_start, test_end] ---
        test_mask = (dates >= test_start_ts) & (dates <= test_end_ts)
        test_rows_count = int(test_mask.sum())
        test_start_str = str(dates[test_mask].iloc[0].date()) if test_rows_count > 0 else ""
        test_end_str = str(dates[test_mask].iloc[-1].date()) if test_rows_count > 0 else ""

        status = "OK" if test_rows_count >= min_test_rows else "INSUFFICIENT_DATA"

        splits.append(DataSplit(
            window_index=window_index,
            symbol=symbol,
            dev_start=dev_start_str,
            dev_end=dev_end_str,
            dev_rows=dev_rows_count,
            test_start=test_start_str,
            test_end=test_end_str,
            test_rows=test_rows_count,
            status=status,
        ))

        window_index += 1
        current_dev_end = current_dev_end + pd.DateOffset(months=step_months)

    return splits


def slice_test_df(df: pd.DataFrame, split: DataSplit) -> pd.DataFrame:
    """
    Return the unseen test slice for *split* with a clean RangeIndex.

    Parameters
    ----------
    df : pd.DataFrame
        Full feature DataFrame (all rows).
    split : DataSplit
        A DataSplit produced by chronological_splits().

    Returns
    -------
    pd.DataFrame
        Rows where date is in [split.test_start, split.test_end],
        sorted chronologically, reset RangeIndex.
    """
    if not split.test_start or not split.test_end:
        return df.iloc[0:0].reset_index(drop=True)

    dates = pd.to_datetime(df["date"])
    mask = (dates >= pd.Timestamp(split.test_start)) & (
        dates <= pd.Timestamp(split.test_end)
    )
    return df[mask].reset_index(drop=True)


def slice_dev_df(df: pd.DataFrame, split: DataSplit) -> pd.DataFrame:
    """
    Return the development slice for *split* with a clean RangeIndex.

    Parameters
    ----------
    df : pd.DataFrame
        Full feature DataFrame (all rows).
    split : DataSplit
        A DataSplit produced by chronological_splits().

    Returns
    -------
    pd.DataFrame
        Rows where date < split.test_start, sorted chronologically,
        reset RangeIndex.
    """
    if not split.test_start:
        return df.reset_index(drop=True)

    dates = pd.to_datetime(df["date"])
    mask = dates < pd.Timestamp(split.test_start)
    return df[mask].reset_index(drop=True)
