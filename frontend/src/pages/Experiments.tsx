import { useState, useMemo, useEffect, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  useExperiments,
  useStrategies,
  useRunBacktest,
  useDeployModel,
  useTrainModel,
  useResearchTemplates,
  useGoldDatasets,
  useGoldDatasetHead,
  useResearchNotebooks,
  useResearchNotebook,
  useCreateResearchNotebook,
  useUpdateResearchNotebook,
  useDuplicateResearchNotebook,
  useActivateResearchNotebook,
  useDeleteResearchNotebook,
  type NotebookCell,
  type ResearchNotebookSummary
} from "@/api/queries";
import {
  Activity, PlayCircle, Loader2,
  Trophy, Rocket, Database, HelpCircle, Play, Cpu, LineChart, Terminal, Plus, Trash2, Eye, Layers, FileCode, FlaskConical, CheckCircle2, Settings2
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import EditorImport from "react-simple-code-editor";
import { codeCellMinHeightPx, highlightPythonCode } from "@/lib/notebookPython";

/** Vite ESM interop: package resolves to `{ default: Component }` instead of the component. */
const Editor =
  typeof EditorImport === "function"
    ? EditorImport
    : (EditorImport as { default: typeof EditorImport }).default;

const INITIAL_CELLS: NotebookCell[] = [
  {
    id: "cell-1",
    type: "code",
    content: "# STEP 1: DATA INGESTION\nimport pandas as pd\nfrom market.fetcher import MarketDataService\n\ntickers = ['AAPL', 'MSFT', 'BTC-USD']\nmkt = MarketDataService()\nprice_frames = {}\nfor ticker in tickers:\n    frame = mkt.get_historical(ticker, days=365)\n    if frame is not None and not frame.empty:\n        frame['Ticker'] = ticker\n        price_frames[ticker] = frame\n        print(f'Loaded {ticker}: {len(frame)} rows')\nif not price_frames:\n    idx = pd.date_range(end=pd.Timestamp.today(), periods=252, freq='B')\n    import numpy as np\n    base = np.linspace(0, 12, len(idx))\n    close = 100 + np.sin(base) * 5 + np.linspace(0, 3, len(idx))\n    open_ = close + np.cos(base) * 0.5\n    for ticker in tickers:\n        synthetic = pd.DataFrame({\n            'Open': open_,\n            'High': close + 1.5,\n            'Low': close - 1.5,\n            'Close': close,\n            'Volume': [1_000_000] * len(idx),\n        }, index=idx)\n        synthetic['Ticker'] = ticker\n        price_frames[ticker] = synthetic\n    print('✓ Using synthetic fallback market data')\nprint(f'✓ Ingested {len(price_frames)} assets')",
    output: []
  },
  {
    id: "cell-2",
    type: "code",
    content: "# STEP 2: QUANT FEATURES\nfrom market.fetcher import add_technical_indicators\n\nfeature_frames = {}\nfor ticker, frame in price_frames.items():\n    enriched = add_technical_indicators(frame)\n    enriched['factor_momentum'] = enriched['Close'].pct_change(10)\n    enriched['factor_volatility'] = enriched['Close'].pct_change().rolling(20).std()\n    enriched['target'] = (enriched['Close'].shift(-1) > enriched['Close']).astype(int)\n    feature_frames[ticker] = enriched.dropna()\nprint(f'✓ Built quant features for {len(feature_frames)} assets')",
    output: []
  },
  {
    id: "cell-3",
    type: "code",
    content: "# STEP 3: MODEL TRAINING\nimport pandas as pd\nimport mlflow.sklearn\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import accuracy_score\n\n# Flatten multi-ticker data\ndataset = pd.concat(feature_frames.values(), ignore_index=True)\nX = dataset[['factor_momentum', 'factor_volatility', 'RSI14', 'MACD']]\ny = dataset['target']\n\nmlflow.set_tracking_uri('sqlite:///data/mlflow.db')\nwith mlflow.start_run(run_name='Notebook_Alpha_Test'):\n    model = RandomForestClassifier(n_estimators=50, random_state=42)\n    model.fit(X, y)\n    predictions = model.predict(X)\n    print(f'Model Accuracy: {accuracy_score(y, predictions):.2%}')\n    mlflow.sklearn.log_model(model, name='alpha_model', registered_model_name='Notebook_Alpha')",
    output: []
  }
];

export function Experiments() {
  const profile = useStore((state) => state.profile);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Data Queries
  const { data: experiments, isLoading: experimentsLoading } = useExperiments();
  const { data: strategies } = useStrategies();
  const { data: templates } = useResearchTemplates();
  const { data: goldDatasets } = useGoldDatasets();
  const { data: notebookLibrary } = useResearchNotebooks(profile);

  // Mutations
  const runBacktest = useRunBacktest();
  const deployModel = useDeployModel();
  const trainModel = useTrainModel();
  const createNotebook = useCreateResearchNotebook(profile);
  const updateNotebook = useUpdateResearchNotebook(profile);
  const duplicateNotebook = useDuplicateResearchNotebook(profile);
  const activateNotebook = useActivateResearchNotebook(profile);
  const deleteNotebook = useDeleteResearchNotebook(profile);

  // Component State
  const [activeTab, setActiveTab] = useState<'train' | 'registry' | 'notebook'>('train');

  // ── Train tab state ──────────────────────────────────────────────────────────
  const [trainDataset, setTrainDataset] = useState<string>("live_sync");
  const [modelType, setModelType] = useState<"gradient_boosting" | "random_forest" | "logistic_regression">("gradient_boosting");
  const [nEstimators, setNEstimators] = useState(50);
  const [learningRate, setLearningRate] = useState(0.1);
  const [maxDepth, setMaxDepth] = useState(3);
  const [cReg, setCReg] = useState(1.0);
  const [maxIter, setMaxIter] = useState(100);
  const [trainResult, setTrainResult] = useState<{ run_id: string; accuracy: number; precision: number; model_class: string } | null>(null);

  const handleTrain = async () => {
    const hyperparams: Record<string, number | string> = {};
    if (modelType === "gradient_boosting") {
      hyperparams.n_estimators = nEstimators;
      hyperparams.learning_rate = learningRate;
      hyperparams.max_depth = maxDepth;
    } else if (modelType === "random_forest") {
      hyperparams.n_estimators = nEstimators;
      hyperparams.max_depth = maxDepth;
    } else {
      hyperparams.C = cReg;
      hyperparams.max_iter = maxIter;
    }
    try {
      const res = await trainModel.mutateAsync({
        profile,
        params: { dataset_name: trainDataset, model_type: modelType, ...hyperparams },
      });
      const result = res?.result ?? res;
      setTrainResult(result);
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
    } catch {
      alert("Entraînement échoué. Vérifiez les logs.");
    }
  };
  const [cells, setCells] = useState<NotebookCell[]>(INITIAL_CELLS);
  const [activeCellId, setActiveCellId] = useState<string | null>(null);
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  const [selectedNotebookId, setSelectedNotebookId] = useState<string | null>(null);
  const [notebookSessionId, setNotebookSessionId] = useState(() => `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [notebookName, setNotebookName] = useState("Untitled Notebook");
  const [notebookDescription, setNotebookDescription] = useState("");
  const [isNotebookDirty, setIsNotebookDirty] = useState(false);
  const [isSavingNotebook, setIsSavingNotebook] = useState(false);
  
  // Data Preview State
  const goldDatasetList = useMemo(() => Array.isArray(goldDatasets) ? goldDatasets : [], [goldDatasets]);
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const { data: dataPreview } = useGoldDatasetHead(selectedDataset ?? "");

  // Simulation Config
  const [selectedStrategy, setSelectedStrategy] = useState("predictive_ml");
  const [strategyParams, setStrategyParams] = useState<any>({});

  // Sync params
  useEffect(() => {
    const strat = (strategies as any[])?.find((s: any) => s.name === selectedStrategy);
    if (strat) {
      setStrategyParams({ ...strat.params });
    }
  }, [selectedStrategy, strategies]);

  const templateList = Array.isArray(templates) ? templates : [];
  const selectedTemplate = useMemo(
    () => templateList.find((template: any) => template.id === selectedTemplateId) ?? templateList[0] ?? null,
    [selectedTemplateId, templateList]
  );

  useEffect(() => {
    if (templateList.length === 0) {
      setSelectedTemplateId(null);
      return;
    }
    if (!selectedTemplateId || !templateList.some((template: any) => template.id === selectedTemplateId)) {
      setSelectedTemplateId(templateList[0].id);
    }
  }, [selectedTemplateId, templateList]);

  useEffect(() => {
    const activeId = notebookLibrary?.active_notebook_id ?? null;
    if (activeId && activeId !== selectedNotebookId) {
      setSelectedNotebookId(activeId);
    }
  }, [notebookLibrary?.active_notebook_id, selectedNotebookId]);

  const activeNotebook = useResearchNotebook(profile, selectedNotebookId);

  useEffect(() => {
    if (activeNotebook.data) {
      setNotebookName(activeNotebook.data.name);
      setNotebookDescription(activeNotebook.data.description || "");
      setCells(activeNotebook.data.cells?.length ? activeNotebook.data.cells : INITIAL_CELLS);
      setIsNotebookDirty(false);
    } else if (!selectedNotebookId) {
      setCells(INITIAL_CELLS);
      setNotebookName("Untitled Notebook");
      setNotebookDescription("");
      setIsNotebookDirty(false);
    }
  }, [activeNotebook.data, selectedNotebookId]);

  useEffect(() => {
    if (selectedNotebookId) {
      setNotebookSessionId(selectedNotebookId);
    }
  }, [selectedNotebookId]);

  useEffect(() => {
    if (!notebookLibrary?.notebooks?.length && !selectedNotebookId) {
      setCells(INITIAL_CELLS);
    }
  }, [notebookLibrary?.notebooks, selectedNotebookId]);

  useEffect(() => {
    if (goldDatasetList.length === 0) {
      setSelectedDataset(null);
      return;
    }

    if (selectedDataset === null) {
      setSelectedDataset(goldDatasetList[0]);
      return;
    }

    if (selectedDataset !== "" && !goldDatasetList.includes(selectedDataset)) {
      setSelectedDataset(goldDatasetList[0]);
    }
  }, [goldDatasetList, selectedDataset]);

  const handleRunExperiment = async () => {
    try {
      await runBacktest.mutateAsync({ 
        strategy: selectedStrategy, 
        days: 90, 
        profile,
        strategy_params: strategyParams
      });
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      setActiveTab('registry');
    } catch (e) {
      alert("Simulation failed.");
    }
  };

  const runFullNotebook = async () => {
    setIsRunningAll(true);
    try {
      await runNotebookCells(cells, cells.map((_, idx) => idx));
    } catch (e) {
      alert("Kernel Execution Error.");
    } finally {
      setIsRunningAll(false);
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
    }
  };

  const runSingleCell = async (cellIndex: number) => {
    if (!cells[cellIndex]) return;
    setIsRunningAll(true);
    try {
      await runNotebookCells([cells[cellIndex]], [cellIndex]);
    } finally {
      setIsRunningAll(false);
    }
  };

  const persistNotebook = async () => {
    setIsSavingNotebook(true);
    try {
      let notebookId = selectedNotebookId;
      if (selectedNotebookId) {
        await updateNotebook.mutateAsync({
          notebookId: selectedNotebookId,
          payload: {
            name: notebookName,
            description: notebookDescription,
            cells,
            activate: true,
          },
        });
      } else {
        const created = await createNotebook.mutateAsync({
          name: notebookName,
          description: notebookDescription,
          cells,
          activate: true,
        });
        notebookId = created.id;
        setSelectedNotebookId(created.id);
        setNotebookSessionId(created.id);
      }
      setIsNotebookDirty(false);
      await queryClient.invalidateQueries({ queryKey: ['research-notebooks', profile] });
      if (notebookId) {
        await queryClient.invalidateQueries({ queryKey: ['research-notebook', profile, notebookId] });
      }
    } catch (error) {
      alert("Notebook save failed.");
    } finally {
      setIsSavingNotebook(false);
    }
  };

  const handleSelectNotebook = async (notebook: ResearchNotebookSummary) => {
    if (isNotebookDirty && !confirm("Discard current notebook changes and switch?")) {
      return;
    }
    setSelectedNotebookId(notebook.id);
    setNotebookSessionId(notebook.id);
    setNotebookName(notebook.name);
    setNotebookDescription(notebook.description || "");
    setIsNotebookDirty(false);
    await activateNotebook.mutateAsync(notebook.id);
    await queryClient.invalidateQueries({ queryKey: ['research-notebooks', profile] });
  };

  const handleNewNotebook = () => {
    if (isNotebookDirty && !confirm("Discard current notebook changes and start a new notebook?")) {
      return;
    }
    setSelectedNotebookId(null);
    setNotebookSessionId(`draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    setNotebookName("Untitled Notebook");
    setNotebookDescription("");
    setCells(INITIAL_CELLS);
    setActiveCellId(null);
    setIsNotebookDirty(false);
  };

  const handleDuplicateNotebook = async () => {
    if (!selectedNotebookId) {
      alert("Save the notebook first so it can be duplicated.");
      return;
    }
    const nextName = window.prompt("Duplicate notebook name", `${notebookName} Copy`)?.trim();
    if (!nextName) return;
    const duplicated = await duplicateNotebook.mutateAsync({
      notebookId: selectedNotebookId,
      name: nextName,
    });
    setSelectedNotebookId(duplicated.id);
    setNotebookSessionId(duplicated.id);
    await queryClient.invalidateQueries({ queryKey: ['research-notebooks', profile] });
    await queryClient.invalidateQueries({ queryKey: ['research-notebook', profile, duplicated.id] });
  };

  const handleDeleteNotebook = async () => {
    if (!selectedNotebookId) {
      alert("There is no saved notebook to delete yet.");
      return;
    }
    if (!confirm(`Delete notebook "${notebookName}"? This cannot be undone.`)) {
      return;
    }
    await deleteNotebook.mutateAsync(selectedNotebookId);
    setSelectedNotebookId(null);
    setNotebookSessionId(`draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
    setNotebookName("Untitled Notebook");
    setNotebookDescription("");
    setCells(INITIAL_CELLS);
    setIsNotebookDirty(false);
    await queryClient.invalidateQueries({ queryKey: ['research-notebooks', profile] });
  };

  const templateCategory = (template: any) => {
    const text = `${template?.name ?? ""} ${template?.description ?? ""}`.toLowerCase();
    if (text.includes("regression") || text.includes("logistic")) return "Regression";
    if (text.includes("random forest") || text.includes("boost") || text.includes("gradient")) return "Ensemble";
    if (text.includes("svm")) return "Kernel";
    if (text.includes("classification")) return "Classification";
    return "Research";
  };

  const buildDatasetAwareIngestionCell = (template: any, datasetName: string | null) => {
    const datasetLiteral = JSON.stringify(datasetName);

    switch (template?.id) {
      case "random_forest":
      case "logistic":
      case "svm":
      case "gb":
        return `# STEP 1: DATA INGESTION
import pandas as pd
from market.fetcher import MarketDataService
from services.data_lake_service import DataLakeService

selected_gold_dataset = ${datasetLiteral}

tickers = ['AAPL', 'MSFT', 'BTC-USD']
mkt = MarketDataService()
lake = DataLakeService()
price_frames = {}

if selected_gold_dataset:
    gold_bundle = lake.load_gold(selected_gold_dataset)
    if gold_bundle:
        price_frames = gold_bundle
        for ticker, frame in price_frames.items():
            if frame is not None and not frame.empty:
                frame['Ticker'] = ticker
        print(f"✓ Loaded Gold dataset '{selected_gold_dataset}': {len(price_frames)} assets")

if not price_frames:
    for ticker in tickers:
        frame = mkt.get_historical(ticker, days=365)
        if frame is not None and not frame.empty:
            frame['Ticker'] = ticker
            price_frames[ticker] = frame
            print(f'Loaded {ticker}: {len(frame)} rows')
    if not price_frames:
        idx = pd.date_range(end=pd.Timestamp.today(), periods=252, freq='B')
        import numpy as np
        base = np.linspace(0, 12, len(idx))
        close = 100 + np.sin(base) * 5 + np.linspace(0, 3, len(idx))
        open_ = close + np.cos(base) * 0.5
        for ticker in tickers:
            synthetic = pd.DataFrame({
                'Open': open_,
                'High': close + 1.5,
                'Low': close - 1.5,
                'Close': close,
                'Volume': [1_000_000] * len(idx),
            }, index=idx)
            synthetic['Ticker'] = ticker
            price_frames[ticker] = synthetic
        print('✓ Using synthetic fallback market data')

print(f'✓ Ingested {len(price_frames)} assets')`;
      case "full_pipeline":
        return `# STEP 1: DATA INGESTION
import pandas as pd
from market.fetcher import MarketDataService
from services.data_lake_service import DataLakeService

selected_gold_dataset = ${datasetLiteral}

tickers = ['AAPL', 'MSFT', 'NVDA', 'BTC-USD']
mkt = MarketDataService()
lake = DataLakeService()
dfs = []

if selected_gold_dataset:
    gold_bundle = lake.load_gold(selected_gold_dataset)
    if gold_bundle:
        for ticker, frame in gold_bundle.items():
            if frame is None or frame.empty:
                continue
            frame = frame.copy()
            frame['Ticker'] = frame.get('Ticker', ticker)
            dfs.append(frame)
        print(f"✓ Loaded Gold dataset '{selected_gold_dataset}' into {len(dfs)} frames")

if not dfs:
    for ticker in tickers:
        frame = mkt.get_historical(ticker, days=500)
        if frame is not None and not frame.empty:
            frame['Ticker'] = ticker
            dfs.append(frame)
            print(f'✓ Ingested {ticker}')
    if not dfs:
        idx = pd.date_range(end=pd.Timestamp.today(), periods=500, freq='B')
        import numpy as np
        base = np.linspace(0, 20, len(idx))
        close = 100 + np.sin(base) * 8 + np.linspace(0, 4, len(idx))
        open_ = close + np.cos(base) * 0.75
        for ticker in tickers:
            synthetic = pd.DataFrame({
                'Open': open_,
                'High': close + 1.75,
                'Low': close - 1.75,
                'Close': close,
                'Volume': [2_000_000] * len(idx),
            }, index=idx)
            synthetic['Ticker'] = ticker
            dfs.append(synthetic)
        print('✓ Using synthetic fallback market data')

print(f'✓ Ingested {len(dfs)} assets')`;
      case "sentiment_xgb":
        return `# STEP 1: DATA INGESTION
import pandas as pd
from market.fetcher import MarketDataService
from services.data_lake_service import DataLakeService
from services.news_service import NewsSentimentService

selected_gold_dataset = ${datasetLiteral}

ticker = 'TSLA'
mkt = MarketDataService()
lake = DataLakeService()
news = NewsSentimentService()
df = None

if selected_gold_dataset:
    gold_bundle = lake.load_gold(selected_gold_dataset)
    if gold_bundle:
        ticker, df = next(iter(gold_bundle.items()))
        if df is not None and not df.empty:
            df = df.copy()
            df['Ticker'] = ticker
            print(f"✓ Loaded Gold dataset '{selected_gold_dataset}' using {ticker}: {len(df)} rows")
        else:
            df = None

if df is None or df.empty:
    df = mkt.get_historical(ticker, days=100)
    if df is None or df.empty:
        idx = pd.date_range(end=pd.Timestamp.today(), periods=100, freq='B')
        import numpy as np
        base = np.linspace(0, 8, len(idx))
        close = 200 + np.sin(base) * 7 + np.linspace(0, 2, len(idx))
        open_ = close + np.cos(base) * 0.5
        df = pd.DataFrame({
            'Open': open_,
            'High': close + 1.5,
            'Low': close - 1.5,
            'Close': close,
            'Volume': [1_500_000] * len(idx),
        }, index=idx)
        print('✓ Using synthetic fallback market data')
    print(f'✓ Ingested price data: {len(df)} rows')

sentiment_snapshot = news.get_ticker_sentiment(ticker)
print(f"✓ Ingested sentiment sample: score={sentiment_snapshot.get('score', 0.0)}")`;
      default:
        return String(template?.cells?.[0]?.content ?? template?.content ?? "");
    }
  };

  const buildNotebookCellsFromTemplate = (template: any, datasetName: string | null) => {
    const templateCells = Array.isArray(template?.cells) && template.cells.length > 0
      ? template.cells.map((cell: any, index: number) => ({
          id: cell.id || `cell-${Date.now()}-${index}`,
          type: cell.type || "code",
          content: String(cell.content ?? ""),
          output: [],
        }))
      : [];

    if (templateCells.length === 0) {
      return [
        {
          id: `cell-${Date.now()}-1`,
          type: "code",
          content: buildDatasetAwareIngestionCell(template, datasetName),
          output: [],
        },
      ];
    }

    return templateCells.map((cell: any, index: number) =>
      index === 0 && datasetName
        ? { ...cell, content: buildDatasetAwareIngestionCell(template, datasetName) }
        : cell
    );
  };

  const templatePreview = (template: any) => {
    const cells = buildNotebookCellsFromTemplate(template, selectedDataset);
    return cells
      .map((cell: any, index: number) => {
        const snippet = String(cell?.content ?? "")
          .split("\n")
          .slice(0, 4)
          .join("\n");
        return `# CELL ${index + 1}: ${String(cell?.type ?? "code").toUpperCase()}\n${snippet}`;
      })
      .join("\n\n");
  };

  const createNotebookFromTemplate = async (template: any) => {
    if (!template) return;
    const templateCells = buildNotebookCellsFromTemplate(template, selectedDataset);
    try {
      const created = await createNotebook.mutateAsync({
        name: `${template.name} Notebook`,
        description: template.description || "Created from a research template",
        cells: templateCells,
        activate: true,
      });
      setSelectedNotebookId(created.id);
      setNotebookSessionId(created.id);
      setNotebookName(created.name);
      setNotebookDescription(created.description || "");
      setCells(created.cells?.length ? created.cells : INITIAL_CELLS);
      setActiveCellId(null);
      setIsNotebookDirty(false);
      await queryClient.invalidateQueries({ queryKey: ['research-notebooks', profile] });
      await queryClient.invalidateQueries({ queryKey: ['research-notebook', profile, created.id] });
    } catch (error) {
      alert("Template notebook creation failed.");
    }
  };


  const addCell = (afterId: string) => {
    const idx = cells.findIndex(c => c.id === afterId);
    const newCell: NotebookCell = { id: `cell-${Date.now()}`, type: 'code', content: "", output: [] };
    const newCells = [...cells];
    newCells.splice(idx + 1, 0, newCell);
    setCells(newCells);
    setIsNotebookDirty(true);
  };

  const removeCell = (id: string) => {
    if (cells.length > 1) {
      setCells(cells.filter(c => c.id !== id));
      setIsNotebookDirty(true);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>, id: string) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const val = target.value.substring(0, start) + "    " + target.value.substring(end);
      setCells((prev) => prev.map((c) => (c.id === id ? { ...c, content: val } : c)));
      setIsNotebookDirty(true);
      setTimeout(() => {
        target.selectionStart = target.selectionEnd = start + 4;
      }, 0);
    }
  };

  const leaderboard = useMemo(() => {
    if (!experiments) return [];
    return [...experiments]
      .filter(e => e.status === 'FINISHED' && e.metrics?.sharpe)
      .sort((a, b) => (b.metrics.sharpe || 0) - (a.metrics.sharpe || 0))
      .slice(0, 3);
  }, [experiments]);

  const appendNotebookOutput = (cellIndex: number, message: Record<string, any>) => {
    setCells((prev) => {
      if (!Array.isArray(prev) || !prev[cellIndex]) return prev;
      const next = [...prev];
      next[cellIndex] = {
        ...next[cellIndex],
        output: [...(next[cellIndex].output || []), message],
      };
      return next;
    });
  };

  const runNotebookCells = async (executionCells: NotebookCell[], cellIndexMap: number[]) => {
    if (!executionCells.length) return;

    setCells((prev) =>
      prev.map((cell, idx) =>
        cellIndexMap.includes(idx) ? { ...cell, output: [] } : cell
      )
    );

    try {
      const response = await fetch(`/api/run/notebook`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-KEY': localStorage.getItem('prediction_wallet_api_key') || ''
        },
        body: JSON.stringify({
          notebook_id: notebookSessionId,
          notebook_cells: executionCells.map((cell) => ({
            id: cell.id,
            type: cell.type,
            content: cell.content,
            output: [],
          })),
          strategy_params: {
            kernel_id: notebookSessionId,
          },
        })
      });

      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const messages = chunk.split('\n\n').filter(m => m.trim());

        for (const msg of messages) {
          try {
            const parsed = JSON.parse(msg.replace(/^data: /, ''));
            if (typeof parsed.cell_index === 'number' && typeof parsed.line === 'string') {
              const targetIdx = cellIndexMap[parsed.cell_index] ?? parsed.cell_index;
              appendNotebookOutput(targetIdx, {
                line: parsed.line,
                kind: parsed.kind,
                execution_count: parsed.execution_count,
              });
            }
          } catch {
            const fallbackIdx = cellIndexMap[0] ?? 0;
            appendNotebookOutput(fallbackIdx, { line: msg });
          }
        }
      }
    } catch (e) {
      alert("Kernel Execution Error.");
    }
  };

  if (experimentsLoading) return (
    <div className="relative min-h-screen overflow-hidden bg-background flex items-center justify-center px-6">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.16),_transparent_36%),radial-gradient(circle_at_bottom_right,_rgba(34,197,94,0.12),_transparent_30%)]" />
      <Card className="relative w-full max-w-2xl border-border/50 bg-card/80 shadow-2xl backdrop-blur-xl rounded-[3rem]">
        <CardContent className="p-10 md:p-14 flex flex-col items-start gap-6">
          <div className="flex items-center gap-4">
            <div className="rounded-[1.5rem] border border-primary/20 bg-primary/10 p-4">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
            <div>
              <div className="text-[10px] font-black uppercase tracking-[0.35em] text-muted-foreground">Experiments</div>
              <div className="text-3xl md:text-4xl font-black tracking-tighter uppercase">Loading the workstation</div>
            </div>
          </div>
          <p className="max-w-xl text-sm md:text-base text-muted-foreground leading-relaxed">
            Fetching notebooks, templates, and dataset previews so the workspace can render with the latest registry state.
          </p>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary/40">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-gradient-to-r from-primary via-emerald-500 to-cyan-500" />
          </div>
        </CardContent>
      </Card>
    </div>
  );

  return (
    <div className="relative min-h-screen overflow-hidden text-foreground">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(16,185,129,0.10),_transparent_24%),linear-gradient(180deg,_rgba(15,23,42,0.02),_transparent_20%)]" />
      <div className="relative space-y-8 pb-24 px-2 md:px-4">
        <section className="overflow-hidden rounded-[3rem] border border-border/60 bg-card/75 shadow-[0_24px_100px_rgba(0,0,0,0.18)] backdrop-blur-2xl">
          <div className="p-6 md:p-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex items-start gap-5">
                <div className="rounded-[2rem] border border-primary/20 bg-primary/10 p-5 shadow-inner">
                  <Cpu className="h-11 w-11 text-primary" />
                </div>
                <div className="space-y-3">
                  <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-[10px] font-black uppercase tracking-[0.35em] text-emerald-600">
                    Live research workspace
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  </div>
                  <div>
                    <h2 className="text-4xl md:text-6xl font-black tracking-tighter uppercase italic leading-none">Quant Workstation</h2>
                    <p className="mt-3 max-w-2xl text-sm md:text-base text-muted-foreground leading-relaxed">
                      Review notebooks, compare model runs, and push the best configuration toward production without leaving the page.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 rounded-[1.75rem] border border-border/60 bg-background/60 p-2 shadow-inner">
                <button
                  onClick={() => setActiveTab('train')}
                  className={`flex items-center gap-3 rounded-2xl px-6 py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all ${
                    activeTab === 'train'
                      ? 'bg-primary text-white shadow-2xl shadow-primary/20'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                  }`}
                >
                  <Settings2 className="h-4 w-4" /> Entraîner
                </button>
                <button
                  onClick={() => setActiveTab('registry')}
                  className={`flex items-center gap-3 rounded-2xl px-6 py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all ${
                    activeTab === 'registry'
                      ? 'bg-background text-primary shadow-xl'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                  }`}
                >
                  <Layers className="h-4 w-4" /> Registre
                </button>
                <button
                  onClick={() => setActiveTab('notebook')}
                  className={`flex items-center gap-3 rounded-2xl px-6 py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all ${
                    activeTab === 'notebook'
                      ? 'bg-background text-primary shadow-xl'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                  }`}
                >
                  <Terminal className="h-4 w-4" /> Notebook
                </button>
              </div>
            </div>
          </div>
        </section>

        {activeTab === 'train' && (
          <div className="grid gap-8 md:grid-cols-2 items-start px-2">
            {/* Config panel */}
            <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/70 backdrop-blur-xl shadow-2xl">
              <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                  <Settings2 className="h-4 w-4" /> Configuration du modèle
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6 p-8">
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Dataset d'entraînement</label>
                  <select
                    value={trainDataset}
                    onChange={e => setTrainDataset(e.target.value)}
                    className="h-12 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-sm font-bold outline-none transition-all focus:border-primary"
                  >
                    <option value="live_sync">Live sync (Yahoo Finance)</option>
                    {goldDatasetList.filter(d => d !== "live_market_cache").map(ds => (
                      <option key={ds} value={ds}>{ds}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Type de modèle</label>
                  <div className="grid grid-cols-3 gap-2">
                    {([
                      { key: "gradient_boosting", label: "Gradient Boost" },
                      { key: "random_forest", label: "Random Forest" },
                      { key: "logistic_regression", label: "Logistic Reg." },
                    ] as const).map(({ key, label }) => (
                      <button
                        key={key}
                        onClick={() => setModelType(key)}
                        className={`rounded-2xl border-2 px-3 py-3 text-[10px] font-black uppercase tracking-[0.2em] transition-all ${
                          modelType === key
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border/50 bg-background text-muted-foreground hover:border-primary/30'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {(modelType === "gradient_boosting" || modelType === "random_forest") && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                        n_estimators <span className="text-primary">{nEstimators}</span>
                      </label>
                      <input
                        type="range" min={10} max={300} step={10}
                        value={nEstimators}
                        onChange={e => setNEstimators(Number(e.target.value))}
                        className="w-full accent-primary"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                        max_depth <span className="text-primary">{maxDepth}</span>
                      </label>
                      <input
                        type="range" min={1} max={10} step={1}
                        value={maxDepth}
                        onChange={e => setMaxDepth(Number(e.target.value))}
                        className="w-full accent-primary"
                      />
                    </div>
                    {modelType === "gradient_boosting" && (
                      <div className="col-span-2 space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                          learning_rate <span className="text-primary">{learningRate}</span>
                        </label>
                        <input
                          type="range" min={0.01} max={1.0} step={0.01}
                          value={learningRate}
                          onChange={e => setLearningRate(Number(e.target.value))}
                          className="w-full accent-primary"
                        />
                      </div>
                    )}
                  </div>
                )}

                {modelType === "logistic_regression" && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                        C (régularisation) <span className="text-primary">{cReg}</span>
                      </label>
                      <input
                        type="range" min={0.01} max={10} step={0.01}
                        value={cReg}
                        onChange={e => setCReg(Number(e.target.value))}
                        className="w-full accent-primary"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                        max_iter <span className="text-primary">{maxIter}</span>
                      </label>
                      <input
                        type="range" min={50} max={500} step={50}
                        value={maxIter}
                        onChange={e => setMaxIter(Number(e.target.value))}
                        className="w-full accent-primary"
                      />
                    </div>
                  </div>
                )}

                <Button
                  className="h-14 w-full rounded-[1.4rem] bg-primary font-black uppercase tracking-[0.22em] text-white shadow-2xl shadow-primary/30 transition-all hover:bg-primary/90 active:scale-95"
                  onClick={handleTrain}
                  disabled={trainModel.isPending}
                >
                  {trainModel.isPending ? (
                    <><Loader2 className="mr-3 h-5 w-5 animate-spin" /> Entraînement en cours…</>
                  ) : (
                    <><PlayCircle className="mr-3 h-5 w-5 fill-current" /> Lancer l'entraînement</>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Results panel */}
            {trainResult ? (
              <Card className="overflow-hidden rounded-[2.5rem] border-emerald-500/20 bg-card/70 backdrop-blur-xl shadow-2xl">
                <CardHeader className="border-b border-emerald-500/20 bg-emerald-500/5 px-8 py-6">
                  <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-emerald-600">
                    <CheckCircle2 className="h-4 w-4" /> Entraînement réussi
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-6 p-8">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-[1.5rem] border border-border/50 bg-background/70 p-5">
                      <div className="text-[9px] font-black uppercase tracking-[0.28em] text-muted-foreground">Accuracy</div>
                      <div className="mt-2 text-4xl font-black text-primary">{(trainResult.accuracy * 100).toFixed(1)}%</div>
                    </div>
                    <div className="rounded-[1.5rem] border border-border/50 bg-background/70 p-5">
                      <div className="text-[9px] font-black uppercase tracking-[0.28em] text-muted-foreground">Precision</div>
                      <div className="mt-2 text-4xl font-black text-foreground">{(trainResult.precision * 100).toFixed(1)}%</div>
                    </div>
                  </div>

                  <div className="rounded-[1.5rem] border border-border/50 bg-background/70 p-5 space-y-2">
                    <div className="text-[9px] font-black uppercase tracking-[0.28em] text-muted-foreground">Modèle</div>
                    <div className="text-sm font-bold text-foreground">{trainResult.model_class}</div>
                    <div className="text-[9px] font-mono text-muted-foreground/60 break-all">{trainResult.run_id}</div>
                  </div>

                  <Button
                    className="h-14 w-full rounded-[1.4rem] bg-emerald-600 font-black uppercase tracking-[0.22em] text-white shadow-2xl shadow-emerald-600/30 transition-all hover:bg-emerald-500 active:scale-95"
                    onClick={() => navigate(`/model-tests?run_id=${trainResult.run_id}`)}
                  >
                    <FlaskConical className="mr-3 h-5 w-5" /> Tester ce modèle →
                  </Button>

                  <Button
                    variant="outline"
                    className="h-11 w-full rounded-[1.2rem] border-2 border-border/60 text-[10px] font-black uppercase tracking-[0.22em]"
                    onClick={() => setActiveTab('registry')}
                  >
                    Voir le registre
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <Card className="flex min-h-[400px] items-center justify-center rounded-[2.5rem] border-dashed border-border/60 bg-card/40">
                <div className="max-w-xs px-8 py-10 text-center text-muted-foreground">
                  <Cpu className="mx-auto mb-4 h-12 w-12 opacity-20" />
                  <div className="text-base font-bold text-foreground">Aucun entraînement</div>
                  <p className="mt-2 text-sm leading-relaxed">
                    Configurez votre modèle à gauche et lancez l'entraînement pour voir les résultats ici.
                  </p>
                </div>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'notebook' && (
         <div className="grid gap-8 md:grid-cols-12 items-start px-2">
            {/* Context Sidebar */}
            <div className="md:col-span-3 space-y-6 sticky top-6">
               <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/70 backdrop-blur-xl shadow-2xl">
                  <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                     <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground"><Database className="h-4 w-4" /> Data Lake</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6 p-8">
                     <div className="space-y-3">
                        <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Select Dataset to Inspect</label>
                        <select 
                          className="h-11 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-xs font-black outline-none transition-all focus:border-primary"
                          value={selectedDataset ?? ""}
                          onChange={e => setSelectedDataset(e.target.value)}
                        >
                           <option value="">-- Choose Gold Pack --</option>
                           {goldDatasetList.map(ds => <option key={ds} value={ds}>{ds}</option>)}
                        </select>
                     </div>

                     <div className="flex items-center gap-2">
                       <Button
                         variant="outline"
                         className="h-11 rounded-[1.2rem] border-2 border-border/60 text-[10px] font-black uppercase tracking-[0.22em]"
                         onClick={() => setSelectedDataset("")}
                         disabled={!selectedDataset}
                       >
                         Clear
                       </Button>
                       <div className="flex-1 rounded-[1.2rem] border border-primary/20 bg-primary/5 px-4 py-3 text-[9px] font-black uppercase tracking-[0.28em] text-primary">
                         {selectedDataset ? `Ready to inject ${selectedDataset}` : "No dataset selected"}
                       </div>
                     </div>

                     {dataPreview ? (
                        <div className="space-y-3 rounded-2xl border border-white/5 bg-black/40 p-4 shadow-inner">
                           <div className="flex items-center justify-between">
                              <span className="text-[9px] font-black uppercase tracking-widest text-emerald-500">Preview: {dataPreview.ticker}</span>
                              <Eye className="h-3 w-3 text-white/20" />
                           </div>
                           <div className="overflow-x-auto">
                              <table className="w-full text-[9px] font-mono text-zinc-400">
                                 <thead>
                                    <tr className="border-b border-white/10">
                                       {Array.isArray(dataPreview.columns) ? dataPreview.columns.slice(0, 3).map((c: string) => <th key={c} className="pb-1 pr-3 text-left font-black uppercase tracking-widest text-zinc-500">{c}</th>) : null}
                                    </tr>
                                 </thead>
                                 <tbody>
                                    {Array.isArray(dataPreview.records) ? dataPreview.records.slice(0, 6).map((r: any, i: number) => (
                                       <tr key={i} className="border-b border-white/5">
                                          {Array.isArray(dataPreview.columns) ? dataPreview.columns.slice(0, 3).map((c: string) => <td key={c} className="py-1 pr-3">{typeof r[c] === 'number' ? r[c].toFixed(2) : String(r[c])}</td>) : null}
                                       </tr>
                                    )) : null}
                                 </tbody>
                              </table>
                           </div>
                        </div>
                     ) : (
                        <div className="rounded-2xl border border-dashed border-border/60 bg-background/60 px-5 py-6 text-xs leading-relaxed text-muted-foreground">
                          Select a gold dataset to preview the first rows directly inside the workspace.
                        </div>
                     )}
                  </CardContent>
               </Card>

               <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/70 shadow-2xl backdrop-blur-xl">
                  <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                     <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                        <Layers className="h-4 w-4" /> Notebook
                     </CardTitle>
                     <CardDescription className="pt-3 text-left text-[13px] leading-relaxed text-muted-foreground">
                        <span className="font-semibold text-foreground">{cells.length} cells</span>
                        {" · "}
                        {isNotebookDirty ? (
                          <span className="text-amber-600">Unsaved changes</span>
                        ) : (
                          <span className="text-emerald-600">All changes saved</span>
                        )}
                        {" · "}
                        {selectedNotebookId ? (
                          <span className="text-primary">In the list below</span>
                        ) : (
                          <span>Draft — save to add it to the list below</span>
                        )}
                     </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-5 p-8">
                     <div className="space-y-3">
                        <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Notebook Name</label>
                        <input
                          value={notebookName}
                          onChange={(e) => {
                            setNotebookName(e.target.value);
                            setIsNotebookDirty(true);
                          }}
                          className="h-12 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-sm font-black outline-none transition-all focus:border-primary"
                          placeholder="Untitled Notebook"
                        />
                     </div>
                     <div className="space-y-3">
                        <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Description</label>
                        <textarea
                          value={notebookDescription}
                          onChange={(e) => {
                            setNotebookDescription(e.target.value);
                            setIsNotebookDirty(true);
                          }}
                          className="min-h-24 w-full resize-none rounded-2xl border-2 border-border/50 bg-background px-4 py-3 text-sm outline-none transition-all focus:border-primary"
                          placeholder="What does this notebook do?"
                        />
                     </div>
                     <div className="grid grid-cols-1 gap-3">
                        <Button
                          className="h-14 rounded-[1.4rem] bg-primary font-black uppercase tracking-[0.22em] text-white transition-all hover:bg-primary/90"
                          onClick={persistNotebook}
                          disabled={isSavingNotebook || createNotebook.isPending || updateNotebook.isPending}
                        >
                          {selectedNotebookId ? "Save Notebook" : "Create Notebook"}
                        </Button>
                        <div className="grid grid-cols-2 gap-3">
                          <Button
                            variant="outline"
                            className="h-12 rounded-[1.2rem] border-dashed border-2 border-border/60 text-[11px] font-black uppercase tracking-[0.22em]"
                            onClick={handleNewNotebook}
                          >
                            New Draft
                          </Button>
                          <Button
                            variant="outline"
                            className="h-12 rounded-[1.2rem] border-2 border-border/60 text-[11px] font-black uppercase tracking-[0.22em]"
                            onClick={handleDuplicateNotebook}
                            disabled={!selectedNotebookId || duplicateNotebook.isPending}
                          >
                            Duplicate
                          </Button>
                        </div>
                        <Button
                          variant="ghost"
                          className="h-12 rounded-[1.2rem] border-2 border-transparent text-[11px] font-black uppercase tracking-[0.22em] text-destructive transition-all hover:border-destructive/20 hover:bg-destructive/5"
                          onClick={handleDeleteNotebook}
                          disabled={!selectedNotebookId || deleteNotebook.isPending}
                        >
                          Delete Notebook
                        </Button>
                     </div>
                     <div className="space-y-2">
                        <div className="flex items-center justify-between text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                          <span>Saved notebooks</span>
                          <span>{Array.isArray(notebookLibrary?.notebooks) ? notebookLibrary.notebooks.length : 0}</span>
                        </div>
                        <div className="max-h-72 space-y-2 overflow-y-auto pr-1">
                          {Array.isArray(notebookLibrary?.notebooks) && notebookLibrary.notebooks.length > 0 ? notebookLibrary.notebooks.map((notebook) => (
                            <button
                              key={notebook.id}
                              onClick={() => handleSelectNotebook(notebook)}
                              className={`w-full rounded-2xl border px-4 py-3 text-left transition-all ${
                                selectedNotebookId === notebook.id
                                  ? 'border-primary bg-primary/10 shadow-lg'
                                  : 'border-border/50 bg-background/60 hover:border-primary/20 hover:bg-primary/5'
                              }`}
                            >
                              <div className="flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="truncate text-xs font-black uppercase tracking-wide">{notebook.name}</div>
                                  <div className="mt-1 line-clamp-2 text-[9px] font-bold uppercase opacity-60">
                                    {notebook.description || "No description"}
                                  </div>
                                </div>
                                {notebook.is_active && (
                                  <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-[9px] font-black uppercase tracking-widest text-emerald-600">
                                    Active
                                  </span>
                                )}
                              </div>
                              <div className="mt-3 flex items-center justify-between text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground/70">
                                <span>{notebook.cell_count} cells</span>
                                <span>{new Date(notebook.updated_at).toLocaleDateString()}</span>
                              </div>
                            </button>
                          )) : (
                            <div className="rounded-2xl border border-dashed border-border/60 bg-background/60 px-5 py-6 text-xs font-semibold text-muted-foreground">
                              No saved notebooks yet. Create one from the current draft.
                            </div>
                          )}
                        </div>
                     </div>
                  </CardContent>
               </Card>

               <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/70 shadow-2xl backdrop-blur-xl">
                  <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                     <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                        <Play className="h-4 w-4" /> Lab Controls
                     </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6 p-8">
                     <Button 
                       className="h-16 w-full rounded-[1.5rem] bg-emerald-600 font-black tracking-[0.2em] text-white shadow-2xl shadow-emerald-600/30 transition-all hover:bg-emerald-500 active:scale-95" 
                       onClick={runFullNotebook} 
                       disabled={isRunningAll}
                     >
                        {isRunningAll ? <Loader2 className="h-6 w-6 animate-spin mr-3" /> : <PlayCircle className="h-6 w-6 fill-current mr-3" />} RUN NOTEBOOK
                     </Button>
                     
                     <div className="mx-4 h-[2px] rounded-full bg-border/30" />
                     <div className="rounded-[2rem] border border-primary/20 bg-primary/5 p-5">
                       <div className="flex items-center justify-between gap-3">
                         <div>
                           <div className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">Model Test Lab</div>
                           <div className="mt-2 text-sm font-semibold text-foreground">Dedicated page for train/test backtracking</div>
                         </div>
                         <Button
                           className="h-11 rounded-[1.2rem] bg-primary px-4 text-[10px] font-black uppercase tracking-[0.22em] text-white hover:bg-primary/90"
                           onClick={() => setActiveTab('registry')}
                           type="button"
                         >
                           Open Registry
                         </Button>
                       </div>
                       <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
                         The test workspace now lives on its own page, with a virtual $100k portfolio, ticker selection, and direct model backtests.
                       </p>
                       <Button
                         variant="outline"
                         className="mt-4 h-11 rounded-[1.2rem] border-2 border-border/60 px-4 text-[10px] font-black uppercase tracking-[0.22em]"
                         onClick={() => window.location.assign('/model-tests')}
                       >
                         Go to Model Test Lab
                       </Button>
                     </div>
                     
                     {selectedTemplate ? (
                       <div className="space-y-4 rounded-[2rem] border border-border/60 bg-background/60 p-5">
                         <div className="flex items-start justify-between gap-3">
                           <div className="min-w-0">
                             <div className="flex flex-wrap items-center gap-2">
                               <span className="rounded-full bg-primary/10 px-3 py-1 text-[9px] font-black uppercase tracking-[0.3em] text-primary">
                                 {templateCategory(selectedTemplate)}
                               </span>
                               <span className="rounded-full bg-secondary px-3 py-1 text-[9px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                                 Selected template
                               </span>
                             </div>
                             <div className="mt-3 truncate text-sm font-black uppercase tracking-wide text-foreground">
                               {selectedTemplate.name}
                             </div>
                             <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                               {selectedTemplate.description}
                             </p>
                             <p className="mt-2 text-[10px] font-black uppercase tracking-[0.25em] text-primary/80">
                               {selectedDataset ? `Step 1 will use ${selectedDataset}` : "Step 1 will use live market data"}
                             </p>
                             <div className="mt-3 flex flex-wrap gap-2">
                               {["Ingestion", "Quant Features", "Model Training"].map((label) => (
                                 <span key={label} className="rounded-full bg-muted px-3 py-1 text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">
                                   {label}
                                 </span>
                               ))}
                             </div>
                           </div>
                           <Button
                             className="h-11 rounded-[1.2rem] bg-primary px-4 text-[10px] font-black uppercase tracking-[0.22em] text-white hover:bg-primary/90"
                             onClick={() => createNotebookFromTemplate(selectedTemplate)}
                             disabled={createNotebook.isPending}
                           >
                             Create with Dataset
                           </Button>
                         </div>
                         <div className="rounded-[1.5rem] border border-white/5 bg-black/50 p-4">
                           <div className="mb-3 text-[9px] font-black uppercase tracking-[0.3em] text-muted-foreground">Code Preview</div>
                           <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-slate-300">
                             {templatePreview(selectedTemplate)}
                           </pre>
                         </div>
                       </div>
                     ) : (
                       <div className="rounded-2xl border border-dashed border-border/60 bg-background/60 px-5 py-6 text-xs font-semibold text-muted-foreground">
                         No notebook template selected.
                       </div>
                     )}

                     <div className="space-y-4">
                        <label className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground"><FileCode className="h-4 w-4" /> Available Templates</label>
                        <div className="grid grid-cols-1 gap-3">
                           {Array.isArray(templates) && templates.length > 0 ? templates.map((t: any) => (
                              <button
                                key={t.id}
                                onClick={() => setSelectedTemplateId(t.id)}
                                className={`group rounded-2xl border px-5 py-4 text-left transition-all ${
                                  selectedTemplate?.id === t.id
                                    ? 'border-primary bg-primary/10 shadow-lg'
                                    : 'border-transparent bg-secondary/20 hover:border-primary/20 hover:bg-primary/10'
                                }`}
                              >
                                 <div className="flex items-start justify-between gap-3">
                                   <div className="min-w-0">
                                     <div className="text-xs font-black text-foreground transition-colors group-hover:text-primary">{t.name}</div>
                                     <div className="mt-1 line-clamp-2 text-[9px] font-bold uppercase opacity-60">{t.description}</div>
                                   </div>
                                   <span className="rounded-full bg-background/80 px-2.5 py-1 text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">
                                     {templateCategory(t)}
                                   </span>
                                 </div>
                              </button>
                           )) : (
                              <div className="rounded-2xl border border-dashed border-border/60 bg-background/60 px-5 py-6 text-xs font-semibold text-muted-foreground">
                                No notebook templates loaded yet. Populate the research templates endpoint to unlock quick starts.
                              </div>
                           )}
                        </div>
                     </div>
                  </CardContent>
               </Card>

               <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/70 backdrop-blur-xl shadow-2xl">
                  <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                     <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground"><HelpCircle className="h-4 w-4" /> Pipeline SOP</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6 p-8">
                     <Button variant="ghost" className="h-14 w-full rounded-2xl border-2 border-transparent bg-card/20 text-[11px] font-black text-muted-foreground transition-all hover:border-primary/20 hover:text-primary" onClick={() => setShowTutorial(true)}>
                       <HelpCircle className="mr-3 h-5 w-5" /> Open SOP
                     </Button>
                  </CardContent>
               </Card>
            </div>

            {/* Notebook Interface — title, status, and actions live only in the Notebook card (left) */}
            <div className="md:col-span-9 space-y-8">
               <Card className="overflow-hidden rounded-[2.5rem] border-primary/20 bg-primary/5 shadow-2xl backdrop-blur-xl">
                  <CardContent className="flex flex-col gap-3 px-8 py-6 md:flex-row md:items-center md:justify-between">
                     <div>
                        <div className="text-[10px] font-black uppercase tracking-[0.35em] text-primary">Dataset-first notebook bootstrap</div>
                        <div className="mt-2 text-sm font-semibold text-foreground">
                          {selectedDataset
                            ? `The selected Gold dataset ${selectedDataset} will be injected into STEP 1 when you create a notebook from a template.`
                            : "Select a Gold dataset first, then create a template notebook to inject it into STEP 1."}
                        </div>
                     </div>
                     <div className="rounded-full border border-primary/20 bg-background/80 px-4 py-2 text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                        Template-ready
                     </div>
                  </CardContent>
               </Card>

               {cells.map((cell, idx) => (
                  <div key={cell.id} className="relative group/cell">
                     <div className="absolute -left-16 top-4 bottom-4 w-12 flex flex-col items-center gap-4 opacity-0 group-hover/cell:opacity-100 transition-all">
                        <button onClick={() => removeCell(cell.id)} className="p-2.5 rounded-xl text-red-500 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 shadow-xl backdrop-blur-md transition-all"><Trash2 className="h-5 w-5" /></button>
                        <button onClick={() => addCell(cell.id)} className="p-2.5 rounded-xl text-primary hover:bg-primary/10 border border-transparent hover:border-primary/20 shadow-xl backdrop-blur-md transition-all"><Plus className="h-5 w-5" /></button>
                     </div>

                     <Card className={`overflow-hidden rounded-[3rem] border-2 shadow-2xl transition-all duration-300 ${activeCellId === cell.id ? 'border-primary ring-4 ring-primary/5' : 'border-border/50'}`} onFocus={() => setActiveCellId(cell.id)}>
                        <div className="flex items-center justify-between border-b bg-secondary/10 px-10 py-5 font-mono">
                           <div className="flex items-center gap-5">
                              <span className="rounded-xl border border-primary/20 bg-primary/20 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-primary">Cell [{idx + 1}]</span>
                              <div className="h-8 w-[1px] bg-border/50" />
                              <span className="text-[10px] font-black uppercase tracking-widest text-muted-foreground/70">Quant Kernel v1.0</span>
                           </div>
                           <div className="flex items-center gap-3">
                              <button
                                className="rounded-lg p-2 text-emerald-500 transition-all hover:bg-emerald-500/10"
                                onClick={() => runSingleCell(idx)}
                                disabled={isRunningAll}
                              >
                                <PlayCircle className="h-5 w-5" />
                              </button>
                           </div>
                        </div>
                        <CardContent className="bg-[#080808] p-0">
                           <Editor
                              value={cell.content}
                              onValueChange={(code) =>
                                {
                                  setIsNotebookDirty(true);
                                  setCells((prev) =>
                                  prev.map((c) => (c.id === cell.id ? { ...c, content: code } : c))
                                  );
                                }
                              }
                              onKeyDown={(e) =>
                                handleKeyDown(e as KeyboardEvent<HTMLTextAreaElement>, cell.id)
                              }
                              highlight={highlightPythonCode}
                              padding={48}
                              tabSize={4}
                              className="notebook-python-editor w-full"
                              preClassName="!m-0 !bg-transparent font-mono text-[16px] leading-relaxed"
                              textareaClassName="!outline-none selection:bg-primary/20 caret-sky-400"
                              style={{
                                fontFamily: '"Fira Code", "JetBrains Mono", monospace',
                                fontSize: 16,
                                lineHeight: 1.625,
                                minHeight: codeCellMinHeightPx(cell.content),
                              }}
                           />
                        </CardContent>
                        
                        {cell.output.length > 0 && (
                           <div className="border-t-2 border-white/5 bg-black p-10 font-mono text-[13px] leading-relaxed shadow-inner">
                              <div className="mb-4 flex items-center gap-3 text-[10px] font-black uppercase tracking-widest text-emerald-500/40">
                                 <Terminal className="h-4 w-4" /> Stream Output
                              </div>
                              <div className="space-y-1">
                                 {cell.output.map((o, i) => (
                                    <div key={i} className={
                                      o.kind === 'stderr' || o.line?.includes('ERROR') || o.line?.includes('Traceback') ? 'text-red-400 bg-red-500/5 px-2 rounded border-l-2 border-red-500 my-1' : 
                                      o.kind === 'cell_start' || o.line?.startsWith('---') ? 'text-blue-400 font-black mt-4' :
                                      o.kind === 'cell_end' || o.line?.startsWith('✓') ? 'text-emerald-400 font-bold' :
                                      'text-zinc-500'
                                    }>
                                       {o.line}
                                    </div>
                                 ))}
                              </div>
                           </div>
                        )}
                     </Card>
                  </div>
               ))}
               
               <div className="flex justify-center pt-8">
                  <Button 
                    variant="outline" 
                    className="h-20 rounded-[2rem] border-4 border-dashed border-border/50 px-16 text-xs font-black uppercase tracking-[0.3em] transition-all hover:border-primary/50 hover:bg-primary/5 hover:scale-105 active:scale-95" 
                    onClick={() => addCell(cells[cells.length - 1].id)}
                  >
                     <Plus className="h-6 w-6 mr-4 text-primary" /> APPEND RESEARCH CELL
                  </Button>
               </div>
            </div>
         </div>
        )}

        {activeTab === 'registry' && (
         <div className="grid gap-10 px-4 md:grid-cols-4 items-start">
           <div className="md:col-span-1 space-y-6">
             <Card className="overflow-hidden rounded-[3rem] border-2 border-primary/20 bg-card/75 shadow-2xl backdrop-blur-xl">
               <CardHeader className="border-b-2 border-primary/10 bg-primary/5 px-10 py-8">
                  <CardTitle className="flex items-center gap-4 text-lg font-black uppercase tracking-tighter text-primary"><LineChart className="h-6 w-6" /> Backtest Lab</CardTitle>
               </CardHeader>
               <CardContent className="space-y-10 px-10 pb-12 pt-10 font-medium">
                 <div className="space-y-4">
                    <label className="ml-1 text-[11px] font-black uppercase tracking-widest text-muted-foreground">Target Architecture</label>
                    <select 
                      className="h-14 w-full cursor-pointer appearance-none rounded-2xl border-2 border-border/50 bg-background px-6 text-sm font-black capitalize outline-none transition-all focus:ring-4 focus:ring-primary/10" 
                      value={selectedStrategy} 
                      onChange={(e) => setSelectedStrategy(e.target.value)}
                    >
                      {Array.isArray(strategies) ? strategies.map((s: any) => (<option key={s.name} value={s.name}>{s.name}</option>)) : null}
                    </select>
                 </div>
                 <Button className="h-16 w-full rounded-[1.5rem] bg-primary text-sm font-black tracking-[0.3em] text-white shadow-2xl shadow-primary/40 transition-all hover:bg-primary/90 hover:scale-105 active:scale-95" onClick={handleRunExperiment} disabled={runBacktest.isPending}>
                    {runBacktest.isPending ? <Loader2 className="h-6 w-6 animate-spin mr-3" /> : <PlayCircle className="h-6 w-6 mr-3 fill-current" />} LAUNCH TEST
                 </Button>
               </CardContent>
             </Card>
           </div>
           
          <div className="md:col-span-3 space-y-10">
             <div className="grid gap-4 md:grid-cols-3">
               {leaderboard.length > 0 ? leaderboard.map((run, i) => (
                 <Card key={run.run_id} className={`group relative overflow-hidden rounded-[3rem] border-2 bg-card transition-all ${i === 0 ? 'z-10 border-yellow-500 shadow-[0_0_50px_rgba(234,179,8,0.15)]' : 'border-border/50 shadow-xl hover:-translate-y-1'}`}>
                     <CardContent className="px-10 pb-10 pt-12">
                        <div className="mb-8 flex items-center justify-between">
                           <div className={`rounded-[1.5rem] p-4 ${i === 0 ? 'bg-yellow-500 text-white shadow-xl shadow-yellow-500/20' : 'bg-secondary text-muted-foreground shadow-inner'}`}>
                              <Trophy className="h-6 w-6" />
                           </div>
                           <div className="text-right text-xs font-black uppercase tracking-widest text-primary">Rank #{i+1}</div>
                        </div>
                        <div className="mb-2 truncate text-xl font-black uppercase tracking-tighter text-foreground">{run.name}</div>
                        <div className="mb-10 text-[11px] font-bold uppercase tracking-[0.3em] text-muted-foreground/50">{run.params?.strategy_type || "QUANT-ML"}</div>
                        <div className="flex items-center justify-between border-t-2 border-border/30 pt-10">
                           <div>
                              <div className="text-4xl font-black tracking-tighter text-primary">{run.metrics?.sharpe?.toFixed(2)}</div>
                              <div className="mt-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground">Sharpe</div>
                           </div>
                           <div className="text-right">
                              <div className={`text-2xl font-black ${run.metrics?.ann_ret > 0 ? 'text-emerald-500' : 'text-destructive'}`}>{(run.metrics?.ann_ret * 100)?.toFixed(1)}%</div>
                              <div className="mt-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground">Return</div>
                           </div>
                        </div>
                     </CardContent>
                     {i === 0 && <div className="absolute right-0 top-0 rounded-bl-[2rem] bg-yellow-500 px-8 py-2 text-[10px] font-black tracking-[0.4em] text-white shadow-2xl">CHAMPION</div>}
                 </Card>
               )) : (
                 <Card className="rounded-[3rem] border border-dashed border-border/60 bg-card/70 shadow-xl">
                   <CardContent className="flex flex-col items-center justify-center gap-4 px-10 py-16 text-center">
                     <Activity className="h-10 w-10 text-muted-foreground/40" />
                     <div className="text-2xl font-black tracking-tighter uppercase">No runs to show yet</div>
                     <div className="max-w-md text-sm leading-relaxed text-muted-foreground">
                       Launch a backtest to populate the registry leaderboard and compare the latest experiment outputs.
                     </div>
                   </CardContent>
                 </Card>
               )}
             </div>
             
             <Card className="overflow-hidden rounded-[3.5rem] border border-border/60 bg-card/70 shadow-2xl backdrop-blur-xl">
                <CardHeader className="flex flex-row items-center justify-between border-b border-border/30 bg-secondary/10 px-10 py-8 md:px-14 md:py-10">
                   <div>
                      <CardTitle className="flex items-center gap-4 text-2xl md:text-3xl font-black uppercase tracking-tighter text-foreground">
                         <Activity className="h-8 w-8 text-primary" /> Model Registry
                      </CardTitle>
                      <CardDescription className="mt-3 text-[11px] font-bold uppercase tracking-[0.3em] opacity-50">Comprehensive audit of training runs and live deployments.</CardDescription>
                   </div>
                   <div className="flex items-center gap-4 rounded-2xl border-2 border-border bg-background px-6 py-3 shadow-2xl">
                     <div className="h-3 w-3 animate-pulse rounded-full bg-emerald-500" />
                     <span className="font-mono text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">Sync: ACTIVE</span>
                   </div>
                </CardHeader>
                <CardContent className="p-0">
                   <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                         <thead className="bg-secondary/30 border-b-2 border-border/50 text-[10px] uppercase font-black tracking-[0.2em] text-muted-foreground">
                            <tr><th className="py-8 px-14 text-left">Identifier / Architecture</th><th className="py-8 px-4 text-center">Status</th><th className="py-8 px-4 text-center">Score Card</th><th className="py-8 px-14 text-right">Workflow</th></tr>
                         </thead>
                         <tbody className="divide-y divide-border/30">
                            {Array.isArray(experiments) && experiments.length > 0 ? experiments
                              .filter((run: any) => run.params?.strategy_type === "predictive_ml" || run.metrics?.accuracy !== undefined)
                              .map((run: any) => {
                               const isTrainingRun = run.metrics?.accuracy !== undefined;
                               return (
                                 <tr key={run.run_id} className="hover:bg-primary/5 transition-colors group">
                                    <td className="py-8 px-10">
                                       <div className="font-black group-hover:text-primary transition-colors uppercase text-base tracking-tight">{run.name}</div>
                                       <div className="text-[11px] text-muted-foreground font-mono mt-2 font-bold flex items-center gap-3 flex-wrap">
                                          <span className="bg-primary/10 text-primary px-3 py-1 rounded-xl border border-primary/20 text-[9px] tracking-widest">{run.params?.model_type || run.params?.model_class || "ML"}</span>
                                          <span className="opacity-30 font-normal">{run.run_id.slice(0, 12)}</span>
                                          {run.params?.features && <span className="opacity-40 text-[9px]">{run.params.features}</span>}
                                       </div>
                                    </td>
                                    <td className="py-8 px-4 text-center">
                                       <span className={`text-[10px] px-4 py-2 rounded-2xl font-black uppercase tracking-widest border ${run.status === 'FINISHED' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-red-500/10 text-red-500 border-red-500/20'}`}>{run.status}</span>
                                    </td>
                                    <td className="py-8 px-4">
                                       <div className="flex justify-center gap-8">
                                          {isTrainingRun && (
                                             <>
                                             <div className="text-center">
                                                <div className="text-xl font-black text-blue-500 tracking-tighter">{(run.metrics?.accuracy * 100)?.toFixed(1)}%</div>
                                                <div className="text-[9px] uppercase font-black tracking-widest opacity-40 mt-1">Accuracy</div>
                                             </div>
                                             <div className="text-center">
                                                <div className="text-xl font-black text-foreground tracking-tighter">{run.metrics?.precision !== undefined ? (run.metrics.precision * 100).toFixed(1) + '%' : '—'}</div>
                                                <div className="text-[9px] uppercase font-black tracking-widest opacity-40 mt-1">Precision</div>
                                             </div>
                                             </>
                                          )}
                                          {!isTrainingRun && (
                                             <div className="text-center">
                                                <div className="text-xl font-black text-foreground tracking-tighter">{run.metrics?.sharpe?.toFixed(2) || "—"}</div>
                                                <div className="text-[9px] uppercase font-black tracking-widest opacity-40 mt-1">Sharpe</div>
                                             </div>
                                          )}
                                       </div>
                                    </td>
                                    <td className="py-8 px-8 text-right">
                                       <div className="flex items-center justify-end gap-3">
                                         {isTrainingRun && (
                                           <Button
                                             variant="outline"
                                             className="h-10 text-[10px] px-5 font-black uppercase tracking-[0.2em] rounded-[1.1rem] border-2 border-border/60 hover:border-primary/30"
                                             onClick={() => navigate(`/model-tests?run_id=${run.run_id}`)}
                                           >
                                             <FlaskConical className="mr-2 h-3.5 w-3.5" /> Tester
                                           </Button>
                                         )}
                                         <Button
                                           className="h-10 text-[10px] px-5 font-black uppercase tracking-[0.2em] shadow-xl bg-emerald-600 hover:bg-emerald-500 text-white rounded-[1.1rem] flex items-center gap-2 transition-all hover:scale-105 active:scale-95"
                                           onClick={() => {if(confirm(`Promouvoir ce modèle en production ?`)) {deployModel.mutate(run.run_id, {onSuccess: (data) => alert(data.message)});}}}
                                           disabled={deployModel.isPending}
                                         >
                                           {deployModel.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Rocket className="h-3.5 w-3.5" />}
                                           {isTrainingRun ? "Déployer" : "Params"}
                                         </Button>
                                       </div>
                                    </td>
                                 </tr>
                               );
                            }) : (
                              <tr>
                                <td colSpan={4} className="px-14 py-16">
                                  <div className="flex flex-col items-center justify-center gap-4 rounded-[2rem] border border-dashed border-border/60 bg-background/60 px-8 py-14 text-center">
                                    <Activity className="h-10 w-10 text-muted-foreground/40" />
                                    <div className="text-2xl font-black tracking-tighter uppercase">Registry is empty</div>
                                    <div className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                                      Once backtests are available, they will appear here with status, architecture, score card, and deployment actions.
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                         </tbody>
                      </table>
                   </div>
                </CardContent>
             </Card>
          </div>
        </div>
      )}

      {/* Tutorial SOP */}
      {showTutorial && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/98 p-12 backdrop-blur-3xl">
           <Card className="max-w-4xl overflow-hidden rounded-[3.5rem] border-primary/20 bg-card text-foreground shadow-2xl">
              <div className="h-4 bg-gradient-to-r from-primary via-emerald-500 to-blue-500" />
              <CardHeader className="border-b border-white/5 bg-primary/5 px-16 py-14">
                 <CardTitle className="text-6xl font-black italic tracking-tighter uppercase text-primary">Protocol.Alpha</CardTitle>
                 <CardDescription className="text-xs font-black uppercase tracking-[0.4em] mt-4 opacity-70">Research Pipeline Specification</CardDescription>
              </CardHeader>
              <CardContent className="max-h-[60vh] space-y-16 overflow-y-auto p-16 custom-scrollbar">
                 <section className="space-y-8">
                    <h3 className="text-2xl font-black uppercase border-l-8 border-primary pl-8 text-foreground tracking-tighter">Modular Execution</h3>
                    <p className="font-bold text-muted-foreground text-xl leading-relaxed">Break your logic into semantic cells. The workstation concatenates them into a unified runtime. Always end with <code>mlflow.log_model</code> to enable one-click activation.</p>
                 </section>
                 <Button className="w-full bg-primary h-24 text-white font-black tracking-[0.5em] rounded-[2rem] text-2xl shadow-2xl shadow-primary/40 hover:scale-105 transition-all" onClick={() => setShowTutorial(false)}>INITIALIZE WORKSPACE</Button>
              </CardContent>
           </Card>
        </div>
      )}
      </div>
    </div>
  );
}
