// src/components/layout/Header.tsx
import { useLocation } from 'react-router-dom';

function getTitle(pathname: string): string {
  if (pathname.startsWith('/stocks')) return 'Stock Analysis';
  if (pathname.startsWith('/backtest')) return 'Backtest Lab';
  if (pathname.startsWith('/trades')) return 'Trade Journal';
  if (pathname.startsWith('/data')) return 'Data Center';
  return 'Overview';
}

function getSymbol(pathname: string): string {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length >= 2) {
    return parts[1].toUpperCase();
  }
  return 'ITC';
}

export function Header() {
  const { pathname } = useLocation();
  const title = getTitle(pathname);
  const symbol = getSymbol(pathname);

  return (
    <header className="header">
      <div className="header-title">{title}</div>
      <div className="header-right">
        <div className="header-badge">
          <span className="header-badge-dot" />
          {symbol} · Historical Data
        </div>
        <div className="research-badge">Research Mode</div>
      </div>
    </header>
  );
}
