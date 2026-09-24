"""
quant/data/pipeline.py
----------------------
Top-level orchestrator for the QuantEdge data pipeline.

Sprint 5: Generalized to support any symbol in the registry.
Sprint 1 legacy: zero-arg call still works for ITC backward compat.

Entry points:
    python -m quant.data.pipeline                      # ITC (legacy)
    python -m quant.data.pipeline --symbol ITC
    python -m quant.data.pipeline --symbols ITC RELIANCE TCS

Sequence (per symbol):
    1. Ingest raw CSV                 (sources/csv_source.py)
    2. Clean / parse / deduplicate    (cleaning.py)
    3. Validate                       (validation.py)
    4. Write canonical CSV            → Data/processed/stocks/{SYMBOL}.csv
    5. Write JSON report              → Data/reports/stocks/{SYMBOL}_data_quality.json
    6. Write Markdown report          → Data/reports/stocks/{SYMBOL}_data_quality.md
    7. Verify raw file is unchanged   (ingestion.verify_source_unchanged)

Running the pipeline twice on the same raw input produces identical outputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from quant.data.ingestion import load_raw_csv, verify_source_unchanged
from quant.data.cleaning import clean, CANONICAL_COLUMNS
from quant.data.validation import validate, report_to_dict, ValidationReport
from quant.data.registry import (
    get_raw_path,
    get_processed_path,
    get_quality_report_paths,
    get_symbol_config,
    SYMBOL_REGISTRY,
    VALID_SYMBOLS,
)


# ---------------------------------------------------------------------------
# Path configuration (legacy ITC constants — kept for backward compat)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent

# Legacy ITC paths (Sprint 1-4 backward compat; not used by new pipeline).
RAW_CSV      = PROJECT_ROOT / "Data" / "raw" / "ITC Stock Price History.csv"
PROCESSED_CSV = PROJECT_ROOT / "Data" / "processed" / "itc_daily_clean.csv"
REPORT_JSON  = PROJECT_ROOT / "Data" / "reports" / "itc_data_quality.json"
REPORT_MD    = PROJECT_ROOT / "Data" / "reports" / "itc_data_quality.md"


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def _write_json_report(report: ValidationReport, path: Path) -> None:
    """Serialise the report to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    d = report_to_dict(report)
    d["generated_at"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, default=str)
    print(f"  [report] JSON -> {path}")


