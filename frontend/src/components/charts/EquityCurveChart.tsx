// src/components/charts/EquityCurveChart.tsx
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts';
import type { EquityCurveRow } from '../../types';

interface Props {
  data: EquityCurveRow[];
  initialCapital: number;
}

const TICK_STYLE = { fill: '#555c75', fontSize: 11 };

function formatDate(d: string): string {
  // Show year only for axis labels
  return d.substring(0, 4);
}

function formatCurrency(v: number): string {
  return `₹${(v / 1000).toFixed(0)}k`;
}

// Downsample to ~500 points for perf while keeping start/end
function downsample(rows: EquityCurveRow[], max: number): EquityCurveRow[] {
  if (rows.length <= max) return rows;
  const step = Math.ceil(rows.length / max);
  const out: EquityCurveRow[] = [];
  for (let i = 0; i < rows.length; i += step) out.push(rows[i]);
  if (out[out.length - 1] !== rows[rows.length - 1]) out.push(rows[rows.length - 1]);
  return out;
}

interface TooltipPayload {
  payload: EquityCurveRow;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '10px 14px',
      fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 6 }}>{d.date}</div>
      <div style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
        Equity: ₹{d.equity.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </div>
      {d.position_quantity > 0 && (
        <div style={{ color: 'var(--text-secondary)', fontSize: 11, marginTop: 4 }}>
          Position: {d.position_quantity} shares
        </div>
      )}
    </div>
  );
}

export function EquityCurveChart({ data, initialCapital }: Props) {
  const sampled = downsample(data, 600);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={sampled} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}    />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#1d2030" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          tick={TICK_STYLE}
          axisLine={false}
          tickLine={false}
          interval={Math.floor(sampled.length / 8)}
        />
        <YAxis
          tickFormatter={formatCurrency}
          tick={TICK_STYLE}
          axisLine={false}
          tickLine={false}
          width={52}
          domain={['auto', 'auto']}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine
          y={initialCapital}
          stroke="#555c75"
          strokeDasharray="4 4"
          label={{ value: 'Initial', fill: '#555c75', fontSize: 10, position: 'insideTopRight' }}
        />
        <Area
          type="monotone"
          dataKey="equity"
          stroke="#3b82f6"
          strokeWidth={1.5}
          fill="url(#equityGrad)"
          dot={false}
          name="Equity"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
