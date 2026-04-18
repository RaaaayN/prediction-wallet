import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from './client';
import type { 
  PortfolioSnapshot, 
  MarketSnapshot, 
  CycleObservation, 
  GovernanceReport,
  SystemStatus,
  MonteCarloResult,
  CorrelationData,
  StressScenario,
  IdeaBookEntry
} from '@/types';

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

// System & Analytics Queries
export const useSystemStatus = (profile: string) => {
  return useQuery({
    queryKey: ['system-status', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<SystemStatus>(`/status?profile=${profile}`);
      return data;
    },
  });
};

export const useMonteCarlo = (profile: string, paths: number = 5000) => {
  return useQuery({
    queryKey: ['monte-carlo', profile, paths],
    queryFn: async () => {
      const { data } = await apiClient.get<MonteCarloResult>(`/monte-carlo?profile=${profile}&paths=${paths}`);
      return data;
    },
    enabled: false, // Manual trigger usually preferred for heavy analytics
  });
};

export const useCorrelation = (profile: string, days: number = 90) => {
  return useQuery({
    queryKey: ['correlation', profile, days],
    queryFn: async () => {
      const { data } = await apiClient.get<CorrelationData>(`/correlation?profile=${profile}&days=${days}`);
      return data;
    },
  });
};

export const useStressTests = (profile: string) => {
  return useQuery({
    queryKey: ['stress-tests', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<StressScenario[]>(`/stress?profile=${profile}`);
      return data;
    },
  });
};

// Idea Book Queries
export const useIdeaBook = (profile: string) => {
  return useQuery({
    queryKey: ['idea-book', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<IdeaBookEntry[]>(`/idea-book?profile=${profile}`);
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

// Governance
export const useGovernanceReport = (profile: string) => {
  return useQuery({
    queryKey: ['governance', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<GovernanceReport>(`/audit/governance?profile=${profile}`);
      return data;
    },
    retry: false
  });
};

// Backtesting
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

// Idea Book Mutations
export const useGenerateIdeas = () => {
  return useMutation({
    mutationFn: async ({ profile }: { profile: string }) => {
      const { data } = await apiClient.post(`/idea-book/generate?profile=${profile}`, {});
      return data;
    }
  });
};

export const useReviewIdea = () => {
  return useMutation({
    mutationFn: async ({ idea_id, status, profile }: { idea_id: string; status: string; profile: string }) => {
      const { data } = await apiClient.post(`/idea-book/${idea_id}/review?profile=${profile}`, {
        review_status: status
      });
      return data;
    }
  });
};
