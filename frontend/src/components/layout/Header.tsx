// src/components/layout/Header.tsx
import { useLocation } from 'react-router-dom';

const TITLES: Record<string, string> = {
  '/': 'Overview',
  '/stocks/ITC': 'Stock Analysis',
  '/backtest': 'Backtest Lab',
  '/trades': 'Trade Journal',
  '/data': 'Data Center',
};

export function Header() {
  const { pathname } = useLocation();
  const title = TITLES[pathname] ?? 'QuantEdge';

  return (
    <header className="header">
      <div className="header-title">{title}</div>
      <div className="header-right">
        <div className="header-badge">
          <span className="header-badge-dot" />
          ITC · Historical Data
        </div>
        <div className="research-badge">Research Mode</div>
      </div>
    </header>
  );
}
