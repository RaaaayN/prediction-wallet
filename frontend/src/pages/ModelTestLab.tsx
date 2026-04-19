import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  useExperiments,
  useGoldDatasets,
  useTestTrainedModel,
  useTrainModel,
  type ModelTestResult,
} from "@/api/queries";
import { useStore } from "@/store/useStore";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import { ArrowLeft, Cpu, Loader2, PlayCircle, FlaskConical, LineChart, ArrowUpCircle, ArrowDownCircle, AlertTriangle, TrendingUp } from "lucide-react";

export function ModelTestLab() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const profile = useStore((state) => state.profile);

  const { data: experiments } = useExperiments();
  const { data: goldDatasets } = useGoldDatasets();
  const trainModel = useTrainModel();
  const testTrainedModel = useTestTrainedModel();

  const goldDatasetList = useMemo(() => (Array.isArray(goldDatasets) ? goldDatasets : []), [goldDatasets]);
  const trainingRuns = useMemo(() => {
    if (!Array.isArray(experiments)) return [];
    return [...experiments]
      .filter((run: any) => run.status === "FINISHED" && typeof run.metrics?.accuracy === "number")
      .sort((a: any, b: any) => (b.start_time || "").localeCompare(a.start_time || ""));
  }, [experiments]);

  const [selectedModelRunId, setSelectedModelRunId] = useState<string | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const [modelTestDays, setModelTestDays] = useState(90);
  const [modelTestCapital, setModelTestCapital] = useState(100000);
  const [modelTestTickers, setModelTestTickers] = useState("AAPL, MSFT, NVDA");
  const [grossLimit, setGrossLimit] = useState(2.0);
  const [maxSingleTicker, setMaxSingleTicker] = useState(1.0);
  const [modelTestResult, setModelTestResult] = useState<ModelTestResult | null>(null);
  const [activeResultTab, setActiveResultTab] = useState<"metrics" | "trades" | "positions" | "violations">("metrics");
  const [tradeFilter, setTradeFilter] = useState("");

  // Pre-select run from URL query param (e.g. from Experiments "Tester ce modèle")
  useEffect(() => {
    const urlRunId = searchParams.get("run_id");
    if (urlRunId) setSelectedModelRunId(urlRunId);
  }, [searchParams]);

  useEffect(() => {
    if (goldDatasetList.length === 0) { setSelectedDataset(null); return; }
    if (selectedDataset === null || !goldDatasetList.includes(selectedDataset)) {
      setSelectedDataset(goldDatasetList[0]);
    }
  }, [goldDatasetList, selectedDataset]);

  useEffect(() => {
    if (!selectedModelRunId && trainingRuns[0]?.run_id) {
      setSelectedModelRunId(trainingRuns[0].run_id);
    }
  }, [trainingRuns, selectedModelRunId]);

  const selectedRun = useMemo(
    () => trainingRuns.find((r: any) => r.run_id === selectedModelRunId) ?? trainingRuns[0] ?? null,
    [trainingRuns, selectedModelRunId]
  );

  const fmt = (v: unknown, d: number) =>
    typeof v === "number" && Number.isFinite(v) ? v.toFixed(d) : "—";
  const fmtPct = (v: unknown, d = 2) => `${fmt(v, d)}%`;

  const parseTickers = () =>
    modelTestTickers.split(",").map(t => t.trim().toUpperCase()).filter(Boolean);

  const runModelTest = async (runId: string, sourceDataset?: string | null) => {
    const tickers = parseTickers();
    if (tickers.length === 0) { alert("Fournissez au moins un ticker."); return; }
    try {
      const result = await testTrainedModel.mutateAsync({
        run_id: runId, profile,
        days: modelTestDays,
        initial_capital: modelTestCapital,
        tickers,
        gold_dataset_name: sourceDataset || undefined,
        run_name: `model_test_${runId.slice(0, 8)}_${modelTestDays}d`,
      });
      setModelTestResult(result);
      setSelectedModelRunId(runId);
      setActiveResultTab("metrics");
    } catch {
      alert("Test échoué. Vérifiez les logs.");
    }
  };

  const trainAndTest = async () => {
    try {
      const datasetName = selectedDataset || "live_sync";
      const trainResult = await trainModel.mutateAsync({ profile, params: { dataset_name: datasetName } });
      const runId = trainResult?.result?.run_id || trainResult?.run_id;
      if (!runId) { alert("Entraînement OK mais pas de run_id retourné."); return; }
      setSelectedModelRunId(runId);
      await runModelTest(runId, selectedDataset || undefined);
    } catch {
      alert("Entraînement échoué.");
    }
  };

  const testSelectedRun = async () => {
    const runId = selectedModelRunId || trainingRuns[0]?.run_id;
    if (!runId) { alert("Sélectionnez un run entraîné."); return; }
    await runModelTest(runId, selectedDataset || undefined);
  };

  // Compute drawdown series for equity chart
  const equityWithDrawdown = useMemo(() => {
    if (!modelTestResult?.history?.length) return [];
    let peak = modelTestResult.history[0].total_value;
    return modelTestResult.history.map(d => {
      if (d.total_value > peak) peak = d.total_value;
      const dd = peak > 0 ? ((d.total_value - peak) / peak) * 100 : 0;
      return { ...d, drawdown: parseFloat(dd.toFixed(2)) };
    });
  }, [modelTestResult?.history]);

  const filteredTrades = useMemo(() => {
    if (!modelTestResult?.trades) return [];
    return tradeFilter
      ? modelTestResult.trades.filter(t => t.ticker.includes(tradeFilter.toUpperCase()))
      : modelTestResult.trades;
  }, [modelTestResult?.trades, tradeFilter]);

  const totalCommission = useMemo(
    () => modelTestResult?.trades?.reduce((sum, t) => sum + (t.commission ?? 0), 0) ?? 0,
    [modelTestResult?.trades]
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-[10px] font-black uppercase tracking-[0.35em] text-muted-foreground">
            <FlaskConical className="h-4 w-4" /> Position Lab
          </div>
          <h2 className="text-3xl font-black tracking-tight text-foreground">Model Test Lab</h2>
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
            Sélectionnez un modèle entraîné, configurez l'univers et la période, puis analysez chaque trade et position pris par le modèle.
          </p>
        </div>
        <Button variant="outline" className="rounded-2xl" onClick={() => navigate("/experiments")}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Experiments
        </Button>
      </div>

      <div className="grid gap-8 xl:grid-cols-[380px_1fr]">
        {/* Config panel */}
        <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/75 shadow-2xl backdrop-blur-xl">
          <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
            <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground">
              <Cpu className="h-4 w-4" /> Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 p-8">
            {/* Model selector */}
            <div className="space-y-2">
              <label className="text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">Modèle entraîné</label>
              <select
                value={selectedModelRunId ?? ""}
                onChange={e => setSelectedModelRunId(e.target.value || null)}
                className="h-11 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-sm font-bold outline-none transition-all focus:border-primary"
              >
                <option value="">— Dernier run entraîné —</option>
                {trainingRuns.map((run: any) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.name} · {(run.metrics?.accuracy * 100).toFixed(1)}% acc
                  </option>
                ))}
              </select>
            </div>

            {/* Selected model info */}
            {selectedRun && (
              <div className="rounded-[1.25rem] border border-primary/20 bg-primary/5 p-4 space-y-1">
                <div className="text-[9px] font-black uppercase tracking-[0.28em] text-primary">Modèle sélectionné</div>
                <div className="text-xs font-bold text-foreground">{selectedRun.params?.model_type || selectedRun.params?.model_class || "sklearn"}</div>
                <div className="flex gap-4 text-[9px] font-black uppercase text-muted-foreground mt-1">
                  <span>Acc: <span className="text-blue-500">{(selectedRun.metrics?.accuracy * 100).toFixed(1)}%</span></span>
                  {selectedRun.metrics?.precision !== undefined && (
                    <span>Prec: <span className="text-foreground">{(selectedRun.metrics.precision * 100).toFixed(1)}%</span></span>
                  )}
                </div>
                <div className="font-mono text-[9px] text-muted-foreground/40 break-all">{selectedRun.run_id}</div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">
                  Jours <span className="text-primary">{modelTestDays}</span>
                </label>
                <input
                  type="range" min={10} max={365} step={5}
                  value={modelTestDays}
                  onChange={e => setModelTestDays(Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">Capital</label>
                <input
                  type="number" min={1000} step={1000}
                  value={modelTestCapital}
                  onChange={e => setModelTestCapital(Number(e.target.value))}
                  className="h-9 w-full rounded-xl border border-border/50 bg-background px-3 text-sm font-bold outline-none focus:border-primary"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">Tickers (séparés par virgule)</label>
              <input
                value={modelTestTickers}
                onChange={e => setModelTestTickers(e.target.value)}
                placeholder="AAPL, MSFT, NVDA"
                className="h-11 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-sm font-bold outline-none focus:border-primary"
              />
            </div>

            <div className="space-y-1">
              <label className="text-[9px] font-black uppercase tracking-[0.25em] text-muted-foreground">Gold dataset</label>
              <select
                value={selectedDataset ?? ""}
                onChange={e => setSelectedDataset(e.target.value || null)}
                className="h-11 w-full rounded-2xl border-2 border-border/50 bg-background px-4 text-sm font-bold outline-none focus:border-primary"
              >
                <option value="">Marché live (fallback)</option>
                {goldDatasetList.map((ds: string) => <option key={ds} value={ds}>{ds}</option>)}
              </select>
            </div>

            {/* Risk params */}
            <details className="rounded-[1.25rem] border border-border/40 bg-background/50 p-4">
              <summary className="text-[9px] font-black uppercase tracking-[0.28em] text-muted-foreground cursor-pointer select-none">
                Risk params (avancé)
              </summary>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                    Gross limit <span className="text-primary">{grossLimit}x</span>
                  </label>
                  <input
                    type="range" min={1.0} max={3.0} step={0.1}
                    value={grossLimit}
                    onChange={e => setGrossLimit(Number(e.target.value))}
                    className="w-full accent-primary"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[9px] font-black uppercase tracking-[0.22em] text-muted-foreground">
                    Max ticker <span className="text-primary">{(maxSingleTicker * 100).toFixed(0)}%</span>
                  </label>
                  <input
                    type="range" min={0.1} max={1.0} step={0.05}
                    value={maxSingleTicker}
                    onChange={e => setMaxSingleTicker(Number(e.target.value))}
                    className="w-full accent-primary"
                  />
                </div>
              </div>
            </details>

            <div className="grid grid-cols-2 gap-3">
              <Button
                className="h-12 rounded-[1.25rem] bg-primary text-[10px] font-black uppercase tracking-[0.2em] text-white hover:bg-primary/90"
                onClick={trainAndTest}
                disabled={trainModel.isPending || testTrainedModel.isPending}
              >
                {trainModel.isPending || testTrainedModel.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <PlayCircle className="mr-2 h-4 w-4" />
                )}
                Train & Test
              </Button>
              <Button
                variant="outline"
                className="h-12 rounded-[1.25rem] border-2 border-border/60 text-[10px] font-black uppercase tracking-[0.2em]"
                onClick={testSelectedRun}
                disabled={testTrainedModel.isPending || trainingRuns.length === 0}
              >
                {testTrainedModel.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Tester le run
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Results panel */}
        {modelTestResult ? (
          <div className="space-y-6">
            {/* Result sub-tabs */}
            <div className="flex gap-2 rounded-[1.5rem] border border-border/60 bg-background/60 p-2 w-fit">
              {(["metrics", "trades", "positions", "violations"] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveResultTab(tab)}
                  className={`rounded-xl px-5 py-2.5 text-[10px] font-black uppercase tracking-[0.25em] transition-all ${
                    activeResultTab === tab
                      ? 'bg-primary text-white shadow-lg'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab === "violations" && (modelTestResult.risk_violations?.length ?? 0) > 0 && (
                    <span className="mr-1.5 rounded-full bg-amber-500 px-1.5 py-0.5 text-[8px] text-white">
                      {modelTestResult.risk_violations!.length}
                    </span>
                  )}
                  {tab}
                </button>
              ))}
            </div>

            <Card className="overflow-hidden rounded-[2.5rem] border-border/60 bg-card/75 shadow-2xl backdrop-blur-xl">
              <CardHeader className="border-b border-border/50 bg-secondary/10 px-8 py-6">
                <CardTitle className="flex items-center gap-3 text-[11px] font-black uppercase tracking-[0.3em] text-muted-foreground">
                  <LineChart className="h-4 w-4" /> Résultats du test
                </CardTitle>
                <CardDescription className="pt-2 text-sm text-muted-foreground">
                  Run <span className="font-mono text-foreground">{modelTestResult.model_run_id?.slice(0, 8)}</span>
                  {" · "}{modelTestResult.days}j
                  {" · "}${Number(modelTestResult.initial_capital || 0).toLocaleString()}
                  {modelTestResult.gold_dataset_name ? ` · ${modelTestResult.gold_dataset_name}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-8 p-8">

                {activeResultTab === "metrics" && (
                  <>
                    <div className="rounded-[1.25rem] border border-border/40 bg-background/60 p-4 text-sm text-muted-foreground">
                      Mode long/short : le modèle classe l'univers quotidiennement, construit un livre market-neutral et rééquilibre sur la fenêtre demandée.
                    </div>
                    <div className="grid gap-4 md:grid-cols-4">
                      <MetricCard label="Rendement annualisé" value={fmtPct(modelTestResult.annualized_return)} accent="text-primary" />
                      <MetricCard label="Sharpe" value={fmt(modelTestResult.sharpe, 2)} />
                      <MetricCard label="Max drawdown" value={fmtPct(modelTestResult.max_drawdown)} accent="text-destructive" />
                      <MetricCard label="Trades" value={String(modelTestResult.n_trades)} />
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                      <MetricCard label="Alpha" value={fmt(modelTestResult.alpha, 4)} />
                      <MetricCard label="Beta" value={fmt(modelTestResult.beta, 4)} />
                      <MetricCard label="Risk violations" value={String(modelTestResult.n_risk_violations ?? 0)} accent={modelTestResult.n_risk_violations ? "text-amber-500" : "text-foreground"} />
                    </div>

                    {equityWithDrawdown.length > 0 && (
                      <div className="rounded-[2rem] border border-border/50 bg-background/70 p-5 space-y-4">
                        <div className="text-[9px] font-black uppercase tracking-[0.3em] text-muted-foreground">Equity curve</div>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={equityWithDrawdown}>
                              <defs>
                                <linearGradient id="equityArea" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.35} />
                                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0.02} />
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.3} />
                              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickLine={false} />
                              <YAxis tick={{ fontSize: 9 }} tickLine={false} />
                              <Tooltip formatter={(v: any) => [`$${Number(v).toLocaleString()}`, "Valeur"]} />
                              <Area type="monotone" dataKey="total_value" stroke="#22c55e" fill="url(#equityArea)" strokeWidth={2.5} dot={false} />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>

                        {/* Drawdown chart */}
                        <div className="text-[9px] font-black uppercase tracking-[0.3em] text-muted-foreground mt-2">Drawdown</div>
                        <div className="h-32">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={equityWithDrawdown}>
                              <defs>
                                <linearGradient id="ddArea" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.4} />
                                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                                </linearGradient>
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.2} />
                              <XAxis dataKey="date" tick={{ fontSize: 9 }} tickLine={false} />
                              <YAxis tick={{ fontSize: 9 }} tickLine={false} />
                              <ReferenceLine y={0} stroke="hsl(var(--border))" />
                              <Tooltip formatter={(v: any) => [`${Number(v).toFixed(2)}%`, "Drawdown"]} />
                              <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="url(#ddArea)" strokeWidth={1.5} dot={false} />
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2 text-[10px] font-black uppercase tracking-[0.25em] text-muted-foreground">
                      {modelTestResult.tickers?.map(t => (
                        <span key={t} className="rounded-full bg-secondary px-3 py-1">{t}</span>
                      ))}
                      {modelTestResult.data_hash && (
                        <span className="rounded-full bg-secondary px-3 py-1">hash {modelTestResult.data_hash.slice(0, 8)}</span>
                      )}
                    </div>
                  </>
                )}

                {activeResultTab === "trades" && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-4">
                      <div className="text-sm font-bold text-foreground">
                        {filteredTrades.length} trades
                        {totalCommission > 0 && (
                          <span className="ml-3 text-muted-foreground font-normal">
                            · Commission totale: ${totalCommission.toFixed(2)}
                          </span>
                        )}
                      </div>
                      <input
                        value={tradeFilter}
                        onChange={e => setTradeFilter(e.target.value)}
                        placeholder="Filtrer par ticker…"
                        className="h-9 w-44 rounded-xl border border-border/50 bg-background px-3 text-sm outline-none focus:border-primary"
                      />
                    </div>
                    <div className="overflow-auto rounded-[1.5rem] border border-border/40">
                      <table className="min-w-full text-left text-xs">
                        <thead className="bg-secondary/20 text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                          <tr>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Ticker</th>
                            <th className="px-4 py-3">Action</th>
                            <th className="px-4 py-3 text-right">Quantité</th>
                            <th className="px-4 py-3 text-right">Prix marché</th>
                            <th className="px-4 py-3 text-right">Fill price</th>
                            <th className="px-4 py-3 text-right">Commission</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredTrades.length === 0 ? (
                            <tr>
                              <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                                Aucun trade {tradeFilter ? `pour "${tradeFilter}"` : ""}
                              </td>
                            </tr>
                          ) : filteredTrades.map((trade, i) => (
                            <tr key={i} className="border-t border-border/30 hover:bg-primary/5 transition-colors">
                              <td className="px-4 py-2.5 text-muted-foreground font-mono">{trade.timestamp?.split("T")[0] ?? trade.timestamp}</td>
                              <td className="px-4 py-2.5 font-black text-foreground">{trade.ticker}</td>
                              <td className="px-4 py-2.5">
                                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[9px] font-black uppercase tracking-wider ${
                                  trade.action === "buy"
                                    ? "bg-emerald-500/10 text-emerald-600"
                                    : "bg-red-500/10 text-red-500"
                                }`}>
                                  {trade.action === "buy"
                                    ? <ArrowUpCircle className="h-3 w-3" />
                                    : <ArrowDownCircle className="h-3 w-3" />}
                                  {trade.action}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-right font-mono">{Number(trade.quantity).toFixed(3)}</td>
                              <td className="px-4 py-2.5 text-right font-mono">${Number(trade.market_price).toFixed(2)}</td>
                              <td className="px-4 py-2.5 text-right font-mono text-muted-foreground">${Number(trade.fill_price).toFixed(2)}</td>
                              <td className="px-4 py-2.5 text-right font-mono text-muted-foreground">${Number(trade.commission ?? 0).toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {activeResultTab === "positions" && (
                  <div className="space-y-4">
                    <div className="text-sm font-bold text-foreground">
                      {modelTestResult.exposures?.length ?? 0} jours · positions long/short quotidiennes
                    </div>
                    <div className="overflow-auto rounded-[1.5rem] border border-border/40 max-h-[600px]">
                      <table className="min-w-full text-left text-xs">
                        <thead className="sticky top-0 bg-secondary/30 text-[9px] uppercase tracking-[0.22em] text-muted-foreground">
                          <tr>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Long</th>
                            <th className="px-4 py-3">Short</th>
                            <th className="px-4 py-3 text-right">Gross</th>
                            <th className="px-4 py-3 text-right">Net</th>
                            <th className="px-4 py-3 text-right">L/S</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(modelTestResult.exposures ?? []).map((day, i) => {
                            const sides = day.position_sides ?? {};
                            const longs = Object.entries(sides).filter(([, s]) => s === "long").map(([t]) => t);
                            const shorts = Object.entries(sides).filter(([, s]) => s === "short").map(([t]) => t);
                            return (
                              <tr key={i} className="border-t border-border/30 hover:bg-primary/5 transition-colors">
                                <td className="px-4 py-2.5 font-mono text-muted-foreground">{day.date}</td>
                                <td className="px-4 py-2.5">
                                  <div className="flex flex-wrap gap-1">
                                    {longs.length > 0 ? longs.map(t => (
                                      <span key={t} className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[9px] font-black text-emerald-600">{t}</span>
                                    )) : <span className="text-muted-foreground/40">—</span>}
                                  </div>
                                </td>
                                <td className="px-4 py-2.5">
                                  <div className="flex flex-wrap gap-1">
                                    {shorts.length > 0 ? shorts.map(t => (
                                      <span key={t} className="rounded-full bg-red-500/10 px-2 py-0.5 text-[9px] font-black text-red-500">{t}</span>
                                    )) : <span className="text-muted-foreground/40">—</span>}
                                  </div>
                                </td>
                                <td className="px-4 py-2.5 text-right font-mono">{fmtPct(day.gross_exposure)}</td>
                                <td className="px-4 py-2.5 text-right font-mono">{fmtPct(day.net_exposure)}</td>
                                <td className="px-4 py-2.5 text-right text-[10px] font-black">
                                  <span className="text-emerald-500">{day.long_count ?? 0}L</span>
                                  {" / "}
                                  <span className="text-red-500">{day.short_count ?? 0}S</span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {activeResultTab === "violations" && (
                  <div className="space-y-4">
                    {(modelTestResult.risk_violations?.length ?? 0) === 0 ? (
                      <div className="flex flex-col items-center justify-center gap-3 rounded-[1.5rem] border border-dashed border-border/50 bg-background/60 py-14 text-center">
                        <TrendingUp className="h-8 w-8 text-emerald-500 opacity-60" />
                        <div className="text-base font-bold text-foreground">Aucune violation</div>
                        <p className="text-sm text-muted-foreground">Tous les ordres ont respecté les limites de risque.</p>
                      </div>
                    ) : (
                      <div className="overflow-auto rounded-[1.5rem] border border-amber-500/20">
                        <table className="min-w-full text-left text-xs">
                          <thead className="bg-amber-500/5 text-[9px] uppercase tracking-[0.22em] text-amber-600">
                            <tr>
                              <th className="px-4 py-3">Date</th>
                              <th className="px-4 py-3">Ticker</th>
                              <th className="px-4 py-3">Violation</th>
                              <th className="px-4 py-3">Détails</th>
                            </tr>
                          </thead>
                          <tbody>
                            {modelTestResult.risk_violations!.map((v, i) => (
                              <tr key={i} className="border-t border-amber-500/10 hover:bg-amber-500/5 transition-colors">
                                <td className="px-4 py-2.5 font-mono text-muted-foreground">{v.timestamp?.split("T")[0] ?? v.timestamp}</td>
                                <td className="px-4 py-2.5 font-black">{v.ticker}</td>
                                <td className="px-4 py-2.5">
                                  <span className="flex items-center gap-1.5 text-amber-600 font-bold">
                                    <AlertTriangle className="h-3.5 w-3.5" />{v.violation}
                                  </span>
                                </td>
                                <td className="px-4 py-2.5 text-muted-foreground font-mono">{v.details}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

              </CardContent>
            </Card>
          </div>
        ) : (
          <Card className="flex min-h-[520px] items-center justify-center rounded-[2.5rem] border-dashed border-border/60 bg-card/50">
            <div className="max-w-md px-8 py-10 text-center text-muted-foreground">
              <FlaskConical className="mx-auto mb-4 h-12 w-12 opacity-20" />
              <h3 className="text-lg font-bold text-foreground">Aucun test lancé</h3>
              <p className="mt-2 text-sm leading-relaxed">
                Entraînez un modèle ou sélectionnez un run existant, puis lancez un backtest pour voir les trades et positions pris par le modèle.
              </p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent = "text-foreground",
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="rounded-[1.75rem] border border-border/50 bg-background/70 p-5">
      <div className="text-[9px] font-black uppercase tracking-[0.28em] text-muted-foreground">{label}</div>
      <div className={`mt-3 text-3xl font-black ${accent}`}>{value}</div>
    </div>
  );
}
