import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeAll } from 'vitest';
import { AssistantPanel } from '../components/layout/AssistantPanel';

// Mock the API service
vi.mock('../services/api', () => ({
  sendChatMessage: vi.fn(),
}));

// Mock scrollIntoView which is not implemented in jsdom
beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

describe('AssistantPanel', () => {
  it('renders the toggle button', () => {
    render(
      <MemoryRouter initialEntries={['/backtest/ITC']}>
        <AssistantPanel />
      </MemoryRouter>
    );
    expect(screen.getByText('AI Assistant')).toBeInTheDocument();
  });

  it('inherits the symbol from the route', () => {
    render(
      <MemoryRouter initialEntries={['/backtest/RELIANCE']}>
        <AssistantPanel />
      </MemoryRouter>
    );
    // Open the panel
    fireEvent.click(screen.getByText('AI Assistant'));
    expect(screen.getByText('RELIANCE')).toBeInTheDocument();
  });
});
