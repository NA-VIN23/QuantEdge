// src/pages/StockAnalysis/index.tsx
// Sprint 5: Symbol read from URL param /stocks/:symbol
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/api';
import { PriceChart } from '../../components/charts/PriceChart';
import { VolumeChart } from '../../components/charts/VolumeChart';
import { StockSelector } from '../../components/ui/StockSelector';
import type { FeatureRow } from '../../types';

function fmt(v: number | null, dec = 2): string {
  if (v === null) return '—';
  return v.toFixed(dec);
}

function FeaturePanel({ row }: { row: FeatureRow }) {
  const features: [string, string][] = [
    ['Close',         `₹${fmt(row.close)}`],
    ['Open',          `₹${fmt(row.open)}`],
    ['High',          `₹${fmt(row.high)}`],
    ['Low',           `₹${fmt(row.low)}`],
    ['EMA20',         row.ema20 !== null ? `₹${fmt(row.ema20)}` : '—'],
    ['EMA50',         row.ema50 !== null ? `₹${fmt(row.ema50)}` : '—'],
    ['SMA20',         row.sma20 !== null ? `₹${fmt(row.sma20)}` : '—'],
    ['SMA50',         row.sma50 !== null ? `₹${fmt(row.sma50)}` : '—'],
    ['ATR14',         row.atr14 !== null ? fmt(row.atr14) : '—'],
    ['Avg Vol (20d)', row.avg_volume_20 !== null ? `${(row.avg_volume_20 / 1e6).toFixed(2)}M` : '—'],
    ['Volume Ratio',  row.volume_ratio !== null ? `${fmt(row.volume_ratio)}×` : '—'],
    ['Momentum 5',    fmt(row.momentum_5)],
    ['Momentum 20',   fmt(row.momentum_20)],
    ['Signal',        row.signal],
  ];

  return (
    <div className="card" style={{ minWidth: 240 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 'var(--space-3)' }}>
        {row.date}
      </div>
      {row.signal === 'LONG' && (
        <div style={{ background: 'var(--positive-dim)', border: '1px solid rgba(52,211,153,0.25)', borderRadius: 'var(--radius)', padding: '4px 10px', fontSize: 11, fontWeight: 700, color: 'var(--positive)', marginBottom: 'var(--space-3)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          ▲ Long Signal
        </div>
      )}
      {features.map(([k, v]) => (
        <div className="feature-chip" key={k}>
          <span className="feature-name">{k}</span>
          <span className="feature-val" style={{ color: k === 'Signal' && v === 'LONG' ? 'var(--positive)' : undefined }}>{v}</span>
        </div>
      ))}
    </div>
  );
}

export function StockAnalysis() {
  const { symbol = 'ITC' } = useParams<{ symbol: string }>();
  const [data, setData]         = useState<FeatureRow[]>([]);
  const [selected, setSelected] = useState<FeatureRow | null>(null);
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(true);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate]     = useState('');

  function loadData(from?: string, to?: string) {
    setLoading(true);
    api.stockFeatures(symbol, from || undefined, to || undefined)
      .then(rows => {
        setData(rows);
        setSelected(rows[rows.length - 1] ?? null);
      })
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }

  useEffect(() => { loadData(); }, [symbol]);

  const signals = data.filter(r => r.signal === 'LONG').length;
  const first = data[0];
  const last  = data[data.length - 1];

  if (loading) return (
    <div className="state-container">
      <div className="spinner" />
      <div className="state-title">Loading 5,000 rows…</div>
    </div>
  );

  if (error) return (
    <div className="state-container">
      <div className="state-icon">⚠</div>
      <div className="state-title">Could not load stock data</div>
      <div className="state-desc">{error}</div>
    </div>
  );

  return (
    <div className="page-content">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div className="page-title">{symbol} — Historical Research Dataset</div>
          <StockSelector currentSymbol={symbol} routeTemplate="/stocks/:symbol" />
        </div>
        <div className="page-subtitle">
          {first?.date} → {last?.date} · {data.length.toLocaleString('en-IN')} rows · {signals} LONG signals
        </div>
      </div>

      {/* Date range filter */}
      <div className="section">
        <div className="card" style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>From</div>
            <input
              type="date"
              className="table-search"
              style={{ width: 160 }}
              value={fromDate}
              onChange={e => setFromDate(e.target.value)}
            />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>To</div>
            <input
              type="date"
              className="table-search"
              style={{ width: 160 }}
              value={toDate}
              onChange={e => setToDate(e.target.value)}
            />
          </div>
          <button
            className="pagination-btn"
            style={{ padding: '6px 16px' }}
            onClick={() => loadData(fromDate || undefined, toDate || undefined)}
          >
            Apply
          </button>
          <button
            className="pagination-btn"
            onClick={() => { setFromDate(''); setToDate(''); loadData(); }}
          >
            Reset
          </button>
        </div>
      </div>

      {/* Charts + feature panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 'var(--space-5)', alignItems: 'start' }}>
        <div>
          <div className="chart-wrapper" style={{ marginBottom: 'var(--space-3)' }}>
            <div className="chart-title">
              Close Price · EMA20 · EMA50 · SMA20 · SMA50 · LONG signal markers (green lines)
            </div>
            <PriceChart data={data} />
          </div>
          <div className="chart-wrapper">
            <div className="chart-title">Volume</div>
            <VolumeChart data={data} />
          </div>
        </div>

        <div>
          {selected ? (
            <FeaturePanel row={selected} />
          ) : (
            <div className="card">
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Select a date to inspect features.</div>
            </div>
          )}

          <div className="card" style={{ marginTop: 'var(--space-3)' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 'var(--space-3)' }}>
              Chart Legend
            </div>
            {[
              ['#e2e5f0', 'Close Price'],
              ['#3b82f6', 'EMA20'],
              ['#8b5cf6', 'EMA50'],
              ['#f59e0b', 'SMA20 (dashed)'],
              ['#ec4899', 'SMA50 (dashed)'],
              ['rgba(52,211,153,0.5)', 'LONG Signal'],
            ].map(([color, label]) => (
              <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, fontSize: 12 }}>
                <div style={{ width: 20, height: 2, background: color, flexShrink: 0, borderRadius: 1 }} />
                <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
