"""
quant/api/main.py
-----------------
FastAPI application for QuantEdge Sprint 4.

READ-ONLY research API. All endpoints serve pre-computed data from the
Sprint 1/2/3 pipeline outputs. No user input touches the filesystem.

Start with:
    uvicorn quant.api.main:app --reload --port 8000

CORS is restricted to localhost:5173 (Vite dev server).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quant.api.routes import overview, stocks, backtests, data_quality

app = FastAPI(
    title="QuantEdge Research API",
    description=(
        "Read-only API serving Sprint 1-5 research outputs. "
        "This API does NOT execute trades, place orders, or connect to any broker."
    ),
    version="0.5.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Allow Vite dev server and local production builds
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api")
app.include_router(stocks.router,   prefix="/api")
app.include_router(backtests.router, prefix="/api")
app.include_router(data_quality.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    """Liveness check."""
    return {"status": "ok", "service": "QuantEdge Research API", "sprint": 5}
