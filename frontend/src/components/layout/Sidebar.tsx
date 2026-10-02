// src/components/layout/Sidebar.tsx
// Sprint 5: Dynamic nav items using active symbol route.
import { NavLink, useLocation } from 'react-router-dom';

function getSymbol(pathname: string): string {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length >= 2) {
    return parts[1].toUpperCase();
  }
  return 'ITC';
}

export function Sidebar() {
  const { pathname } = useLocation();
  const currentSymbol = getSymbol(pathname);

  const nav = [
    { to: '/',                         label: 'Overview',       icon: '\u25c8', end: true },
    { to: `/stocks/${currentSymbol}`,   label: 'Stock Analysis', icon: '\u2197', end: false },
    { to: `/backtest/${currentSymbol}`, label: 'Backtest Lab',   icon: '\u27f3', end: false },
    { to: `/trades/${currentSymbol}`,   label: 'Trade Journal',  icon: '\u2261', end: false },
    { to: `/data/${currentSymbol}`,     label: 'Data Center',    icon: '\u229e', end: false },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-name">QuantEdge</div>
        <div className="sidebar-logo-sub">Research Platform</div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Research</div>
        {nav.map(item => (
          <NavLink
            key={item.label}
            to={item.to}
            end={item.end}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-item-icon" aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-dataset">
        <div className="sidebar-dataset-label">Active Symbol</div>
        <div className="sidebar-dataset-value">{currentSymbol} \u00b7 NSE</div>
      </div>
    </aside>
  );
}
