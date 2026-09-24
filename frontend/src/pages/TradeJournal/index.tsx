// src/pages/TradeJournal/index.tsx
// Sprint 5: Symbol read from URL param /trades/:symbol
import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../../services/api';
import { StockSelector } from '../../components/ui/StockSelector';
import type { TradeRow } from '../../types';

const PAGE_SIZE = 25;

type SortKey = keyof TradeRow;
type SortDir = 'asc' | 'desc';

function exitBadge(reason: string) {
  const cls = reason === 'TREND_EXIT' ? 'badge-trend'
            : reason === 'STOP_LOSS'  ? 'badge-stop'
            : reason === 'STOP_GAP'   ? 'badge-gap'
            : 'badge-eod';
  return <span className={`badge ${cls}`}>{reason.replace('_', ' ')}</span>;
}

function pnlClass(v: number) {
  return v > 0 ? 'td-positive' : v < 0 ? 'td-negative' : 'td-neutral';
}

function fmt(v: number, dec = 2): string { return v.toFixed(dec); }
function fmtCurrency(v: number): string {
  const sign = v >= 0 ? '+' : '−';
  return `${sign}₹${Math.abs(v).toFixed(2)}`;
}

interface DetailPanelProps {
  trade: TradeRow;
  onClose: () => void;
}

