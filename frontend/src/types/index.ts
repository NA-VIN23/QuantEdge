// src/types/index.ts
// TypeScript interfaces matching the FastAPI response schemas exactly.

export interface StockListItem {
  symbol: string;
  description: string;
}

export interface OHLCVRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FeatureRow extends OHLCVRow {
  ema20: number | null;
  ema50: number | null;
  sma20: number | null;
  sma50: number | null;
  atr14: number | null;
  avg_volume_20: number | null;
  volume_ratio: number | null;
  momentum_5: number | null;
  momentum_20: number | null;
  trend_condition: boolean;
  price_condition: boolean;
  breakout_condition: boolean;
  volume_condition: boolean;
  signal: string;
}

export interface StockMeta {
  symbol: string;
  date_min: string;
  date_max: string;
  row_count: number;
  columns: string[];
}

export interface BacktestSummary {
  initial_capital: number;
  final_equity: number;
  total_net_pnl: number;
  total_return_pct: number;
  num_signals_total: number;
  num_signals_executed: number;
  num_signals_skipped: number;
  num_trades: number;
  num_wins: number;
  num_losses: number;
  win_rate: number | null;
  avg_net_pnl: number | null;
  avg_win_pnl: number | null;
  avg_loss_pnl: number | null;
  profit_factor: number | null;
  max_drawdown_pct: number;
  avg_holding_days: number | null;
  exposure_pct: number;
  best_trade_net_pnl: number | null;
  worst_trade_net_pnl: number | null;
  exit_reason_counts: Record<string, number>;
  skip_reason_counts: Record<string, number>;
  backtest_config: Record<string, unknown>;
}

export interface OverviewResponse {
  dataset: StockMeta;
  strategy_name: string;
  num_signals: number;
  backtest: BacktestSummary;
}

export interface TradeRow {
  trade_id: number;
  symbol: string;
  signal_date: string;
  entry_date: string;
  entry_reference_price: number;
  entry_price: number;
  initial_stop: number;
  atr_at_signal: number;
  quantity: number;
  risk_budget: number;
  exit_date: string;
  exit_reference_price: number;
  exit_price: number;
  exit_reason: string;
  gross_pnl: number;
  transaction_cost: number;
  net_pnl: number;
  return_pct: number;
  r_multiple: number;
  holding_days: number;
}

export interface EquityCurveRow {
  date: string;
  cash: number;
  position_quantity: number;
  position_market_value: number;
  equity: number;
}

export interface DataQualityReport {
  source_filename: string;
  symbol: string;
  original_row_count: number;
  final_row_count: number;
  removed_row_count: number;
  date_min: string;
  date_max: string;
  missing_counts: Record<string, number>;
  duplicate_exact_count: number;
  duplicate_date_count: number;
  invalid_ohlc_count: number;
  invalid_volume_count: number;
  zero_volume_count: number;
  negative_volume_count: number;
  invalid_date_count: number;
  non_monotonic_date_count: number;
  change_pct_mismatch_count: number;
  cleaning_issue_count: number;
  status: string;
  generated_at: string;
}
