"""
quant/api/context_builder.py
----------------------------
Context Builder for QuantEdge Research Assistant.
Provides purely read-only, verified context derived directly from pipeline JSON artifacts.
Ensures zero alteration to numbers/metrics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Tuple, List

from quant.data.registry import (
    get_backtest_dir,
    get_quality_report_paths,
    VALID_SYMBOLS,
    _require
)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_research_context(symbol: str) -> Tuple[str, List[str]]:
    """
    Build a safe, strictly read-only context string from verified QuantEdge outputs.
    Preserves all exact numerical values.

    Returns:
        (context_string, sources_list)
    """
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise ValueError(f"Symbol '{symbol}' is not recognised.")

    sources = []
    context_parts = []
    context_parts.append(f"RESEARCH CONTEXT FOR {symbol}")
    context_parts.append("===========================")

    # 1. Backtest Summary
    bt_dir = get_backtest_dir(symbol)
    summary_path = bt_dir / "summary.json"
    summary_data = _load_json(summary_path)

    if summary_data:
        sources.append(f"{symbol} backtest summary")
        context_parts.append("\n[1. BACKTEST SUMMARY]")
        context_parts.append(json.dumps(summary_data, indent=2))
    else:
        context_parts.append("\n[1. BACKTEST SUMMARY]")
        context_parts.append("Unavailable.")

    # 2. Data Quality
    dq_json_path, _ = get_quality_report_paths(symbol)
    dq_data = _load_json(dq_json_path)

    if dq_data:
        sources.append(f"{symbol} data quality report")
        context_parts.append("\n[2. DATA QUALITY REPORT]")
        context_parts.append(json.dumps(dq_data, indent=2))
    else:
        context_parts.append("\n[2. DATA QUALITY REPORT]")
        context_parts.append("Unavailable.")

    # 3. Walk-Forward Summary (Sprint 6)
    # The README shows validation is at data/validation/{SYMBOL}_summary.json
    # It seems in sprint 6 it was added. Let's find exactly where it is.
    # Note: DATA_ROOT / "validation" / f"{symbol}_summary.json"
    DATA_ROOT = get_backtest_dir(symbol).parent.parent
    val_summary_path = DATA_ROOT / "validation" / f"{symbol}_summary.json"
    val_data = _load_json(val_summary_path)

    if val_data:
        sources.append(f"{symbol} walk-forward summary")
        context_parts.append("\n[3. WALK-FORWARD VALIDATION SUMMARY]")
        context_parts.append(json.dumps(val_data, indent=2))

    val_wf_path = DATA_ROOT / "validation" / f"{symbol}_walkforward.json"
    val_wf_data = _load_json(val_wf_path)
    if val_wf_data:
        sources.append(f"{symbol} walk-forward details")
        context_parts.append("\n[4. WALK-FORWARD DETAILS]")
        context_parts.append(json.dumps(val_wf_data, indent=2))

    val_sens_path = DATA_ROOT / "validation" / f"{symbol}_sensitivity.json"
    val_sens_data = _load_json(val_sens_path)
    if val_sens_data:
        sources.append(f"{symbol} sensitivity analysis")
        context_parts.append("\n[5. SENSITIVITY ANALYSIS]")
        context_parts.append(json.dumps(val_sens_data, indent=2))

    # Compile the final strict instructions for grounding
    context_parts.append("\n--- END OF CONTEXT ---")

    return "\n".join(context_parts), sources