def _write_markdown_report(report: ValidationReport, path: Path) -> None:
    """Render the report as a human-readable Markdown document."""
    path.parent.mkdir(parents=True, exist_ok=True)

    status_badge = {
        "PASS": "PASS",
        "WARNING": "WARNING",
        "FAIL": "FAIL",
    }.get(report.status, report.status)

    ohlc_section = ""
    if report.ohlc_violations:
        rows = []
        for v in report.ohlc_violations[:20]:
            rows.append(
                f"| {v.row_index} | {v.date} | {v.open} | {v.high} | "
                f"{v.low} | {v.close} | {', '.join(v.violated_rules)} |"
            )
        table = "\n".join(rows)
        ohlc_section = f"""
### OHLC Violations ({report.invalid_ohlc_count} total)

| Row | Date | Open | High | Low | Close | Violated Rules |
|-----|------|------|------|-----|-------|----------------|
{table}
"""
        if report.invalid_ohlc_count > 20:
            ohlc_section += (
                f"\n> Only first 20 of {report.invalid_ohlc_count} shown. "
                "See JSON report for full list.\n"
            )

    change_section = ""
    if report.change_pct_mismatch_count > 0:
        rows = []
        for m in report.change_pct_mismatches[:20]:
            rows.append(
                f"| {m.row_index} | {m.date} | {m.close_t:.4f} | "
                f"{m.close_t_minus_1:.4f} | {m.computed_change_pct*100:.4f}% | "
                f"{m.source_change_pct*100:.4f}% | {m.absolute_diff*100:.4f}% |"
            )
        table = "\n".join(rows)
        change_section = f"""
### Change % Cross-Validation Mismatches ({report.change_pct_mismatch_count} total)

| Row | Date | Close(t) | Close(t-1) | Computed % | Source % | |Diff| |
|-----|------|----------|-----------|------------|----------|-------|
{table}
"""

    md = f"""# {report.symbol} Data Quality Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Overall Status: {status_badge}

---

## Summary

| Metric | Value |
|--------|-------|
| Source file | `{report.source_filename}` |
| Symbol | `{report.symbol}` |
| Original row count | {report.original_row_count} |
| Final row count | {report.final_row_count} |
| Removed row count | {report.removed_row_count} |
| Date range | {report.date_min} to {report.date_max} |

---

## Missing Values

| Column | Missing Count |
|--------|--------------|
"""
    for col, cnt in report.missing_counts.items():
        md += f"| `{col}` | {cnt} |\n"

    md += f"""
---

## OHLC Consistency

| Metric | Value |
|--------|-------|
| Invalid OHLC rows | {report.invalid_ohlc_count} |

{ohlc_section}

---

## Volume

| Metric | Value |
|--------|-------|
| Missing (NaN) volume rows | {report.invalid_volume_count} |
| Zero volume rows | {report.zero_volume_count} |
| Negative volume rows | {report.negative_volume_count} |

---

## Date Integrity

| Metric | Value |
|--------|-------|
| Invalid/unparseable dates | {report.invalid_date_count} |
| Non-monotonic date rows | {report.non_monotonic_date_count} |

---

## Change % Cross-Validation

| Metric | Value |
|--------|-------|
| Tolerance | 0.50% |
| Mismatches found | {report.change_pct_mismatch_count} |
| Skipped | {report.change_pct_skipped} |
"""
    if report.change_pct_skipped:
        md += f"| Reason | {report.change_pct_skipped_reason} |\n"

    md += change_section

    if report.warnings or report.cleaning_warnings:
        md += "\n---\n\n## Warnings\n\n"
        for w in report.warnings + report.cleaning_warnings:
            md += f"- {w}\n"

    if report.errors or report.cleaning_errors:
        md += "\n---\n\n## Errors\n\n"
        for e in report.errors + report.cleaning_errors:
            md += f"- {e}\n"

    md += """
---

*This report was auto-generated by QuantEdge data pipeline.*
*Source Change % is a reference field; Close price is authoritative.*
"""

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(md)
    print(f"  [report] Markdown -> {path}")


