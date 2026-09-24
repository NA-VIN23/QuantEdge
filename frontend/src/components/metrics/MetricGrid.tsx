// src/components/metrics/MetricGrid.tsx
import { MetricCard } from './MetricCard';
import type { BacktestSummary } from '../../types';

interface MetricGridProps {
  summary: BacktestSummary;
}

function fmt(v: number, decimals = 2): string {
  return v.toFixed(decimals);
}

function fmtCurrency(v: number): string {
  return `₹${Math.abs(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function pnlSentiment(v: number): 'positive' | 'negative' {
  return v >= 0 ? 'positive' : 'negative';
}

export function MetricGrid({ summary }: MetricGridProps) {
  const pnl = summary.total_net_pnl;
  const ret = summary.total_return_pct;
  const dd  = summary.max_drawdown_pct;

  return (
    <div className="metric-grid">
      <MetricCard
        id="metric-initial-capital"
        label="Initial Capital"
        value={`₹${summary.initial_capital.toLocaleString('en-IN')}`}
      />
      <MetricCard
        id="metric-final-equity"
        label="Final Equity"
        value={`₹${summary.final_equity.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
        sentiment={pnlSentiment(pnl)}
      />
      <MetricCard
        id="metric-net-pnl"
        label="Net P&L"
        value={`${pnl >= 0 ? '+' : '−'}${fmtCurrency(pnl)}`}
        sentiment={pnlSentiment(pnl)}
      />
      <MetricCard
        id="metric-total-return"
        label="Total Return"
        value={`${ret >= 0 ? '+' : ''}${fmt(ret)}%`}
        sentiment={pnlSentiment(ret)}
      />
      <MetricCard
        id="metric-win-rate"
        label="Win Rate"
        value={summary.win_rate !== null ? `${fmt(summary.win_rate * 100, 1)}%` : 'N/A'}
        sub={`${summary.num_wins}W / ${summary.num_losses}L`}
      />
      <MetricCard
        id="metric-profit-factor"
        label="Profit Factor"
        value={summary.profit_factor !== null ? fmt(summary.profit_factor, 3) : 'N/A'}
        sentiment={summary.profit_factor !== null ? (summary.profit_factor >= 1 ? 'positive' : 'negative') : undefined}
      />
      <MetricCard
        id="metric-max-drawdown"
        label="Max Drawdown"
        value={`${fmt(dd)}%`}
        sentiment="negative"
      />
      <MetricCard
        id="metric-trades"
        label="Trades Executed"
        value={String(summary.num_trades)}
        sub={`of ${summary.num_signals_total} signals`}
      />
      <MetricCard
        id="metric-avg-hold"
        label="Avg Holding"
        value={summary.avg_holding_days !== null ? `${fmt(summary.avg_holding_days, 1)}d` : 'N/A'}
      />
      <MetricCard
        id="metric-exposure"
        label="Exposure"
        value={`${fmt(summary.exposure_pct)}%`}
        sub="of trading days"
      />
    </div>
  );
}
