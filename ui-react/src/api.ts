/** API base: same origin in production; Vite dev server proxies `/api`. */

const json = async <T>(path: string): Promise<T> => {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
};

export type PortfolioResponse = Record<string, unknown> & {
  total_value?: number;
  cash?: number;
  pnl_dollars?: number;
  pnl_pct?: number;
  error?: string;
};

export type SnapshotRow = {
  id: number;
  timestamp: string;
  cycle_id: string;
  total_value: number;
  cash: number;
  drawdown: number;
};

export type AgentRunRow = {
  id: number;
  cycle_id: string;
  timestamp: string;
  strategy: string | null;
  trades_count: number;
  kill_switch: number;
};

export type PositionRow = {
  ticker: string;
  quantity: number;
  price: number;
  value: number;
  weight: number;
  target_weight: number;
  drift: number;
  side?: string;
};

export const api = {
  portfolio: () => json<PortfolioResponse>("/api/portfolio"),
  snapshots: (limit = 60) => json<SnapshotRow[]>(`/api/snapshots?limit=${limit}`),
  runs: (limit = 15) => json<AgentRunRow[]>(`/api/runs?limit=${limit}`),
  positions: () => json<PositionRow[]>("/api/positions"),
  config: () => json<Record<string, unknown>>("/api/config"),
};
