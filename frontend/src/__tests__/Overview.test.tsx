// src/__tests__/Overview.test.tsx
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Overview } from '../pages/Overview';
import { api } from '../services/api';
import type { OverviewResponse, EquityCurveRow } from '../types';

vi.mock('../services/api', () => ({
  api: {
    overview: vi.fn(),
    equityCurve: vi.fn(),
    stocks: vi.fn(),  // Sprint 5: StockSelector uses this
  },
}));

// Minimal mock data — uses the actual ITC backtest values from Sprint 3
const MOCK_OVERVIEW: OverviewResponse = {
  dataset: {
    symbol: 'ITC',
    date_min: '2005-04-01',
    date_max: '2025-05-29',
    row_count: 5000,
    columns: ['date', 'open', 'high', 'low', 'close', 'volume', 'ema20'],
  },
  strategy_name: 'Daily Trend-Momentum Breakout',
  num_signals: 137,
  backtest: {
    initial_capital: 100000,
    final_equity: 91464.71,
    total_net_pnl: -8535.29,
    total_return_pct: -8.54,
    num_signals_total: 137,
    num_signals_executed: 70,
    num_signals_skipped: 67,
    num_trades: 70,
    num_wins: 23,
    num_losses: 47,
    win_rate: 0.3286,
    avg_net_pnl: -121.93,
    avg_win_pnl: 1293.59,
    avg_loss_pnl: -814.64,
    profit_factor: 0.777,
    max_drawdown_pct: -25.14,
    avg_holding_days: 21.84,
    exposure_pct: 22.22,
    best_trade_net_pnl: 4190.37,
    worst_trade_net_pnl: -1097.83,
    exit_reason_counts: { TREND_EXIT: 37, STOP_LOSS: 33 },
    skip_reason_counts: { SKIPPED_IN_POSITION: 67 },
    backtest_config: { initial_capital: 100000, risk_per_trade: 0.01 },
  },
};

const MOCK_EQUITY: EquityCurveRow[] = [
  { date: '2005-04-01', cash: 100000, position_quantity: 0, position_market_value: 0, equity: 100000 },
  { date: '2025-05-29', cash: 91464.71, position_quantity: 0, position_market_value: 0, equity: 91464.71 },
];

describe('Overview', () => {
  beforeEach(() => {
    vi.mocked(api.overview).mockResolvedValue(MOCK_OVERVIEW);
    vi.mocked(api.equityCurve).mockResolvedValue(MOCK_EQUITY);
    // Sprint 5: StockSelector calls api.stocks
    (api.stocks as ReturnType<typeof vi.fn>).mockResolvedValue([
      { symbol: 'ITC', description: 'ITC Ltd - NSE' },
    ]);
  });

  it('renders page title', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    expect(await screen.findByText('Research Overview')).toBeInTheDocument();
  });

  it('displays the negative total return', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    // -8.54% must be displayed as-is
    expect(await screen.findByText(/-8\.54%/)).toBeInTheDocument();
  });

  it('displays negative net P&L', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    // −₹8,535.29 or similar representation
    const pnlEl = await screen.findByText(/8,535/);
    expect(pnlEl).toBeInTheDocument();
  });

  it('shows dataset symbol ITC', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    const itcEls = await screen.findAllByText(/ITC/);
    expect(itcEls.length).toBeGreaterThan(0);
  });

  it('shows row count', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    expect(await screen.findByText('5,000')).toBeInTheDocument();
  });

  it('shows strategy name', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    expect(await screen.findByText('Daily Trend-Momentum Breakout')).toBeInTheDocument();
  });

  it('shows disclaimer', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    expect(await screen.findByText(/Historical simulation only/i)).toBeInTheDocument();
  });

  it('renders error state when API fails', async () => {
    vi.mocked(api.overview).mockRejectedValue(new Error('API unavailable'));
    vi.mocked(api.equityCurve).mockRejectedValue(new Error('API unavailable'));
    render(<MemoryRouter><Overview /></MemoryRouter>);
    expect(await screen.findByText(/Could not load data/i)).toBeInTheDocument();
  });

  it('displays win rate correctly', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    // 32.9% win rate
    expect(await screen.findByText(/32\.9%/)).toBeInTheDocument();
  });

  it('negative return metric has negative CSS class', async () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    const returnEl = await screen.findByText(/-8\.54%/);
    expect(returnEl).toHaveClass('negative');
  });
});
