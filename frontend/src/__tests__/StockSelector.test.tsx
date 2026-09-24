// src/__tests__/StockSelector.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MemoryRouter } from 'react-router-dom';
import { StockSelector } from '../components/ui/StockSelector';

// Mock the api module
vi.mock('../services/api', () => ({
  api: {
    stocks: vi.fn(),
  },
}));

import { api } from '../services/api';

function renderWithRouter(ui: React.ReactElement, initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>
  );
}

describe('StockSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    (api.stocks as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    renderWithRouter(<StockSelector />);
    expect(screen.getByText(/loading symbols/i)).toBeInTheDocument();
  });

  it('renders select with ITC option after loading', async () => {
    (api.stocks as ReturnType<typeof vi.fn>).mockResolvedValue([
      { symbol: 'ITC', description: 'ITC Ltd - NSE' },
    ]);
    renderWithRouter(<StockSelector currentSymbol="ITC" />);
    await waitFor(() => {
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });
    expect(screen.getByText('ITC')).toBeInTheDocument();
  });

  it('renders multiple symbols when available', async () => {
    (api.stocks as ReturnType<typeof vi.fn>).mockResolvedValue([
      { symbol: 'ITC',      description: 'ITC Ltd' },
      { symbol: 'RELIANCE', description: 'Reliance Industries' },
    ]);
    renderWithRouter(<StockSelector currentSymbol="ITC" />);
    await waitFor(() => {
      expect(screen.getByText('ITC')).toBeInTheDocument();
      expect(screen.getByText('RELIANCE')).toBeInTheDocument();
    });
  });

  it('shows empty state when no stocks available', async () => {
    (api.stocks as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    renderWithRouter(<StockSelector />);
    await waitFor(() => {
      expect(screen.getByText(/no data available/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when API errors', async () => {
    (api.stocks as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('API down'));
    renderWithRouter(<StockSelector />);
    await waitFor(() => {
      expect(screen.getByText(/no data available/i)).toBeInTheDocument();
    });
  });

  it('select has correct id for accessibility', async () => {
    (api.stocks as ReturnType<typeof vi.fn>).mockResolvedValue([
      { symbol: 'ITC', description: 'ITC Ltd' },
    ]);
    renderWithRouter(<StockSelector />);
    await waitFor(() => {
      expect(screen.getByRole('combobox')).toHaveAttribute('id', 'stock-selector');
    });
  });
});
