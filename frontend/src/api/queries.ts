import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from './client';
import type { PortfolioSnapshot, MarketSnapshot, CycleObservation, GovernanceReport } from '@/types';

// Portfolio Queries
export const usePortfolio = (profile: string) => {
  return useQuery({
    queryKey: ['portfolio', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<PortfolioSnapshot>(`/portfolio?profile=${profile}`);
      return data;
    },
  });
};

// Market Queries
export const useMarketSnapshot = (profile: string) => {
  return useQuery({
    queryKey: ['market-snapshot', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<MarketSnapshot>(`/market/snapshot?profile=${profile}`);
      return data;
    },
  });
};

// Agent Cycle Mutations & Queries
export const useObserve = () => {
  return useMutation({
    mutationFn: async ({ strategy, mode, profile }: { strategy: string; mode: string; profile: string }) => {
      const { data } = await apiClient.post<CycleObservation>(`/runner/observe`, {
        strategy_name: strategy,
        execution_mode: mode,
      }, {
        params: { profile }
      });
      return data;
    },
  });
};

export const useTraces = (profile: string) => {
  return useQuery({
    queryKey: ['traces', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<{ traces: any[] }>(`/audit/traces?profile=${profile}`);
      return data;
    },
  });
};

// Experiments & Governance
export const useGovernanceReport = (profile: string) => {
  return useQuery({
    queryKey: ['governance', profile],
    queryFn: async () => {
      // Assuming a dedicated endpoint or using CLI proxy. The backend has CLI, need an API.
      // Wait, is there a governance report API endpoint?
      const { data } = await apiClient.get<GovernanceReport>(`/audit/governance?profile=${profile}`);
      return data;
    },
    retry: false
  });
};

// Start Backtest
export const useRunBacktest = () => {
  return useMutation({
    mutationFn: async ({ strategy, days, profile }: { strategy: string; days: number; profile: string }) => {
      const { data } = await apiClient.post(`/runner/backtest?profile=${profile}`, {
        strategy_name: strategy,
        days,
      });
      return data;
    }
  });
};
