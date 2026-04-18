export interface PortfolioSnapshot {
  total_value?: number;
  cash?: number;
  positions?: Record<string, number>;
  current_weights?: Record<string, number>;
  target_weights?: Record<string, number>;
  weight_deviation?: Record<string, number>;
  pnl_dollars?: number;
  pnl_pct?: number;
  peak_value?: number;
  error?: string;
}

export interface Position {
  ticker: string;
  quantity: number;
  price: number;
  value: number;
  weight: number;
  target_weight: number;
  drift: number;
  side: 'long' | 'short';
  idea_id?: string;
}

export interface ExecutionResult {
  id?: number;
  timestamp: string;
  cycle_id: string;
  ticker: string;
  action: string;
  quantity: number;
  market_price: number;
  fill_price: number;
  cost: number;
  slippage: number;
  slippage_pct?: number;
  success: boolean | number;
  error?: string;
  reason?: string;
  drift_before?: number;
}

export interface DecisionTrace {
  id: number;
  cycle_id: string;
  stage: string;
  payload_json: string;
  validation_json?: string;
  mcp_tools_json?: string;
  provider?: string;
  agent_backend?: string;
  execution_mode?: string;
  event_type?: string;
  tags?: string;
  created_at: string;
}

export interface AgentRun {
  cycle_id: string;
  timestamp: string;
  strategy?: string;
  signal: boolean | number;
  trades_count: number;
  provider?: string;
  tool_calls?: number;
  fetch_latency_ms?: number;
  /** Legacy UI field name */
  kill_switch?: boolean;
}

export interface MarketMetrics {
  ticker: string;
  price: number;
  ytd_return: number;
  volatility_30d: number;
  sharpe: number;
}

export interface AppConfig {
  ai_provider?: string;
  agent_backend?: string;
  execution_mode?: string;
  target_allocation?: Record<string, number>;
  hedge_fund_enabled?: boolean;
  error?: string;
}

export interface IdeaBookRow {
  idea_id: string;
  ticker: string;
  side: string;
  thesis: string;
  catalyst?: string;
  time_horizon?: string;
  conviction?: number;
  status: string;
  review_status?: string;
  llm_generated?: boolean;
  sleeve?: string;
  source?: string;
  origin_cycle_id?: string;
  supporting_signals?: string[] | string;
  evidence_quality?: string;
  edge_source?: string;
  why_now?: string;
  key_risk?: string;
}

export interface SnapshotRow {
  id?: number;
  timestamp: string;
  cycle_id: string;
  total_value: number;
  cash: number;
  peak_value?: number;
  drawdown?: number;
}

export type JsonRecord = Record<string, unknown>;

export interface OnboardingStatus {
  needs_onboarding: boolean;
  profile: string;
  positions_count: number;
}

export interface OnboardingProfile {
  name: string;
  label: string;
  description: string;
  risk_level: 'Low' | 'Medium' | 'High' | 'Very High';
  strategy_type: string;
  typical_aum: string;
  initial_capital: number;
  tickers: string[];
}

export interface TradePreview {
  current_price: number;
  estimated_cost: number;
  current_holding: number;
  current_weight: number;
  new_weight: number;
  cash_after: number;
  portfolio_value: number;
  available_cash: number;
}

export interface TradeOpinion {
  recommendation: 'APPROVE' | 'CAUTION' | 'REJECT';
  rationale: string;
  confidence: number;
  risk_flags: string[];
  market_context: string;
}

// ── Trading Core ─────────────────────────────────────────────────────────────

export interface Instrument {
  instrument_id: string;
  symbol: string;
  name: string;
  asset_class: string;
  sector?: string;
  is_active: boolean;
}

export interface TC_Order {
  order_id: string;
  cycle_id: string;
  symbol: string;
  side: string;
  requested_quantity: number;
  status: string;
  created_at: string;
}

export interface TC_Execution {
  execution_id: string;
  order_id: string;
  symbol: string;
  side: string;
  quantity: number;
  market_price: number;
  fill_price: number;
  notional: number;
  fees: number;
  executed_at: string;
}

export interface TC_Position {
  instrument_id: string;
  symbol: string;
  quantity: number;
  avg_cost: number;
  last_price: number;
  market_value: number;
  updated_at: string;
}

export interface CashMovement {
  cash_movement_id: string;
  cycle_id?: string;
  movement_type: string;
  amount: number;
  created_at: string;
  description?: string;
}

// ── Middle Office ────────────────────────────────────────────────────────────

export interface ReconciliationBreak {
  break_type: string;
  subject: string;
  legacy_value: number;
  ledger_value: number;
  diff: number;
  severity: string;
}

export interface TCAReport {
  cycle_id: string;
  total_trades: number;
  total_notional: number;
  total_slippage_dollars: number;
  avg_slippage_bps: number;
  trade_details: Array<{
    symbol: string;
    side: string;
    quantity: number;
    market_price: number;
    fill_price: number;
    slippage_dollars: number;
    slippage_bps: number;
    fees: number;
  }>;
}