function DetailPanel({ trade: t, onClose }: DetailPanelProps) {
  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div className="detail-title">Trade #{t.trade_id} — {t.symbol}</div>
        <button className="detail-close" onClick={onClose}>✕ Close</button>
      </div>
      <div className="detail-body">
        <div style={{ marginBottom: 'var(--space-4)' }}>
          {exitBadge(t.exit_reason)}
          <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text-muted)' }}>
            {t.holding_days} days
          </span>
        </div>
        {[
          ['Signal Date',         t.signal_date],
          ['Entry Date',          t.entry_date],
          ['Entry Ref Price',     `₹${fmt(t.entry_reference_price)}`],
          ['Entry Price (eff.)',  `₹${fmt(t.entry_price)}`],
          ['Initial Stop',        `₹${fmt(t.initial_stop)}`],
          ['ATR at Signal',       fmt(t.atr_at_signal, 4)],
          ['Quantity',            t.quantity.toLocaleString('en-IN')],
          ['Risk Budget',         `₹${fmt(t.risk_budget, 2)}`],
          ['Exit Date',           t.exit_date],
          ['Exit Ref Price',      `₹${fmt(t.exit_reference_price)}`],
          ['Exit Price (eff.)',   `₹${fmt(t.exit_price)}`],
          ['Exit Reason',         t.exit_reason],
          ['Gross P&L',           fmtCurrency(t.gross_pnl)],
          ['Transaction Cost',    `₹${fmt(t.transaction_cost, 2)}`],
          ['Net P&L',             fmtCurrency(t.net_pnl)],
          ['Return',              `${fmt(t.return_pct, 2)}%`],
          ['R-Multiple',          `${fmt(t.r_multiple, 3)}R`],
          ['Holding Days',        String(t.holding_days)],
        ].map(([k, v]) => (
          <div className="detail-row" key={k}>
            <span className="detail-key">{k}</span>
            <span
              className="detail-val"
              style={{
                color: (k === 'Net P&L' || k === 'Gross P&L')
                  ? (t.net_pnl >= 0 ? 'var(--positive)' : 'var(--negative)')
                  : undefined,
              }}
            >
              {String(v)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TradeJournal() {
  const { symbol = 'ITC' } = useParams<{ symbol: string }>();
  const [trades, setTrades]       = useState<TradeRow[]>([]);
  const [selected, setSelected]   = useState<TradeRow | null>(null);
  const [error, setError]         = useState<string | null>(null);
  const [loading, setLoading]     = useState(true);
  const [search, setSearch]       = useState('');
  const [exitFilter, setExitFilter] = useState('');
  const [sortKey, setSortKey]     = useState<SortKey>('trade_id');
  const [sortDir, setSortDir]     = useState<SortDir>('asc');
  const [page, setPage]           = useState(1);

  useEffect(() => {
    api.trades(symbol)
      .then(setTrades)
      .catch(e => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, [symbol]);

  const filtered = useMemo(() => {
    let rows = trades;
    if (exitFilter) rows = rows.filter(r => r.exit_reason === exitFilter);
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(r =>
        r.signal_date.includes(q) ||
        r.entry_date.includes(q)  ||
        r.exit_date.includes(q)   ||
        String(r.trade_id).includes(q)
      );
    }
    return [...rows].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1  : -1;
      return 0;
    });
  }, [trades, search, exitFilter, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows   = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
    setPage(1);
  }

  function sortIcon(key: SortKey) {
    if (sortKey !== key) return ' ↕';
    return sortDir === 'asc' ? ' ↑' : ' ↓';
  }

  const exitReasons = [...new Set(trades.map(t => t.exit_reason))];

  if (loading) return <div className="state-container"><div className="spinner" /><div className="state-title">Loading trades…</div></div>;
  if (error)   return <div className="state-container"><div className="state-icon">⚠</div><div className="state-title">{error}</div></div>;

  return (
    <div className="page-content" style={{ position: 'relative' }}>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div className="page-title">Trade Journal — {symbol}</div>
          <StockSelector currentSymbol={symbol} routeTemplate="/trades/:symbol" />
        </div>
        <div className="page-subtitle">
          {trades.length} executed trades · historical simulation only
        </div>
      </div>

      <div className="disclaimer">
        These are historical simulation trades only. They were never executed in any real market.
        Net P&amp;L values are displayed as computed — including losses.
      </div>

      <div className="table-wrapper">
        <div className="table-controls">
          <input
            className="table-search"
            placeholder="Search by date or trade ID…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            id="trade-search-input"
          />
          <select
            className="table-filter-select"
            value={exitFilter}
            onChange={e => { setExitFilter(e.target.value); setPage(1); }}
            id="exit-reason-filter"
          >
            <option value="">All exit reasons</option>
            {exitReasons.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
            {filtered.length} result{filtered.length !== 1 ? 's' : ''}
          </span>
        </div>

        {filtered.length === 0 ? (
          <div className="state-container">
            <div className="state-title">No trades match the filter</div>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" id="trade-table">
              <thead>
                <tr>
                  {([
                    ['trade_id',    '#'],
                    ['signal_date', 'Signal Date'],
                    ['entry_date',  'Entry Date'],
                    ['entry_price', 'Entry Price'],
                    ['initial_stop','Stop'],
                    ['quantity',    'Qty'],
                    ['exit_date',   'Exit Date'],
                    ['exit_price',  'Exit Price'],
                    ['exit_reason', 'Reason'],
                    ['gross_pnl',   'Gross P&L'],
                    ['transaction_cost', 'Costs'],
                    ['net_pnl',     'Net P&L'],
                    ['return_pct',  'Return'],
                    ['r_multiple',  'R-Mult'],
                    ['holding_days','Hold (d)'],
                  ] as [SortKey, string][]).map(([key, label]) => (
                    <th key={key} onClick={() => toggleSort(key)}>
                      {label}{sortIcon(key)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map(t => (
                  <tr key={t.trade_id} onClick={() => setSelected(t)}>
                    <td>{t.trade_id}</td>
                    <td>{t.signal_date}</td>
                    <td>{t.entry_date}</td>
                    <td>₹{fmt(t.entry_price)}</td>
                    <td>₹{fmt(t.initial_stop)}</td>
                    <td>{t.quantity.toLocaleString('en-IN')}</td>
                    <td>{t.exit_date}</td>
                    <td>₹{fmt(t.exit_price)}</td>
                    <td>{exitBadge(t.exit_reason)}</td>
                    <td className={pnlClass(t.gross_pnl)}>{fmtCurrency(t.gross_pnl)}</td>
                    <td>₹{fmt(t.transaction_cost)}</td>
                    <td className={pnlClass(t.net_pnl)}>{fmtCurrency(t.net_pnl)}</td>
                    <td className={pnlClass(t.return_pct)}>{fmt(t.return_pct, 2)}%</td>
                    <td className={pnlClass(t.r_multiple)}>{fmt(t.r_multiple, 3)}R</td>
                    <td>{t.holding_days}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="pagination">
          <span>Page {page} of {totalPages} · {filtered.length} trades</span>
          <div className="pagination-controls">
            <button className="pagination-btn" onClick={() => setPage(1)} disabled={page === 1}>«</button>
            <button className="pagination-btn" onClick={() => setPage(p => p - 1)} disabled={page === 1}>‹</button>
            <button className="pagination-btn" onClick={() => setPage(p => p + 1)} disabled={page === totalPages}>›</button>
            <button className="pagination-btn" onClick={() => setPage(totalPages)} disabled={page === totalPages}>»</button>
          </div>
        </div>
      </div>

      {selected && <DetailPanel trade={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
