import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from './client';
import type { 
  PortfolioSnapshot, 
  CycleObservation, 
  GovernanceReport,
  SystemStatus,
  MonteCarloResult,
  CorrelationData,
  StressScenario,
  IdeaBookEntry,
  ReportInfo,
  BacktestResult
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
      const { data } = await apiClient.get(`/market/snapshot?profile=${profile}`);
      return data;
    },
  });
};

export const useRefreshMarket = () => {
  return useMutation({
    mutationFn: async (profile: string) => {
      const { data } = await apiClient.post(`/market/refresh?profile=${profile}`);
      return data;
    }
  });
};

export const useSentiment = (profile: string) => {
  return useQuery({
    queryKey: ['sentiment', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/market/sentiment?profile=${profile}`);
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
        strategy: strategy,
        mode: mode,
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

export const useReports = (profile: string) => {
  return useQuery({
    queryKey: ['reports', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<ReportInfo[]>(`/reports?profile=${profile}`);
      return data;
    },
  });
};

export const useGenerateReport = () => {
  return useMutation({
    mutationFn: async ({ profile }: { profile: string }) => {
      const { data } = await apiClient.post(`/run/report`, { profile });
      return data;
    }
  });
};

// Backtesting
export const useRunBacktest = () => {
  return useMutation({
    mutationFn: async ({ strategy, days, profile, run_name, strategy_params }: { strategy: string; days: number; profile: string; run_name?: string; strategy_params?: any }) => {
      const { data } = await apiClient.post(`/runner/backtest?profile=${profile}`, {
        strategy_name: strategy,
        days,
        run_name,
        strategy_params
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

// Trading Core Queries
export const useTradingCoreOrders = (profile: string) => {
  return useQuery({
    queryKey: ['trading-core-orders', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/trading-core/orders?profile=${profile}`);
      return data;
    },
  });
};

export const useTradingCoreExecutions = (profile: string) => {
  return useQuery({
    queryKey: ['trading-core-executions', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/trading-core/executions?profile=${profile}`);
      return data;
    },
  });
};

export const useTradingCorePositions = (profile: string) => {
  return useQuery({
    queryKey: ['trading-core-positions', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/trading-core/positions?profile=${profile}`);
      return data;
    },
  });
};

export const useTCCashMovements = (profile: string) => {
  return useQuery({
    queryKey: ['trading-core-cash-movements', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/trading-core/cash-movements?profile=${profile}`);
      return data;
    },
  });
};

export const useCreateCashMovement = () => {
  return useMutation({
    mutationFn: async ({ profile, amount, type, description }: { profile: string; amount: number; type: string; description?: string }) => {
      const { data } = await apiClient.post(`/trading-core/cash-movements?profile=${profile}`, {
        amount,
        movement_type: type,
        description
      });
      return data;
    }
  });
};

// Middle Office Queries
export const useReconciliation = (profile: string) => {
  return useQuery({
    queryKey: ['reconciliation', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/middle-office/reconcile?profile=${profile}`);
      return data;
    },
  });
};

export const useTCA = (profile: string) => {
  return useQuery({
    queryKey: ['tca', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/middle-office/tca?profile=${profile}`);
      return data;
    },
  });
};

export const useSyncLegacy = () => {
  return useMutation({
    mutationFn: async (profile: string) => {
      const { data } = await apiClient.post(`/middle-office/sync?profile=${profile}`);
      return data;
    }
  });
};

export const useCalculateNAV = () => {
  return useMutation({
    mutationFn: async (profile: string) => {
      const { data } = await apiClient.post(`/middle-office/nav/calculate?profile=${profile}`);
      return data;
    }
  });
};

export const useNAVHistory = (profile: string) => {
  return useQuery({
    queryKey: ['nav-history', profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/middle-office/nav/history?profile=${profile}`);
      return data;
    },
  });
};

export const useTriggerBackup = () => {
  return useMutation({
    mutationFn: async (profile: string) => {
      const { data } = await apiClient.post(`/middle-office/backup?profile=${profile}`);
      return data;
    }
  });
};


// Strategy Lab Queries
export const useStrategies = () => {
  return useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const { data } = await apiClient.get('/strategies');
      return data;
    },
  });
};

export const useUpdateStrategyParams = () => {
  return useMutation({
    mutationFn: async ({ strategy, params }: { strategy: string; params: any }) => {
      const { data } = await apiClient.post(`/strategies/params?strategy=${strategy}`, params);
      return data;
    }
  });
};


// Experiments Queries
export const useExperiments = () => {
  return useQuery({
    queryKey: ['experiments'],
    queryFn: async () => {
      const { data } = await apiClient.get('/experiments');
      return data;
    },
  });
};

export const useDeployModel = () => {
  return useMutation({
    mutationFn: async (run_id: string) => {
      const { data } = await apiClient.post(`/experiments/${run_id}/deploy`);
      return data;
    }
  });
};

export const useTrainModel = () => {
  return useMutation({
    mutationFn: async ({ profile, params }: { profile: string; params?: any }) => {
      const { data } = await apiClient.post(`/run/train?profile=${profile}`, {
        strategy_params: params
      });
      return data;
    }
  });
};

export interface ModelTestResult extends BacktestResult {
  ok: boolean;
  model_run_id: string;
  initial_capital: number;
  tickers: string[];
  gold_dataset_name?: string | null;
  metrics?: Record<string, number>;
}

