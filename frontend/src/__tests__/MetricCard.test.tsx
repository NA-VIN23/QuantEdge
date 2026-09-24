// src/__tests__/MetricCard.test.tsx
import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MetricCard } from '../components/metrics/MetricCard';

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="Total Return" value="-8.54%" id="test-metric" />);
    expect(screen.getByText('Total Return')).toBeInTheDocument();
    expect(screen.getByText('-8.54%')).toBeInTheDocument();
  });

  it('applies negative class for negative sentiment', () => {
    render(<MetricCard label="Net P&L" value="-₹8,535.29" sentiment="negative" id="pnl-metric" />);
    const valueEl = screen.getByText('-₹8,535.29');
    expect(valueEl).toHaveClass('negative');
  });

  it('applies positive class for positive sentiment', () => {
    render(<MetricCard label="Best Trade" value="+₹4,190.37" sentiment="positive" id="best-trade" />);
    const valueEl = screen.getByText('+₹4,190.37');
    expect(valueEl).toHaveClass('positive');
  });

  it('renders sub text when provided', () => {
    render(<MetricCard label="Win Rate" value="32.9%" sub="23W / 47L" id="win-rate" />);
    expect(screen.getByText('23W / 47L')).toBeInTheDocument();
  });

  it('renders without sub text when omitted', () => {
    render(<MetricCard label="Trades" value="70" id="trades" />);
    // should not throw, label and value present
    expect(screen.getByText('70')).toBeInTheDocument();
  });
});
