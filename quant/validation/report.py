"""
quant/validation/report.py
---------------------------
Report writer for Sprint 6 validation results.

Writes the following output files:

Machine-readable:
  data/validation/{SYMBOL}_splits.json       ← walk-forward window metadata
  data/validation/{SYMBOL}_walkforward.json  ← per-window metrics + benchmark
  data/validation/{SYMBOL}_sensitivity.json  ← sensitivity table (11 configs)
  data/validation/{SYMBOL}_summary.json      ← headline numbers + gate results

Human-readable:
  docs/sprint-6-validation.md               ← full Markdown validation report
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from quant.validation.sensitivity import SensitivityResult
from quant.validation.walk_forward import WalkForwardSummary, WalkForwardWindow


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent

VALIDATION_DIR = PROJECT_ROOT / "data" / "validation"
DOCS_DIR = PROJECT_ROOT / "docs"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_validation_report(
    symbol: str,
    summary: WalkForwardSummary,
    sensitivity_results: list[SensitivityResult],
    baseline_metrics: Optional[dict] = None,
    bh_full: Optional[dict] = None,
    gate_status: str = "PASSED",
    gate_errors: Optional[list[str]] = None,
) -> dict[str, Path]:
    """
    Write all Sprint 6 validation output files.

    Parameters
    ----------
    symbol : str
        NSE symbol.
    summary : WalkForwardSummary
        Walk-forward results.
    sensitivity_results : list[SensitivityResult]
        Sensitivity analysis results.
    baseline_metrics : dict, optional
        Full-dataset backtest metrics.
    bh_full : dict, optional
        Full-dataset buy-and-hold result.
    gate_status : str
        "PASSED" or "FAILED".
    gate_errors : list[str], optional
        Gate error messages.

    Returns
    -------
    dict[str, Path]
        Mapping of artifact name → written file path.
    """
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    errors = gate_errors or []
    written: dict[str, Path] = {}

    # 1. Splits JSON
    splits_path = VALIDATION_DIR / f"{symbol}_splits.json"
    _write_json(splits_path, _splits_payload(summary))
    written["splits"] = splits_path

    # 2. Walk-forward JSON
    wf_path = VALIDATION_DIR / f"{symbol}_walkforward.json"
    _write_json(wf_path, _walkforward_payload(summary))
    written["walkforward"] = wf_path

    # 3. Sensitivity JSON
    sens_path = VALIDATION_DIR / f"{symbol}_sensitivity.json"
    _write_json(sens_path, _sensitivity_payload(sensitivity_results))
    written["sensitivity"] = sens_path

    # 4. Summary JSON
    summary_path = VALIDATION_DIR / f"{symbol}_summary.json"
    _write_json(
        summary_path,
        _summary_payload(
            symbol, summary, sensitivity_results,
            baseline_metrics, bh_full, gate_status, errors,
        ),
    )
    written["summary"] = summary_path

    # 5. Markdown report
    md_path = DOCS_DIR / "sprint-6-validation.md"
    md_path.write_text(
        _markdown_report(
            symbol, summary, sensitivity_results,
            baseline_metrics, bh_full, gate_status, errors,
        ),
        encoding="utf-8",
    )
    written["markdown"] = md_path

    return written


# ---------------------------------------------------------------------------
# JSON payload builders
# ---------------------------------------------------------------------------


def _splits_payload(summary: WalkForwardSummary) -> dict:
    return {
        "symbol": summary.symbol,
        "generated_at": datetime.now().isoformat(),
        "total_windows": summary.total_windows,
        "ok_windows": summary.ok_windows,
        "zero_trade_windows": summary.zero_trade_windows,
        "insufficient_data_windows": summary.insufficient_data_windows,
        "windows": [
            {
                "window_index": w.window_index,
                "dev_start": w.dev_start,
                "dev_end": w.dev_end,
                "dev_rows": w.dev_rows,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "test_rows": w.test_rows,
                "status": w.status,
            }
            for w in summary.windows
        ],
    }


def _walkforward_payload(summary: WalkForwardSummary) -> dict:
    return {
        "symbol": summary.symbol,
        "generated_at": datetime.now().isoformat(),
        "total_windows": summary.total_windows,
        "ok_windows": summary.ok_windows,
        "zero_trade_windows": summary.zero_trade_windows,
        "insufficient_data_windows": summary.insufficient_data_windows,
        "windows": [
            {
                "window_index": w.window_index,
                "dev_start": w.dev_start,
                "dev_end": w.dev_end,
                "dev_rows": w.dev_rows,
                "test_start": w.test_start,
                "test_end": w.test_end,
                "test_rows": w.test_rows,
                "status": w.status,
                "strategy": {
                    "num_trades": w.num_trades,
                    "total_return_pct": w.total_return_pct,
                    "win_rate": w.win_rate,
                    "profit_factor": w.profit_factor,
                    "max_drawdown_pct": w.max_drawdown_pct,
                    "final_equity": w.final_equity,
                },
                "buy_and_hold": {
                    "total_return_pct": w.bh_total_return_pct,
                    "final_equity": w.bh_final_equity,
                },
                "excess_return_pct": w.excess_return_pct,
            }
            for w in summary.windows
        ],
    }


def _sensitivity_payload(results: list[SensitivityResult]) -> list[dict]:
    return [
        {
            "param_name": r.param_name,
            "param_value": r.param_value,
            "is_baseline": r.is_baseline,
            "num_trades": r.num_trades,
            "total_return_pct": r.total_return_pct,
            "win_rate": r.win_rate,
            "profit_factor": r.profit_factor,
            "max_drawdown_pct": r.max_drawdown_pct,
            "final_equity": r.final_equity,
        }
        for r in results
    ]


def _summary_payload(
    symbol: str,
    summary: WalkForwardSummary,
    sensitivity_results: list[SensitivityResult],
    baseline_metrics: Optional[dict],
    bh_full: Optional[dict],
    gate_status: str,
    gate_errors: list[str],
) -> dict:
    ok_windows = [w for w in summary.windows if w.status == "OK"]
    avg_return = (
        round(sum(w.total_return_pct for w in ok_windows) / len(ok_windows), 4)
        if ok_windows else None
    )
    avg_bh_return = (
        round(sum(w.bh_total_return_pct for w in ok_windows) / len(ok_windows), 4)
        if ok_windows else None
    )
    pct_profitable = (
        round(
            sum(1 for w in ok_windows if w.total_return_pct > 0)
            / len(ok_windows) * 100,
            2,
        )
        if ok_windows else None
    )

    return {
        "symbol": symbol,
        "generated_at": datetime.now().isoformat(),
        "integrity_gates": {
            "status": gate_status,
            "errors": gate_errors,
        },
        "full_dataset_baseline": baseline_metrics,
        "full_dataset_buy_and_hold": bh_full,
        "walk_forward": {
            "total_windows": summary.total_windows,
            "ok_windows": summary.ok_windows,
            "zero_trade_windows": summary.zero_trade_windows,
            "insufficient_data_windows": summary.insufficient_data_windows,
            "avg_return_pct_ok_windows": avg_return,
            "avg_bh_return_pct_ok_windows": avg_bh_return,
            "pct_ok_windows_profitable": pct_profitable,
        },
        "sensitivity_configs_tested": len(sensitivity_results),
    }


# ---------------------------------------------------------------------------
# Markdown report builder
# ---------------------------------------------------------------------------


def _markdown_report(
    symbol: str,
    summary: WalkForwardSummary,
    sensitivity_results: list[SensitivityResult],
    baseline_metrics: Optional[dict],
    bh_full: Optional[dict],
    gate_status: str,
    gate_errors: list[str],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    def fmt(v, spec=".2f") -> str:
        if v is None:
            return "N/A"
        if isinstance(v, float):
            return f"{v:{spec}}"
        return str(v)

    # --- Header ---
    add(f"# QuantEdge Sprint 6 — Validation Report [{symbol}]")
    add()
    add(f"**Generated:** {now}")
    add()
    add("> [!CAUTION]")
    add("> This is a **historical simulation only**. Past validation results do NOT")
    add("> guarantee future performance. This report does NOT constitute investment advice.")
    add()
    add("---")
    add()

    # --- 1. Integrity Gates ---
    add("## 1. Integrity Gates")
    add()
    gate_icon = "✅ PASSED" if gate_status == "PASSED" else "❌ FAILED"
    add(f"**Status:** {gate_icon}")
    add()
    if gate_errors:
        add("**Errors:**")
        add()
        for err in gate_errors:
            add(f"- {err}")
        add()
    add("---")
    add()

    # --- 2. Full-Dataset Baseline ---
    add("## 2. Full-Dataset Baseline (ITC Regression)")
    add()
    if baseline_metrics:
        bh_return = bh_full["total_return_pct"] if bh_full else None
        bh_equity = bh_full["final_equity"] if bh_full else None
        add("| Metric | Strategy | Buy-and-Hold |")
        add("|--------|----------|--------------|")
        add(f"| Initial capital | ₹{baseline_metrics['initial_capital']:,.2f} | ₹{baseline_metrics['initial_capital']:,.2f} |")
        add(f"| Final equity | ₹{baseline_metrics['final_equity']:,.2f} | ₹{bh_equity:,.2f} |" if bh_equity is not None else f"| Final equity | ₹{baseline_metrics['final_equity']:,.2f} | N/A |")
        add(f"| Total return | {fmt(baseline_metrics['total_return_pct'])}% | {fmt(bh_return)}% |")
        add(f"| Trades executed | {baseline_metrics['num_trades']} | 1 |")
        wr = baseline_metrics.get("win_rate")
        add(f"| Win rate | {fmt(wr * 100 if wr is not None else None)}% | N/A |")
        add(f"| Profit factor | {fmt(baseline_metrics.get('profit_factor'))} | N/A |")
        add(f"| Max drawdown | {fmt(baseline_metrics.get('max_drawdown_pct'))}% | N/A |")
    else:
        add("*Baseline metrics not available.*")
    add()
    add("---")
    add()

    # --- 3. Walk-Forward Summary ---
    add("## 3. Walk-Forward Validation Summary")
    add()
    add(f"- **Total windows generated:** {summary.total_windows}")
    add(f"- **Windows with trades (OK):** {summary.ok_windows}")
    add(f"- **Windows with zero trades:** {summary.zero_trade_windows}")
    add(f"- **Windows with insufficient data:** {summary.insufficient_data_windows}")
    add()
    ok_windows = [w for w in summary.windows if w.status == "OK"]
    if ok_windows:
        avg_ret = sum(w.total_return_pct for w in ok_windows) / len(ok_windows)
        avg_bh = sum(w.bh_total_return_pct for w in ok_windows) / len(ok_windows)
        pct_pos = sum(1 for w in ok_windows if w.total_return_pct > 0) / len(ok_windows) * 100
        add(f"- **Average strategy return per test window (OK windows):** {avg_ret:.2f}%")
        add(f"- **Average buy-and-hold return per test window:** {avg_bh:.2f}%")
        add(f"- **% of OK windows where strategy was profitable:** {pct_pos:.1f}%")
    add()
    add("---")
    add()

    # --- 4. Walk-Forward Window Table ---
    add("## 4. Walk-Forward Window Results")
    add()
    add("| Window | Test Start | Test End | Rows | Trades | Return % | B&H % | Excess % | Status |")
    add("|--------|------------|----------|------|--------|----------|-------|----------|--------|")
    for w in summary.windows:
        add(
            f"| {w.window_index} | {w.test_start} | {w.test_end} | "
            f"{w.test_rows} | {w.num_trades} | {fmt(w.total_return_pct)} | "
            f"{fmt(w.bh_total_return_pct)} | {fmt(w.excess_return_pct)} | "
            f"{w.status} |"
        )
    add()
    add("---")
    add()

    # --- 5. Sensitivity Analysis ---
    add("## 5. Sensitivity Analysis")
    add()
    add("Small parameter variations around the baseline. No optimization. Results are presented as-is.")
    add()
    add("| Parameter | Value | Baseline? | Trades | Return % | Win Rate % | Profit Factor | Max DD % |")
    add("|-----------|-------|-----------|--------|----------|------------|---------------|----------|")
    for r in sensitivity_results:
        bl = "✓" if r.is_baseline else ""
        wr_pct = r.win_rate * 100 if r.win_rate is not None else None
        add(
            f"| {r.param_name} | {r.param_value} | {bl} | {r.num_trades} | "
            f"{fmt(r.total_return_pct)} | {fmt(wr_pct)} | "
            f"{fmt(r.profit_factor)} | {fmt(r.max_drawdown_pct)} |"
        )
    add()
    add("---")
    add()

    # --- 6. Methodology Notes ---
    add("## 6. Methodology Notes")
    add()
    notes = [
        "**Strategy:** Daily Trend-Momentum Breakout (rule-based, unchanged from Sprint 2).",
        "**Data split:** Development 2005–2017 / Validation 2018–2021 / Out-of-Sample 2022–2025.",
        "**Walk-forward:** Expanding development window, 6-month unseen test steps.",
        "**Feature handling:** Pre-computed `ITC_features.csv` (Approach A). "
        "All indicators are causal — truncation-invariance verified by automated tests.",
        "**Benchmark:** Buy-and-hold: buy at first-row open, sell at last-row close, same costs.",
        "**Parameters:** Fixed throughout. No parameter fitting or optimization.",
        "**Transaction costs:** Commission 0.05% + slippage 0.05% per side (both entry and exit).",
        "**Integrity gates:** 5 programmatic checks must all pass before results are published.",
    ]
    for note in notes:
        add(f"- {note}")
    add()
    add("---")
    add()
    add("*End of Sprint 6 Validation Report.*")
    add()

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
