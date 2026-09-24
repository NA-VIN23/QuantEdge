"""
quant/api/routes/data_quality.py
---------------------------------
Sprint 5: Generalized data quality endpoint.

GET /api/data-quality/{symbol}
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from quant.api.schemas import DataQualityReport
from quant.data.registry import (
    get_quality_report_paths,
    VALID_SYMBOLS,
)

router = APIRouter(tags=["data-quality"])


@router.get("/data-quality/{symbol}", response_model=DataQualityReport)
def get_data_quality(symbol: str) -> DataQualityReport:
    """Return the data quality validation report for a symbol."""
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' is not recognised. Known symbols: {sorted(VALID_SYMBOLS)}.",
        )

    json_path, _ = get_quality_report_paths(symbol)
    if not json_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Data quality report for '{symbol}' not found. "
                f"Run 'python -m quant.data.pipeline --symbol {symbol}' first."
            ),
        )
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    return DataQualityReport(**data)
