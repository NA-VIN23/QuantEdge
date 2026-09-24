// src/services/api.ts
// Typed fetch wrappers for each QuantEdge API endpoint.
// All functions are read-only GET requests.
// Sprint 5: All stock/backtest calls are parameterized by symbol.

import type {
  StockListItem,
  OverviewResponse,
  OHLCVRow,
  FeatureRow,
  BacktestSummary,
  TradeRow,
  EquityCurveRow,
  DataQualityReport,
} from '../types';

const BASE = '/api';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  /** Return the list of symbols with processed data on disk. */
  stocks(): Promise<StockListItem[]> {
    return get('/stocks');
  },

  /** Overview for a symbol (defaults to ITC if not supplied). */
  overview(symbol?: string): Promise<OverviewResponse> {
    const qs = symbol ? `?symbol=${encodeURIComponent(symbol)}` : '';
    return get(`/overview${qs}`);
  },

  stockOHLCV(symbol: string, from?: string, to?: string): Promise<OHLCVRow[]> {
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    const qs = params.size ? `?${params}` : '';
    return get(`/stocks/${encodeURIComponent(symbol)}${qs}`);
  },

  stockFeatures(symbol: string, from?: string, to?: string): Promise<FeatureRow[]> {
    const params = new URLSearchParams();
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    const qs = params.size ? `?${params}` : '';
    return get(`/stocks/${encodeURIComponent(symbol)}/features${qs}`);
  },

  backtestSummary(symbol: string): Promise<BacktestSummary> {
    return get(`/backtests/${encodeURIComponent(symbol)}`);
  },

  trades(symbol: string): Promise<TradeRow[]> {
    return get(`/backtests/${encodeURIComponent(symbol)}/trades`);
  },

  equityCurve(symbol: string): Promise<EquityCurveRow[]> {
    return get(`/backtests/${encodeURIComponent(symbol)}/equity`);
  },

  dataQuality(symbol: string): Promise<DataQualityReport> {
    return get(`/data-quality/${encodeURIComponent(symbol)}`);
  },
};
