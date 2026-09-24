// src/pages/DataCenter/index.tsx
// Sprint 5: Symbol read from URL param /data/:symbol
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/api';
import { StockSelector } from '../../components/ui/StockSelector';
import type { DataQualityReport } from '../../types';

interface MetricRowProps { label: string; value: string | number; ok?: boolean }
function MetricRow({ label, value, ok }: MetricRowProps) {
  const color = ok === undefined ? 'var(--text-primary)'
              : ok ? 'var(--positive)' : 'var(--negative)';
  return (
    <div className="feature-chip">
      <span className="feature-name">{label}</span>
      <span className="feature-val" style={{ color }}>{String(value)}</span>
    </div>
  );
}

const PIPELINE_STEPS = [
  {
    name: 'Raw CSV',
    desc: 'data/raw/ITC Stock Price History.csv — source file, never modified',
  },
  {
    name: 'Ingestion',
    desc: 'quant.data.ingestion — load raw strings, verify SHA-256, detect columns',
  },
  {
    name: 'Cleaning',
    desc: 'quant.data.cleaning — parse dates (MM/DD/YYYY → YYYY-MM-DD), parse numerics, remove commas',
  },
  {
    name: 'Validation',
    desc: 'quant.data.validation — OHLC consistency, volume, date monotonicity, change % check',
  },
  {
    name: 'Canonical Dataset',
    desc: 'data/processed/itc_daily_clean.csv — reproducible, deterministic output',
  },
  {
    name: 'Feature Dataset',
    desc: 'quant.features — EMA20/50, SMA20/50, ATR14, volume ratio, momentum, signals → itc_features.csv',
  },
  {
    name: 'Backtest',
    desc: 'quant.backtest — Sprint 3 simulation engine → trades.csv, equity_curve.csv, summary.json',
  },
];

export function DataCenter() {
  const { symbol = 'ITC' } = useParams<{ symbol: string }>();
  const [report, setReport] = useState<DataQualityReport | null>(null);
  const [error, setError]   = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.dataQuality(symbol)
      .then(setReport)
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div className="state-container"><div className="spinner" /><div className="state-title">Loading quality report…</div></div>;
  if (error)   return <div className="state-container"><div className="state-icon">⚠</div><div className="state-title">{error}</div></div>;
  if (!report) return null;

  const isPass = report.status === 'PASS';

  return (
    <div className="page-content">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div className="page-title">Data Center — {symbol}</div>
          <StockSelector currentSymbol={symbol} routeTemplate="/data/:symbol" />
        </div>
        <div className="page-subtitle">Data provenance, quality metrics, and pipeline overview</div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.6px' }}>Validation Status</div>
          <div className={isPass ? 'status-pass' : 'status-fail'} id="data-quality-status">
            <span>{isPass ? '✓' : '✗'}</span>
            {report.status}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.6px' }}>Generated</div>
          <div style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
            {report.generated_at.split('T')[0]}
          </div>
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 'var(--space-8)' }}>
        {/* Dataset provenance */}
        <div className="card">
          <div className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Dataset Provenance</div>
          <MetricRow label="Symbol"         value={report.symbol} />
          <MetricRow label="Source file"    value={report.source_filename} />
          <MetricRow label="Original rows"  value={report.original_row_count.toLocaleString('en-IN')} />
          <MetricRow label="Final rows"     value={report.final_row_count.toLocaleString('en-IN')} />
          <MetricRow label="Removed rows"   value={report.removed_row_count} ok={report.removed_row_count === 0} />
          <MetricRow label="Date min"       value={report.date_min} />
          <MetricRow label="Date max"       value={report.date_max} />
        </div>

        {/* Quality checks */}
        <div className="card">
          <div className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Quality Checks</div>
          <MetricRow label="Missing dates"         value={report.missing_counts.date ?? 0} ok={(report.missing_counts.date ?? 0) === 0} />
          <MetricRow label="Missing open"          value={report.missing_counts.open ?? 0} ok={(report.missing_counts.open ?? 0) === 0} />
          <MetricRow label="Missing high"          value={report.missing_counts.high ?? 0} ok={(report.missing_counts.high ?? 0) === 0} />
          <MetricRow label="Missing low"           value={report.missing_counts.low  ?? 0} ok={(report.missing_counts.low  ?? 0) === 0} />
          <MetricRow label="Missing close"         value={report.missing_counts.close ?? 0} ok={(report.missing_counts.close ?? 0) === 0} />
          <MetricRow label="Missing volume"        value={report.missing_counts.volume ?? 0} ok={(report.missing_counts.volume ?? 0) === 0} />
          <MetricRow label="Exact duplicates"      value={report.duplicate_exact_count} ok={report.duplicate_exact_count === 0} />
          <MetricRow label="Duplicate dates"       value={report.duplicate_date_count} ok={report.duplicate_date_count === 0} />
          <MetricRow label="OHLC violations"       value={report.invalid_ohlc_count} ok={report.invalid_ohlc_count === 0} />
          <MetricRow label="Invalid volumes"       value={report.invalid_volume_count} ok={report.invalid_volume_count === 0} />
          <MetricRow label="Zero volume"           value={report.zero_volume_count} ok={report.zero_volume_count === 0} />
          <MetricRow label="Non-monotonic dates"   value={report.non_monotonic_date_count} ok={report.non_monotonic_date_count === 0} />
          <MetricRow label="Change % mismatches"   value={report.change_pct_mismatch_count} ok={report.change_pct_mismatch_count === 0} />
          <MetricRow label="Cleaning issues"       value={report.cleaning_issue_count} ok={report.cleaning_issue_count === 0} />
        </div>
      </div>

      {/* Pipeline diagram */}
      <div className="section">
        <div className="section-header">
          <div className="section-title">Data Pipeline</div>
        </div>
        <div className="card">
          <div className="pipeline" id="data-pipeline">
            {PIPELINE_STEPS.map((step, i) => (
              <div className="pipeline-step" key={step.name}>
                <div className="pipeline-connector">
                  <div className={`pipeline-node ${i === PIPELINE_STEPS.length - 1 ? 'active' : ''}`}>
                    {i + 1}
                  </div>
                  {i < PIPELINE_STEPS.length - 1 && <div className="pipeline-line" />}
                </div>
                <div className="pipeline-content">
                  <div className="pipeline-step-name">{step.name}</div>
                  <div className="pipeline-step-desc">{step.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