export const useTestTrainedModel = () => {
  return useMutation({
    mutationFn: async ({
      run_id,
      profile,
      days,
      initial_capital,
      tickers,
      gold_dataset_name,
      run_name,
    }: {
      run_id: string;
      profile: string;
      days: number;
      initial_capital: number;
      tickers: string[];
      gold_dataset_name?: string | null;
      run_name?: string;
    }) => {
      const { data } = await apiClient.post(`/experiments/${run_id}/test?profile=${profile}`, {
        days,
        initial_capital,
        tickers,
        gold_dataset_name,
        run_name,
      });
      // Flatten nested metrics dict into top-level for BacktestResult compatibility
      const metrics = (data as any).metrics || {};
      return {
        ...data,
        ...metrics,
        n_trades: (data as any).trades?.length ?? metrics.n_trades ?? 0,
        n_risk_violations: (data as any).risk_violations?.length ?? metrics.n_risk_violations ?? 0,
      } as ModelTestResult;
    }
  });
};

export const useAlphaScript = (name: string = "alpha_factory.py") => {
  return useQuery({
    queryKey: ['alpha-script', name],
    queryFn: async () => {
      const { data } = await apiClient.get(`/research/scripts/${name}`);
      return data.content as string;
    },
  });
};

export const useAlphaScriptsList = () => {
  return useQuery({
    queryKey: ['alpha-scripts-list'],
    queryFn: async () => {
      const { data } = await apiClient.get<string[]>('/research/scripts');
      return data;
    },
  });
};

export const useSaveAlphaScript = () => {
  return useMutation({
    mutationFn: async ({ name, content, activate }: { name: string; content: string; activate?: boolean }) => {
      const { data } = await apiClient.post('/research/scripts', { name, content, activate });
      return data;
    }
  });
};

export const useGoldDatasets = () => {
  return useQuery({
    queryKey: ['gold-datasets'],
    queryFn: async () => {
      const { data } = await apiClient.get<string[]>('/data/lake/gold');
      return data;
    },
  });
};

export const useImportData = () => {
  return useMutation({
    mutationFn: async ({ name, records }: { name: string; records: any[] }) => {
      const { data } = await apiClient.post(`/research/data/import?dataset_name=${name}`, { records });
      return data;
    }
  });
};

export const useGoldDatasetHead = (name: string) => {
  return useQuery({
    queryKey: ['gold-dataset-head', name],
    queryFn: async () => {
      const { data } = await apiClient.get(`/data/lake/gold/${name}/head`);
      return data;
    },
    enabled: !!name && name !== 'live_market_cache'
  });
};

export const useResearchTemplates = () => {
  return useQuery({
    queryKey: ['research-templates'],
    queryFn: async () => {
      const { data } = await apiClient.get('/research/templates');
      return data;
    },
  });
};

export interface NotebookCell {
  id: string;
  type: "code" | "markdown";
  content: string;
  output: Record<string, any>[];
}

export interface ResearchNotebookSummary {
  id: string;
  profile: string;
  name: string;
  description: string;
  cell_count: number;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface ResearchNotebookDetail extends ResearchNotebookSummary {
  cells: NotebookCell[];
}

export const useResearchNotebooks = (profile: string) => {
  return useQuery({
    queryKey: ['research-notebooks', profile],
    queryFn: async () => {
      const { data } = await apiClient.get<{ active_notebook_id: string | null; notebooks: ResearchNotebookSummary[] }>(`/research/notebooks?profile=${profile}`);
      return data;
    },
  });
};

export const useResearchNotebook = (profile: string, notebookId: string | null) => {
  return useQuery({
    queryKey: ['research-notebook', profile, notebookId],
    queryFn: async () => {
      const { data } = await apiClient.get<ResearchNotebookDetail>(`/research/notebooks/${notebookId}?profile=${profile}`);
      return data;
    },
    enabled: !!profile && !!notebookId,
  });
};

export const useCreateResearchNotebook = (profile: string) => {
  return useMutation({
    mutationFn: async (payload: { name: string; description?: string; cells?: NotebookCell[]; activate?: boolean }) => {
      const { data } = await apiClient.post(`/research/notebooks?profile=${profile}`, payload);
      return data;
    },
  });
};

export const useUpdateResearchNotebook = (profile: string) => {
  return useMutation({
    mutationFn: async ({ notebookId, payload }: { notebookId: string; payload: { name?: string; description?: string; cells?: NotebookCell[]; activate?: boolean } }) => {
      const { data } = await apiClient.put(`/research/notebooks/${notebookId}?profile=${profile}`, payload);
      return data;
    },
  });
};

export const useDuplicateResearchNotebook = (profile: string) => {
  return useMutation({
    mutationFn: async ({ notebookId, name }: { notebookId: string; name?: string }) => {
      const { data } = await apiClient.post(`/research/notebooks/${notebookId}/duplicate?profile=${profile}`, { name });
      return data;
    },
  });
};

export const useActivateResearchNotebook = (profile: string) => {
  return useMutation({
    mutationFn: async (notebookId: string) => {
      const { data } = await apiClient.post(`/research/notebooks/${notebookId}/activate?profile=${profile}`);
      return data;
    },
  });
};

export const useDeleteResearchNotebook = (profile: string) => {
  return useMutation({
    mutationFn: async (notebookId: string) => {
      const { data } = await apiClient.delete(`/research/notebooks/${notebookId}?profile=${profile}`);
      return data;
    },
  });
};


