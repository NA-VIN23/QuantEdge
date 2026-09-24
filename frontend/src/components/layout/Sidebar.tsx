// src/components/layout/Sidebar.tsx
// Sprint 5: Nav items use default ITC symbol routes.
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV: NavItem[] = [
  { to: '/',             label: 'Overview',       icon: '\u25c8' },
  { to: '/stocks/ITC',   label: 'Stock Analysis', icon: '\u2197' },
  { to: '/backtest/ITC', label: 'Backtest Lab',   icon: '\u27f3' },
  { to: '/trades/ITC',   label: 'Trade Journal',  icon: '\u2261' },
  { to: '/data/ITC',     label: 'Data Center',    icon: '\u229e' },
];

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-name">QuantEdge</div>
        <div className="sidebar-logo-sub">Research Platform</div>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Research</div>
        {NAV.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            <span className="nav-item-icon" aria-hidden="true">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-dataset">
        <div className="sidebar-dataset-label">Dataset</div>
        <div className="sidebar-dataset-value">ITC \u00b7 NSE</div>
      </div>
    </aside>
  );
}
