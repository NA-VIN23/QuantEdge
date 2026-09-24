// src/pages/BacktestLab/index.tsx
// Sprint 5: Symbol read from URL param /backtest/:symbol
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/api';
import { MetricGrid } from '../../components/metrics/MetricGrid';
import { EquityCurveChart } from '../../components/charts/EquityCurveChart';
import { StockSelector } from '../../components/ui/StockSelector';
import type { BacktestSummary, EquityCurveRow } from '../../types';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';

export function BacktestLab() {
  const { symbol = 'ITC' } = useParams<{ symbol: string }>();
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [equity, setEquity]   = useState<EquityCurveRow[]>([]);
  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.backtestSummary(symbol), api.equityCurve(symbol)])
      .then(([s, eq]) => { setSummary(s); setEquity(eq); })
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div className="state-container"><div className="spinner" /><div className="state-title">Loading backtest…</div></div>;
  if (error)   return <div className="state-container"><div className="state-icon">⚠</div><div className="state-title">{error}</div></div>;
  if (!summary) return null;

  const cfg = summary.backtest_config as Record<string, string | number>;

  const exitData = Object.entries(summary.exit_reason_counts).map(([reason, count]) => ({
    reason, count,
  }));

  return (
    <div className="page-content">
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div className="page-title">Backtest Lab — {symbol}</div>
          <StockSelector currentSymbol={symbol} routeTemplate="/backtest/:symbol" />
        </div>
        <div className="page-subtitle">Historical simulation results — display only, no live trading</div>
      </div>

      <div className="disclaimer">
        <strong>Important:</strong> This is a historical backtest simulation on ITC data (2005–2025).
        Results reflect the strategy's performance on past data only. They do not predict
        future returns. Strategy parameters are fixed from Sprint 2 and cannot be modified here.
      </div>

      <div className="two-col" style={{ marginBottom: 'var(--space-8)' }}>
        {/* Strategy config */}
        <div className="card">
          <div className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Strategy</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 'var(--space-4)' }}>
            Daily Trend-Momentum Breakout
          </div>
          <table className="assumption-table">
            <tbody>
              {[
                ['Signal', 'End of trading day'],
                ['Entry', 'Next trading day OPEN'],
                ['Position', 'Long only · one at a time'],
                ['Pyramiding', 'Disabled'],
                ['Shorting', 'Disabled'],
              ].map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Signal conditions */}
        <div className="card">
          <div className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Entry Conditions</div>
          <table className="assumption-table">
            <tbody>
              {[
                ['1 — Trend',     'EMA20 > EMA50'],
                ['2 — Price',     'Close > EMA20'],
                ['3 — Breakout',  'Close > 20-day high (prior day)'],
                ['4 — Volume',    'Volume ratio > 1.5×'],
              ].map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="two-col" style={{ marginBottom: 'var(--space-8)' }}>
        {/* Risk parameters */}
        <div className="card">
          <div className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Risk Parameters</div>
          <table className="assumption-table">
            <tbody>
              {[
                ['Initial Capital',   `₹${Number(cfg.initial_capital).toLocaleString('en-IN')}`],
                ['Risk per Trade',    `${(Number(cfg.risk_per_trade) * 100).toFixed(1)}% of equity`],
                ['ATR Multiplier',    `${cfg.atr_multiplier}×`],
                ['Stop Type',         'ATR-based initial stop'],
                ['Stop Price',        'Entry − (ATR mult × ATR14)'],
              ].map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{String(v)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Cost assumptions */}
        <div className="card">
          <div className="section-title" style={{ marginBottom: 'var(--space-4)' }}>Cost Assumptions</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 'var(--space-3)', fontStyle: 'italic' }}>
            Research defaults only. Not actual broker charges.
          </div>
          <table className="assumption-table">
            <tbody>
              {[
                ['Commission rate',  `${(Number(cfg.commission_rate) * 100).toFixed(3)}% per side`],
                ['Slippage rate',    `${(Number(cfg.slippage_rate) * 100).toFixed(3)}% per side`],
                ['Entry slippage',   'Effective entry = open × (1 + slippage)'],
                ['Exit slippage',    'Effective exit = price × (1 − slippage)'],
                ['Applied on',       'Both legs (entry + exit)'],
              ].map(([k, v]) => (
                <tr key={k}><td>{k}</td><td>{v}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Exit rules */}
      <div className="section">
        <div className="section-header"><div className="section-title">Exit Rules</div></div>
        <div className="card">
          <table className="assumption-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <td style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 11 }}>Priority</td>
                <td style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 11 }}>Rule</td>
                <td style={{ fontWeight: 600, color: 'var(--text-secondary)', fontSize: 11 }}>Execution</td>
              </tr>
            </thead>
            <tbody>
              <tr><td>1 — Gap-Down Stop</td><td>Open &lt; stop price</td><td>Exit at day's open → STOP_GAP</td></tr>
              <tr><td>2 — Intraday Stop</td><td>Low ≤ stop price</td><td>Exit at stop price → STOP_LOSS</td></tr>
              <tr><td>3 — Trend Exit</td><td>Close &lt; EMA20</td><td>Exit next day's open → TREND_EXIT</td></tr>
              <tr><td>4 — End of Data</td><td>Final row</td><td>Exit at final close → END_OF_DATA</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Results */}
      <div className="section">
        <div className="section-header"><div className="section-title">Performance Results</div></div>
        <MetricGrid summary={summary} />
      </div>

      {/* Equity curve */}
      <div className="section">
        <div className="section-header"><div className="section-title">Equity Curve</div></div>
        <div className="chart-wrapper">
          <EquityCurveChart data={equity} initialCapital={summary.initial_capital} />
        </div>
      </div>

      {/* Exit reason distribution */}
      <div className="section">
        <div className="section-header"><div className="section-title">Exit Reason Distribution</div></div>
        <div className="chart-wrapper">
          <div className="chart-title">How trades were closed</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={exitData} layout="vertical" margin={{ left: 60, right: 30, top: 10, bottom: 10 }}>
              <CartesianGrid stroke="#1d2030" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#555c75', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis
                type="category"
                dataKey="reason"
                tick={{ fill: '#8890aa', fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={100}
              />
              <Tooltip
                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                labelStyle={{ color: 'var(--text-secondary)' }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {exitData.map(entry => (
                  <Cell
                    key={entry.reason}
                    fill={entry.reason === 'TREND_EXIT' ? '#3b82f6' : entry.reason === 'STOP_LOSS' ? '#f87171' : '#8890aa'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
