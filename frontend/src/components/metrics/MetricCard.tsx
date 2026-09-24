// src/components/metrics/MetricCard.tsx
interface MetricCardProps {
  label: string;
  value: string;
  sub?: string;
  sentiment?: 'positive' | 'negative' | 'neutral' | 'muted';
  id?: string;
}

export function MetricCard({ label, value, sub, sentiment, id }: MetricCardProps) {
  const cls = sentiment ? ` ${sentiment}` : '';
  return (
    <div className="metric-card" id={id}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value${cls}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}