# ---------------------------------------------------------------------------
# Per-symbol pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    symbol: str = "ITC",
    raw_path: Optional[Path] = None,
    processed_path: Optional[Path] = None,
    report_json_path: Optional[Path] = None,
    report_md_path: Optional[Path] = None,
) -> ValidationReport:
    """
    Execute the full data pipeline for one symbol.

    Parameters
    ----------
    symbol : str
        NSE equity symbol (must be in the registry). Defaults to "ITC".
    raw_path : Path, optional
        Override the raw source CSV path. Uses registry default if None.
    processed_path : Path, optional
        Override the output canonical CSV path. Uses registry default if None.
    report_json_path : Path, optional
        Override the JSON report path. Uses registry default if None.
    report_md_path : Path, optional
        Override the Markdown report path. Uses registry default if None.

    Returns
    -------
    ValidationReport
        The completed validation report.
    """
    from quant.data.registry import SYMBOL_REGISTRY
    if symbol not in SYMBOL_REGISTRY and raw_path is None:
        print(f"[!!] Unknown symbol '{symbol}'. Known: {sorted(SYMBOL_REGISTRY)}")
        sys.exit(1)

    # Resolve paths from registry if not overridden.
    if raw_path is None:
        raw_path = get_raw_path(symbol)
    if processed_path is None:
        processed_path = get_processed_path(symbol)
    if report_json_path is None:
        report_json_path, _md = get_quality_report_paths(symbol)
    if report_md_path is None:
        _, report_md_path = get_quality_report_paths(symbol)

    print("=" * 60)
    print(f"QuantEdge -- Data Pipeline  [{symbol}]")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Ingest
    # ------------------------------------------------------------------
    print(f"\n[1/5] Ingesting: {raw_path}")
    df_raw, ingest_result = load_raw_csv(raw_path)
    print(f"      Rows loaded : {ingest_result.raw_row_count}")
    print(f"      Columns     : {ingest_result.raw_columns}")
    print(f"      SHA-256     : {ingest_result.file_sha256[:16]}...")

    if not ingest_result.ok:
        print("\n[!!] Ingestion errors:")
        for e in ingest_result.errors:
            print(f"   {e}")
        sys.exit(1)

    if ingest_result.warnings:
        for w in ingest_result.warnings:
            print(f"  [!!] {w}")

    # ------------------------------------------------------------------
    # 2. Clean (pass symbol so canonical DataFrame has correct symbol col)
    # ------------------------------------------------------------------
    print("\n[2/5] Cleaning...")
    df_clean, clean_result = clean(df_raw, symbol=symbol)
    print(f"      Exact duplicates removed : {clean_result.duplicate_exact_count}")
    print(f"      Duplicate dates removed  : {clean_result.duplicate_date_count}")
    print(f"      Total rows removed       : {clean_result.removed_row_count}")
    print(f"      Final row count          : {clean_result.final_row_count}")

    if clean_result.errors:
        print("\n  Cleaning errors:")
        for e in clean_result.errors:
            print(f"    [!!] {e}")

    if clean_result.warnings:
        for w in clean_result.warnings:
            print(f"    [!!] {w}")

    # ------------------------------------------------------------------
    # 3. Validate
    # ------------------------------------------------------------------
    print("\n[3/5] Validating...")
    report = validate(df_clean, clean_result, source_filename=raw_path.name)
    print(f"      OHLC violations     : {report.invalid_ohlc_count}")
    print(f"      Missing volume rows : {report.invalid_volume_count}")
    print(f"      Change % mismatches : {report.change_pct_mismatch_count}")
    print(f"      Non-monotonic dates : {report.non_monotonic_date_count}")
    print(f"      Overall status      : {report.status}")

    # ------------------------------------------------------------------
    # 4. Write canonical CSV
    # ------------------------------------------------------------------
    print(f"\n[4/5] Writing canonical CSV -> {processed_path}")
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    df_output = df_clean[CANONICAL_COLUMNS].copy()
    df_output.to_csv(processed_path, index=False)
    print(f"      Rows written: {len(df_output)}")

    # ------------------------------------------------------------------
    # 5. Write reports
    # ------------------------------------------------------------------
    print(f"\n[5/5] Writing reports...")
    _write_json_report(report, report_json_path)
    _write_markdown_report(report, report_md_path)

    # ------------------------------------------------------------------
    # Post-run: verify raw file is unchanged
    # ------------------------------------------------------------------
    unchanged = verify_source_unchanged(raw_path, ingest_result.file_sha256)
    if unchanged:
        print(f"\n[OK] Raw file integrity verified (SHA-256 unchanged).")
    else:
        print(f"\n[!!] WARNING: Raw file SHA-256 has changed!")

    print("\n" + "=" * 60)
    print(f"Pipeline complete [{symbol}]. Status: {report.status}")
    print("=" * 60)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="QuantEdge Data Pipeline — ingest, clean, and validate NSE equity data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "--symbol",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Process a single symbol (e.g. ITC).",
    )
    group.add_argument(
        "--symbols",
        nargs="+",
        type=str,
        default=None,
        metavar="SYMBOL",
        help="Process multiple symbols (e.g. ITC RELIANCE TCS).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.symbols:
        symbols = args.symbols
    elif args.symbol:
        symbols = [args.symbol]
    else:
        symbols = ["ITC"]  # legacy default

    any_fail = False
    for sym in symbols:
        try:
            report = run_pipeline(symbol=sym)
            if report.status == "FAIL":
                any_fail = True
        except Exception as exc:
            print(f"\n[!!] Pipeline failed for {sym}: {exc}")
            any_fail = True

    if any_fail:
        sys.exit(1)
