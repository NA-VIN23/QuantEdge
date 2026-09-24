// src/pages/Overview/index.tsx
// Sprint 5: uses explicit 'ITC' symbol until stock-selector navigation lands on this page.
import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { MetricGrid } from '../../components/metrics/MetricGrid';
import { EquityCurveChart } from '../../components/charts/EquityCurveChart';
import { StockSelector } from '../../components/ui/StockSelector';
import type { OverviewResponse, EquityCurveRow } from '../../types';

const DEFAULT_SYMBOL = 'ITC';

export function Overview() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [equity, setEquity] = useState<EquityCurveRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.overview(DEFAULT_SYMBOL), api.equityCurve(DEFAULT_SYMBOL)])
      .then(([ov, eq]) => {
        setOverview(ov);
        setEquity(eq);
      })
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="state-container">
      <div className="spinner" />
      <div className="state-title">Loading research data…</div>
    </div>
  );

  if (error) return (
    <div className="state-container">
      <div className="state-icon">⚠</div>
      <div className="state-title">Could not load data</div>
      <div className="state-desc">{error}</div>
      <div className="state-desc" style={{ fontSize: 11 }}>
        Make sure the QuantEdge API is running: <code>uvicorn quant.api.main:app --reload --port 8000</code>
      </div>
    </div>
  );

  if (!overview) return null;
  const { dataset, strategy_name, num_signals, backtest } = overview;

  return (
    <div className="page-content">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div className="page-title">Research Overview</div>
          <StockSelector currentSymbol={DEFAULT_SYMBOL} routeTemplate="/stocks/:symbol" />
        </div>
        <div className="page-subtitle">
          Historical research pipeline — {DEFAULT_SYMBOL}
        </div>
      </div>

      <div className="disclaimer">
        <strong>Historical simulation only.</strong> This application displays outputs of a
        historical backtest. It does not execute real trades, connect to any broker, or
        predict future returns. Past simulation results do not guarantee future performance.
      </div>

      {/* Dataset */}
      <div className="section">
        <div className="section-header">
          <div className="section-title">Dataset</div>
        </div>
        <div className="card">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--space-5)' }}>
            {[
              ['Symbol',      dataset.symbol],
              ['Rows',        dataset.row_count.toLocaleString('en-IN')],
              ['Date Range',  `${dataset.date_min} → ${dataset.date_max}`],
              ['Columns',     String(dataset.columns.length)],
              ['Strategy',    strategy_name],
              ['LONG Signals', String(num_signals)],
            ].map(([k, v]) => (
              <div key={k}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 4 }}>{k}</div>
                <div style={{ fontSize: 13, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Backtest metrics */}
      <div className="section">
        <div className="section-header">
          <div className="section-title">Backtest Results — {strategy_name}</div>
        </div>
        <MetricGrid summary={backtest} />
      </div>

      {/* Equity curve */}
      <div className="section">
        <div className="section-header">
          <div className="section-title">Equity Curve</div>
        </div>
        {equity.length > 0 ? (
          <div className="chart-wrapper">
            <div className="chart-title">Portfolio equity over time · {DEFAULT_SYMBOL} · {overview.dataset.date_min.slice(0, 4)}–{overview.dataset.date_max.slice(0, 4)}</div>
            <EquityCurveChart data={equity} initialCapital={backtest.initial_capital} />
          </div>
        ) : (
          <div className="state-container">
            <div className="state-title">No equity data available</div>
          </div>
        )}
      </div>
    </div>
  );
}
