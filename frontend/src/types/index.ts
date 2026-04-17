export interface PortfolioSnapshot {
  total_value: number;
  cash: number;
  positions: Record<string, number>;
  current_weights: Record<string, number>;
  target_weights: Record<string, number>;
  weight_deviation: Record<string, number>;
  pnl_dollars: number;
  pnl_pct: number;
  peak_value: number;
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
  action: 'buy' | 'sell';
  quantity: number;
  market_price: number;
  fill_price: number;
  cost: number;
  slippage: number;
  slippage_pct: number;
  success: boolean | number;
  error?: string;
  reason?: string;
  drift_before?: number;
}

export interface DecisionTrace {
  id: number;
  cycle_id: string;
  stage: 'observe' | 'decide' | 'validate' | 'execute' | 'audit';
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
  signal: boolean;
  trades_count: number;
  provider?: string;
  tool_calls?: number;
  fetch_latency_ms?: number;
  kill_switch: boolean;
}

export interface MarketMetrics {
  ticker: string;
  price: number;
  ytd_return: number;
  volatility_30d: number;
  sharpe: number;
}
