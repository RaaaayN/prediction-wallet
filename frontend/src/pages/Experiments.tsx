import { useState, useMemo, useEffect, type KeyboardEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  useExperiments, 
  useStrategies, 
  useRunBacktest, 
  useDeployModel, 
  useResearchTemplates,
  useGoldDatasets,
  useGoldDatasetHead
} from "@/api/queries";
import {
  Activity, PlayCircle, Loader2,
  Trophy, Rocket, Database, HelpCircle, Play, Cpu, LineChart, Terminal, Plus, Trash2, Eye, Layers, FileCode
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

interface LogLine {
  line?: string;
  exit?: number;
}

interface NotebookCell {
  id: string;
  type: 'code' | 'markdown';
  content: string;
  output: LogLine[];
}

const INITIAL_CELLS: NotebookCell[] = [
  {
    id: "cell-1",
    type: "code",
    content: "# STEP 1: DATA INGESTION\nimport pandas as pd\nfrom market.fetcher import MarketDataService\n\ntickers = ['AAPL', 'MSFT', 'BTC-USD']\nmkt = MarketDataService()\nprint(f'Loading data for {tickers}...')\n\ndata = {t: mkt.get_historical(t, days=365) for t in tickers}\nprint('✓ Dataset Ready.')",
    output: []
  },
  {
    id: "cell-2",
    type: "code",
    content: "# STEP 2: QUANT FEATURES\nfrom market.fetcher import add_technical_indicators\n\nfor t, df in data.items():\n    df = add_technical_indicators(df)\n    # Logic: 1-day prediction target\n    df['Target'] = (df['Close'].shift(-1) > df['Close']).astype(int)\n    data[t] = df.dropna()\nprint(f'✓ Feature Engineering Complete for {len(data)} assets.')",
    output: []
  },
  {
    id: "cell-3",
    type: "code",
    content: "# STEP 3: MODEL TRAINING\nimport mlflow.sklearn\nfrom sklearn.ensemble import RandomForestClassifier\n\n# Flatten multi-ticker data\ndataset = pd.concat(data.values())\nX = dataset[['SMA20', 'RSI14', 'MACD']]\ny = dataset['Target']\n\nmlflow.set_tracking_uri('sqlite:///data/mlflow.db')\nwith mlflow.start_run(run_name='Notebook_Alpha_Test'):\n    model = RandomForestClassifier(n_estimators=50).fit(X, y)\n    print(f'Model Accuracy: {model.score(X, y):.2%}')\n    mlflow.sklearn.log_model(model, 'alpha_model', registered_model_name='Notebook_Alpha')",
    output: []
  }
];

export function Experiments() {
  const profile = useStore((state) => state.profile);
  const queryClient = useQueryClient();
  
  // Data Queries
  const { data: experiments, isLoading: experimentsLoading } = useExperiments();
  const { data: strategies } = useStrategies();
  const { data: templates } = useResearchTemplates();
  const { data: goldDatasets } = useGoldDatasets();

  // Mutations
  const runBacktest = useRunBacktest();
  const deployModel = useDeployModel();

  // Component State
  const [activeTab, setActiveTab] = useState<'pipeline' | 'registry'>('pipeline');
  const [cells, setCells] = useState<NotebookCell[]>(INITIAL_CELLS);
  const [activeCellId, setActiveCellId] = useState<string | null>(null);
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [showTutorial, setShowTutorial] = useState(false);
  
  // Data Preview State
  const [previewDataset, setPreviewDataset] = useState<string>("");
  const { data: dataPreview } = useGoldDatasetHead(previewDataset);

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
    const fullCode = cells.map(c => c.content).join("\n\n");
    setIsRunningAll(true);
    setCells(prev => prev.map(c => ({ ...c, output: [] })));
    
    try {
      const response = await fetch(`/api/run/notebook`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-KEY': localStorage.getItem('prediction_wallet_api_key') || ''
        },
        body: JSON.stringify({ strategy_params: { code: fullCode } })
      });

      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const messages = chunk.split('\n\n').filter(m => m.trim());
        const parsed = messages.map(msg => {
          try { return JSON.parse(msg.replace(/^data: /, '')); } catch { return { line: msg }; }
        });
        
        setCells(prev => {
          const newCells = [...prev];
          // For now, append all logs to the active cell or first cell
          const targetIdx = activeCellId ? newCells.findIndex(c => c.id === activeCellId) : 0;
          newCells[targetIdx].output = [...newCells[targetIdx].output, ...parsed];
          return newCells;
        });
      }
    } catch (e) {
      alert("Kernel Execution Error.");
    } finally {
      setIsRunningAll(false);
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
    }
  };

  const loadTemplate = (content: string) => {
    if(confirm("Replace notebook with template?")) {
      setCells([{ id: `cell-${Date.now()}`, type: 'code', content, output: [] }]);
    }
  };

  const addCell = (afterId: string) => {
    const idx = cells.findIndex(c => c.id === afterId);
    const newCell: NotebookCell = { id: `cell-${Date.now()}`, type: 'code', content: "", output: [] };
    const newCells = [...cells];
    newCells.splice(idx + 1, 0, newCell);
    setCells(newCells);
  };

  const removeCell = (id: string) => {
    if (cells.length > 1) setCells(cells.filter(c => c.id !== id));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>, id: string) => {
    if (e.key === "Tab") {
      e.preventDefault();
      const target = e.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const val = target.value.substring(0, start) + "    " + target.value.substring(end);
      setCells((prev) => prev.map((c) => (c.id === id ? { ...c, content: val } : c)));
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

  const totalExperiments = Array.isArray(experiments) ? experiments.length : 0;
  const finishedExperiments = Array.isArray(experiments)
    ? experiments.filter((run: any) => run.status === 'FINISHED').length
    : 0;
  const templateCount = Array.isArray(templates) ? templates.length : 0;
  const datasetCount = Array.isArray(goldDatasets) ? goldDatasets.length : 0;
  const topSharpe = leaderboard[0]?.metrics?.sharpe ?? null;
  const averageSharpe = leaderboard.length
    ? leaderboard.reduce((sum, run) => sum + (run.metrics?.sharpe || 0), 0) / leaderboard.length
    : null;

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
            Fetching runs, templates, and dataset previews so the workspace can render with the latest registry state.
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
                  onClick={() => setActiveTab('pipeline')}
                  className={`flex items-center gap-3 rounded-2xl px-6 py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all ${
                    activeTab === 'pipeline'
                      ? 'bg-primary text-white shadow-2xl shadow-primary/20'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                  }`}
                >
                  <Terminal className="h-4 w-4" /> Notebook
                </button>
                <button
                  onClick={() => setActiveTab('registry')}
                  className={`flex items-center gap-3 rounded-2xl px-6 py-4 text-[11px] font-black uppercase tracking-[0.3em] transition-all ${
                    activeTab === 'registry'
                      ? 'bg-background text-primary shadow-xl'
                      : 'text-muted-foreground hover:text-foreground hover:bg-secondary/40'
                  }`}
                >
                  <Layers className="h-4 w-4" /> Registry
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {[
                { label: 'Experiments', value: String(totalExperiments), hint: `${finishedExperiments} finished runs` },
                { label: 'Top Sharpe', value: topSharpe !== null ? topSharpe.toFixed(2) : '—', hint: averageSharpe !== null ? `Avg of top runs: ${averageSharpe.toFixed(2)}` : 'Best finished run' },
                { label: 'Templates', value: String(templateCount), hint: 'Notebook blueprints' },
                { label: 'Gold datasets', value: String(datasetCount), hint: 'Previewable packs' },
              ].map((item) => (
                <div key={item.label} className="rounded-[2rem] border border-border/60 bg-background/70 px-5 py-4 shadow-lg">
                  <div className="text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">{item.label}</div>
                  <div className="mt-3 text-3xl font-black tracking-tighter">{item.value}</div>
                  <div className="mt-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/80">{item.hint}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {activeTab === 'pipeline' ? (
         <div className="grid gap-8 md:grid-cols-12 items-start px-2">
            {/* Context Sidebar */}
            <div className="md:col-span-3 space-y-6 sticky top-6">
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
                     
                     <div className="space-y-4">
                        <label className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground"><FileCode className="h-4 w-4" /> Logic Blueprints</label>
                        <div className="grid grid-cols-1 gap-3">
                           {Array.isArray(templates) && templates.length > 0 ? templates.map((t: any) => (
                              <button
                                key={t.id}
                                onClick={() => loadTemplate(t.content)}
                                className="group rounded-2xl border border-transparent bg-secondary/20 px-5 py-4 text-left transition-all hover:border-primary/20 hover:bg-primary/10"
                              >
                                 <div className="text-xs font-black text-foreground transition-colors group-hover:text-primary">{t.name}</div>
                                 <div className="mt-1 line-clamp-2 text-[9px] font-bold uppercase opacity-60">{t.description}</div>
                              </button>
                           )) : (
                              <div className="rounded-2xl border border-dashed border-border/60 bg-background/60 px-5 py-6 text-xs font-semibold text-muted-foreground">
                                No template loaded yet. Populate the research templates endpoint to unlock quick starts.
                              </div>
                           )}
                        </div>
                     </div>
                  </CardContent>
               </Card>

               <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/70 backdrop-blur-xl shadow-2xl">
                  <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                     <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground"><Database className="h-4 w-4" /> Data Lake</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6 p-8">
                     <div className="space-y-3">
                        <label className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Select Dataset to Inspect</label>
                        <select 
                          className="h-11 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-xs font-black outline-none transition-all focus:border-primary"
                          value={previewDataset}
                          onChange={e => setPreviewDataset(e.target.value)}
                        >
                           <option value="">-- Choose Gold Pack --</option>
                           {Array.isArray(goldDatasets) ? goldDatasets.map(ds => <option key={ds} value={ds}>{ds}</option>) : null}
                        </select>
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

                     <Button variant="ghost" className="h-14 w-full rounded-2xl border-2 border-transparent bg-card/20 text-[11px] font-black text-muted-foreground transition-all hover:border-primary/20 hover:text-primary" onClick={() => setShowTutorial(true)}>
                       <HelpCircle className="mr-3 h-5 w-5" /> Pipeline SOP
                     </Button>
                  </CardContent>
               </Card>
            </div>

            {/* Notebook Interface */}
            <div className="md:col-span-9 space-y-8">
               <div className="rounded-[2.5rem] border border-border/60 bg-card/65 p-6 shadow-xl backdrop-blur-xl">
                 <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                   <div>
                     <div className="text-[10px] font-black uppercase tracking-[0.35em] text-muted-foreground">Notebook</div>
                     <div className="mt-2 text-2xl font-black tracking-tighter uppercase">Research Draft</div>
                   </div>
                   <div className="rounded-full border border-border/60 bg-background/70 px-4 py-2 text-[10px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                     {cells.length} cells
                   </div>
                 </div>
               </div>

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
                              <button className="rounded-lg p-2 text-emerald-500 transition-all hover:bg-emerald-500/10"><PlayCircle className="h-5 w-5" /></button>
                           </div>
                        </div>
                        <CardContent className="bg-[#080808] p-0">
                           <Editor
                              value={cell.content}
                              onValueChange={(code) =>
                                setCells((prev) =>
                                  prev.map((c) => (c.id === cell.id ? { ...c, content: code } : c))
                                )
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
                                      o.line?.includes('ERROR') || o.line?.includes('Traceback') ? 'text-red-400 bg-red-500/5 px-2 rounded border-l-2 border-red-500 my-1' : 
                                      o.line?.startsWith('---') ? 'text-blue-400 font-black mt-4' :
                                      o.line?.startsWith('✓') ? 'text-emerald-400 font-bold' :
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
      ) : (
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
                            {Array.isArray(experiments) && experiments.length > 0 ? experiments.map((run: any) => {
                               const isTrainingRun = run.metrics?.accuracy !== undefined;
                               return (
                                 <tr key={run.run_id} className="hover:bg-primary/5 transition-colors group">
                                    <td className="py-10 px-14">
                                       <div className="font-black group-hover:text-primary transition-colors uppercase text-lg tracking-tight">{run.name}</div>
                                       <div className="text-[11px] text-muted-foreground font-mono mt-2 font-bold flex items-center gap-3">
                                          <span className="bg-primary/10 text-primary px-3 py-1 rounded-xl border border-primary/20 text-[9px] tracking-widest">{run.params?.model_class || "SCIKIT-LEARN"}</span>
                                          <span className="opacity-30 font-normal">{run.run_id.slice(0, 16)}</span>
                                       </div>
                                    </td>
                                    <td className="py-10 px-4 text-center">
                                       <span className={`text-[10px] px-5 py-2.5 rounded-2xl font-black uppercase tracking-widest border-2 shadow-2xl ${run.status === 'FINISHED' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-red-500/10 text-red-500 border-red-500/20'}`}>{run.status}</span>
                                    </td>
                                    <td className="py-10 px-4">
                                       <div className="flex justify-center gap-12">
                                          {isTrainingRun ? (
                                             <div className="text-center">
                                                <div className="text-2xl font-black text-blue-500 tracking-tighter">{(run.metrics?.accuracy * 100)?.toFixed(1)}%</div>
                                                <div className="text-[9px] uppercase font-black tracking-widest opacity-40 mt-1">Accuracy</div>
                                             </div>
                                          ) : (
                                             <div className="text-center">
                                                <div className="text-2xl font-black text-foreground tracking-tighter">{run.metrics?.sharpe?.toFixed(2) || "0.00"}</div>
                                                <div className="text-[9px] uppercase font-black tracking-widest opacity-40 mt-1">Sharpe</div>
                                             </div>
                                          )}
                                       </div>
                                    </td>
                                    <td className="py-10 px-14 text-right">
                                       <Button 
                                         className="h-12 text-[10px] px-10 font-black uppercase tracking-[0.2em] shadow-2xl bg-emerald-600 hover:bg-emerald-500 text-white rounded-[1.2rem] flex items-center gap-3 transition-all hover:scale-105 active:scale-95" 
                                         onClick={() => {if(confirm(`Promote this model configuration to production?`)) {deployModel.mutate(run.run_id, {onSuccess: (data) => alert(data.message)});}}} 
                                         disabled={deployModel.isPending}
                                       >
                                          {deployModel.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />}
                                          {isTrainingRun ? "ACTIVATE MODEL" : "USE PARAMETERS"}
                                     </Button>
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
