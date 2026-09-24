// src/components/charts/PriceChart.tsx
// Professional OHLC line chart with EMA/SMA overlays and signal markers.
import {
  ComposedChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, ReferenceLine, Scatter,
} from 'recharts';
import type { FeatureRow } from '../../types';

interface Props {
  data: FeatureRow[];
}

const TICK_STYLE = { fill: '#555c75', fontSize: 11 };

function downsample(rows: FeatureRow[], max: number): FeatureRow[] {
  if (rows.length <= max) return rows;
  const step = Math.ceil(rows.length / max);
  const out: FeatureRow[] = [];
  for (let i = 0; i < rows.length; i += step) out.push(rows[i]);
  if (out[out.length - 1] !== rows[rows.length - 1]) out.push(rows[rows.length - 1]);
  return out;
}

interface TooltipPayload {
  payload: FeatureRow;
  color: string;
  name: string;
  value: number;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null;
  const d: FeatureRow = payload[0].payload;
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '10px 14px',
      fontSize: 12,
      minWidth: 200,
    }}>
      <div style={{ color: 'var(--text-muted)', marginBottom: 8 }}>{d.date}</div>
      {[
        ['Open',  d.open],
        ['High',  d.high],
        ['Low',   d.low],
        ['Close', d.close],
      ].map(([k, v]) => (
        <div key={String(k)} style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
          <span style={{ color: 'var(--text-muted)' }}>{k}</span>
          <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
            ₹{(v as number).toFixed(2)}
          </span>
        </div>
      ))}
      {d.signal === 'LONG' && (
        <div style={{ marginTop: 8, color: '#34d399', fontWeight: 600, fontSize: 11 }}>
          ▲ LONG SIGNAL
        </div>
      )}
    </div>
  );
}

export function PriceChart({ data }: Props) {
  const sampled = downsample(data, 500);
  const signals = sampled.filter(r => r.signal === 'LONG');

  return (
    <ResponsiveContainer width="100%" height={360}>
      <ComposedChart data={sampled} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
        <CartesianGrid stroke="#1d2030" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={d => d.substring(0, 4)}
          tick={TICK_STYLE}
          axisLine={false}
          tickLine={false}
          interval={Math.floor(sampled.length / 8)}
        />
        <YAxis
          tick={TICK_STYLE}
          axisLine={false}
          tickLine={false}
          width={55}
          tickFormatter={v => `₹${v.toFixed(0)}`}
          domain={['auto', 'auto']}
        />
        <Tooltip content={<CustomTooltip />} />
        <Legend
          iconType="line"
          iconSize={10}
          wrapperStyle={{ fontSize: 11, color: 'var(--text-muted)', paddingTop: 8 }}
        />

        <Line type="monotone" dataKey="close"  stroke="#e2e5f0" strokeWidth={1}   dot={false} name="Close"  />
        <Line type="monotone" dataKey="ema20"  stroke="#3b82f6" strokeWidth={1.2} dot={false} name="EMA20"  strokeDasharray="0" />
        <Line type="monotone" dataKey="ema50"  stroke="#8b5cf6" strokeWidth={1.2} dot={false} name="EMA50"  />
        <Line type="monotone" dataKey="sma20"  stroke="#f59e0b" strokeWidth={1}   dot={false} name="SMA20"  strokeDasharray="3 2" />
        <Line type="monotone" dataKey="sma50"  stroke="#ec4899" strokeWidth={1}   dot={false} name="SMA50"  strokeDasharray="3 2" />

        {/* Signal markers as reference lines */}
        {signals.slice(0, 100).map(s => (
          <ReferenceLine
            key={s.date}
            x={s.date}
            stroke="rgba(52,211,153,0.35)"
            strokeWidth={1}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
