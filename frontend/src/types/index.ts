export interface PortfolioSnapshot {
  positions: Record<string, number>;
  position_sides: Record<string, string>;
  average_costs: Record<string, number>;
  cash: number;
  peak_value: number;
  total_value: number;
  current_weights: Record<string, number>;
  target_weights: Record<string, number>;
  weight_deviation: Record<string, number>;
  pnl_dollars: number;
  pnl_pct: number;
  last_rebalanced?: string;
  history?: Array<{ date: string; total_value: number }>;
}

export interface RiskStatus {
  kill_switch_active: boolean;
  drawdown: number;
  max_trades_per_cycle: number;
  max_order_fraction_of_portfolio: number;
  allowed_tickers: string[];
  execution_mode: string;
}

export interface ExposureSnapshot {
  gross_exposure: number;
  net_exposure: number;
  long_exposure: number;
  short_exposure: number;
  leverage_used: number;
  sector_gross: Record<string, number>;
  single_name_concentration: Record<string, number>;
}

export interface BookRiskSnapshot {
  exposure: ExposureSnapshot;
  breaches: string[];
}

export interface MarketDataStatus {
  ticker: string;
  refreshed_at?: string;
  success: boolean;
}

export interface MarketSnapshot {
  prices: Record<string, number>;
  metrics: Record<string, any>;
  refresh_status: MarketDataStatus[];
}

export interface CycleObservation {
  cycle_id: string;
  strategy_name: string;
  portfolio: PortfolioSnapshot;
  market: MarketSnapshot;
  risk: RiskStatus;
  exposures: ExposureSnapshot;
  book_risk: BookRiskSnapshot;
}

export interface TradeProposal {
  action: string;
  ticker: string;
  quantity: number;
  reason: string;
}

export interface RejectedTrade {
  action: string;
  ticker: string;
  quantity: number;
  reason: string;
  rejection_reason: string;
}

export interface TradeDecision {
  cycle_id: string;
  summary: string;
  rationale: string;
  rebalance_needed: boolean;
  approved_trades: TradeProposal[];
  rejected_trades: RejectedTrade[];
  confidence: number;
  data_freshness: string;
}

export interface PolicyViolation {
  code: string;
  message: string;
}

export interface PolicyEvaluation {
  approved: boolean;
  allowed_trades: TradeProposal[];
  blocked_trades: RejectedTrade[];
  violations: PolicyViolation[];
}

export interface ExecutionResult {
  action: string;
  ticker: string;
  quantity: number;
  market_price: number;
  fill_price: number;
  cost: number;
  success: boolean;
  error?: string;
}

export interface CycleAudit {
  cycle_id: string;
  timestamp: string;
  strategy_name: string;
  execution_mode: string;
  portfolio: PortfolioSnapshot;
  decision: TradeDecision;
  policy: PolicyEvaluation;
  executions: ExecutionResult[];
}

export interface BacktestResult {
  strategy_name: string;
  days: number;
  annualized_return: number;
  sharpe: number;
  max_drawdown: number;
  alpha: number;
  beta: number;
  n_trades: number;
  n_risk_violations: number;
  data_hash?: string;
  history?: Array<{ date: string; total_value: number }>;
}

export interface GovernanceReport {
  timestamp: string;
  risk_violations_count: number;
  recent_violations: any[];
  champion_strategy?: string;
  data_lineage_status: string;
}

export interface IdeaBookEntry {
  idea_id: string;
  ticker: string;
  status: string;
  review_status: string;
  rationale: string;
  alpha_expectation?: number;
  risk_score?: number;
  llm_generated: boolean;
  created_at: string;
}

export interface StressScenario {
  scenario: string;
  equity_shock: number;
  bond_shock: number;
  crypto_shock: number;
  pnl_dollars: number;
  pnl_pct: number;
  kill_switch_triggered: boolean;
}

export interface CorrelationData {
  tickers: string[];
  matrix: number[][];
  days: number;
  n_obs: number;
}

export interface SystemStatus {
  health: {
    status: string;
    checks: Record<string, any>;
  };
  last_rebalance?: any;
  last_reconciliation?: any;
  last_nav?: any;
  backups: {
    count: number;
    latest?: string;
  };
}

export interface MonteCarloResult {
  current_value: number;
  expected_value: number;
  var_95: number;
  cvar_95: number;
  percentiles: Record<string, number>;
  paths?: number[][];
}
