// src/components/ui/StockSelector.tsx
// Dropdown populated from GET /api/stocks.
// Navigates to the selected symbol route on change.

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import type { StockListItem } from '../../types';

interface Props {
  currentSymbol?: string;
  /** Route template. Default: "/stocks/:symbol" */
  routeTemplate?: string;
}

export function StockSelector({ currentSymbol, routeTemplate = '/stocks/:symbol' }: Props) {
  const [stocks, setStocks] = useState<StockListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.stocks()
      .then(setStocks)
      .catch(() => setStocks([]))
      .finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const sym = e.target.value;
    const route = routeTemplate.replace(':symbol', sym);
    navigate(route);
  };

  if (loading) return <span className="stock-selector-loading">Loading symbols…</span>;
  if (stocks.length === 0) return <span className="stock-selector-empty">No data available</span>;

  return (
    <select
      id="stock-selector"
      className="stock-selector"
      value={currentSymbol ?? stocks[0]?.symbol ?? ''}
      onChange={handleChange}
      aria-label="Select stock symbol"
    >
      {stocks.map(s => (
        <option key={s.symbol} value={s.symbol} title={s.description}>
          {s.symbol}
        </option>
      ))}
    </select>
  );
}
