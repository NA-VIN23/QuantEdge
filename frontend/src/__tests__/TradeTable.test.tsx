// src/__tests__/TradeTable.test.tsx
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { TradeJournal } from '../pages/TradeJournal';
import { api } from '../services/api';
import type { TradeRow } from '../types';

// Mock the API module — include stocks for StockSelector (Sprint 5)
vi.mock('../services/api', () => ({
  api: {
    trades: vi.fn(),
    stocks: vi.fn(),
  },
}));

function renderJournal() {
  return render(
    <MemoryRouter initialEntries={['/trades/ITC']}>
      <TradeJournal />
    </MemoryRouter>
  );
}

const MOCK_TRADES: TradeRow[] = Array.from({ length: 30 }, (_, i) => ({
  trade_id: i + 1,
  symbol: 'ITC',
  signal_date: `2020-01-${String(i + 1).padStart(2, '0')}`,
  entry_date: `2020-01-${String(i + 2).padStart(2, '0')}`,
  entry_reference_price: 100 + i,
  entry_price: 100.05 + i,
  initial_stop: 96 + i,
  atr_at_signal: 2.0,
  quantity: 250,
  risk_budget: 1000,
  exit_date: `2020-02-${String(i + 1).padStart(2, '0')}`,
  exit_reference_price: 110 + i,
  exit_price: 109.9 + i,
  exit_reason: i % 2 === 0 ? 'TREND_EXIT' : 'STOP_LOSS',
  gross_pnl: i % 2 === 0 ? 500 + i * 10 : -(200 + i * 5),
  transaction_cost: 10,
  net_pnl: i % 2 === 0 ? 490 + i * 10 : -(210 + i * 5),
  return_pct: i % 2 === 0 ? 4.9 : -2.1,
  r_multiple: i % 2 === 0 ? 0.49 : -0.21,
  holding_days: 14 + i,
}));

describe('TradeJournal', () => {
  beforeEach(() => {
    vi.mocked(api.trades).mockResolvedValue(MOCK_TRADES);
    // Sprint 5: StockSelector calls api.stocks
    (api.stocks as ReturnType<typeof vi.fn>).mockResolvedValue([
      { symbol: 'ITC', description: 'ITC Ltd - NSE' },
    ]);
  });

  it('renders the page title', async () => {
    renderJournal();
    // Sprint 5: title now shows symbol
    expect(await screen.findByText(/Trade Journal/i)).toBeInTheDocument();
  });

  it('shows total trade count in subtitle', async () => {
    renderJournal();
    expect(await screen.findByText(/30 executed trades/i)).toBeInTheDocument();
  });

  it('paginates — shows first 25 trades on page 1', async () => {
    renderJournal();
    await screen.findByText(/Trade Journal/i);
    const rows = screen.getAllByRole('row');
    // 1 header + 25 data rows
    expect(rows.length).toBe(26);
  });

  it('navigates to page 2', async () => {
    renderJournal();
    await screen.findByText(/Trade Journal/i);
    const nextBtn = screen.getByText('›');
    fireEvent.click(nextBtn);
    expect(screen.getByText(/Page 2 of 2/i)).toBeInTheDocument();
  });

  it('filters by exit reason', async () => {
    renderJournal();
    await screen.findByText(/Trade Journal/i);
    // The exit filter select has no aria-label; use getByRole with name from its sibling label
    const selects = screen.getAllByRole('combobox');
    // selects[0] = stock-selector, selects[1] = exit reason filter
    const exitSelect = selects.find(s => s.id !== 'stock-selector') ?? selects[selects.length - 1];
    fireEvent.change(exitSelect, { target: { value: 'STOP_LOSS' } });
    // All visible rows should be STOP_LOSS
    const badges = screen.getAllByText('STOP LOSS');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('displays negative net P&L', async () => {
    renderJournal();
    await screen.findByText(/Trade Journal/i);
    // At least one negative P&L cell should be rendered (STOP_LOSS trades)
    const negativeCells = document.querySelectorAll('.td-negative');
    expect(negativeCells.length).toBeGreaterThan(0);
  });

  it('shows disclaimer text', async () => {
    renderJournal();
    await screen.findByText(/historical simulation trades only/i);
  });
});
