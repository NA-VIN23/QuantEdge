// src/components/charts/VolumeChart.tsx
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import type { FeatureRow } from '../../types';

interface Props { data: FeatureRow[] }

const TICK_STYLE = { fill: '#555c75', fontSize: 11 };

function downsample(rows: FeatureRow[], max: number): FeatureRow[] {
  if (rows.length <= max) return rows;
  const step = Math.ceil(rows.length / max);
  const out: FeatureRow[] = [];
  for (let i = 0; i < rows.length; i += step) out.push(rows[i]);
  return out;
}

interface TooltipPayload {
  payload: FeatureRow;
}

function VolumeTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayload[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius)',
      padding: '8px 12px',
      fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-muted)' }}>{d.date}</div>
      <div style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
        Vol: {(d.volume / 1_000_000).toFixed(2)}M
      </div>
      {d.volume_ratio !== null && (
        <div style={{ color: d.volume_ratio > 1.5 ? 'var(--positive)' : 'var(--text-muted)', fontSize: 11 }}>
          Ratio: {d.volume_ratio.toFixed(2)}x
        </div>
      )}
    </div>
  );
}

export function VolumeChart({ data }: Props) {
  const sampled = downsample(data, 400);
  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={sampled} margin={{ top: 4, right: 20, left: 10, bottom: 0 }}>
        <CartesianGrid stroke="#1d2030" strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={d => d.substring(0, 4)}
          tick={TICK_STYLE}
          axisLine={false}
          tickLine={false}
          interval={Math.floor(sampled.length / 6)}
        />
        <YAxis
          tick={TICK_STYLE}
          axisLine={false}
          tickLine={false}
          width={50}
          tickFormatter={v => `${(v / 1_000_000).toFixed(0)}M`}
        />
        <Tooltip content={<VolumeTooltip />} />
        <Bar dataKey="volume" fill="#2a3050" radius={[1, 1, 0, 0]} name="Volume" />
      </BarChart>
    </ResponsiveContainer>
  );
}
