import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useExperiments, useStrategies, useRunBacktest, useDeployModel } from "@/api/queries";
import { ExternalLink, Clock, Activity, BarChart2, PlayCircle, Loader2, Settings2, Trophy, Beaker, Rocket } from "lucide-react";
import { format } from "date-fns";
import { useQueryClient } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";

export function Experiments() {
  const profile = useStore((state) => state.profile);
  const { data: experiments, isLoading } = useExperiments();
  const { data: strategies, isLoading: stratsLoading } = useStrategies();
  const runBacktest = useRunBacktest();
  const deployModel = useDeployModel();
  const queryClient = useQueryClient();

  const [selectedStrategy, setSelectedStrategy] = useState("ensemble");
  const [runName, setRunName] = useState("");
  const [days, setDays] = useState(90);
  const [strategyParams, setStrategyParams] = useState<any>({});

  // Initialize params when strategy changes
  useMemo(() => {
    const strat = strategies?.find((s: any) => s.name === selectedStrategy);
    if (strat) {
      setStrategyParams({ ...strat.params });
    }
  }, [selectedStrategy, strategies]);

  const handleRunExperiment = async () => {
    try {
      await runBacktest.mutateAsync({ 
        strategy: selectedStrategy, 
        days, 
        profile,
        run_name: runName || undefined,
        strategy_params: strategyParams
      });
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      setRunName("");
    } catch (e) {
      alert("Failed to launch experiment.");
    }
  };

  // Leaderboard Calculation
  const leaderboard = useMemo(() => {
    if (!experiments) return [];
    return [...experiments]
      .filter(e => e.status === 'FINISHED' && e.metrics?.sharpe)
      .sort((a, b) => (b.metrics.sharpe || 0) - (a.metrics.sharpe || 0))
      .slice(0, 3);
  }, [experiments]);

  if (isLoading) return (
    <div className="p-8 flex flex-col items-center justify-center min-h-[400px] text-muted-foreground">
      <Loader2 className="h-8 w-8 animate-spin mb-4" />
      <p className="animate-pulse">Synchronizing with MLflow Tracking Server...</p>
    </div>
  );

  return (
    <div className="space-y-6 pb-20">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Experiment Space</h2>
          <p className="text-muted-foreground mt-1">Design, parameterize, and benchmark investment models with MLflow tracking.</p>
        </div>
        <div className="flex gap-3">
          <a 
            href="http://localhost:5000" 
            target="_blank" 
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-border bg-card text-sm font-medium hover:bg-accent transition-colors"
          >
            <ExternalLink className="h-4 w-4" /> MLflow UI
          </a>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        {/* Model Designer Panel */}
        <Card className="md:col-span-1 border-primary/20 shadow-lg shadow-primary/5">
          <CardHeader className="bg-primary/5 border-b border-primary/10">
             <CardTitle className="flex items-center gap-2 text-primary"><Beaker className="h-4 w-4" /> Model Designer</CardTitle>
             <CardDescription>Configure hyperparameters</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
             <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest">Base Logic</label>
                <select 
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:ring-2 focus:ring-primary capitalize transition-all"
                  value={selectedStrategy}
                  onChange={(e) => setSelectedStrategy(e.target.value)}
                  disabled={stratsLoading}
                >
                  {strategies?.map((s: any) => (
                    <option key={s.name} value={s.name}>{s.name}</option>
                  ))}
                </select>
             </div>

             <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase text-muted-foreground tracking-widest">Experiment Name</label>
                <input 
                  type="text" 
                  placeholder="e.g. Aggressive Sentiment"
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:ring-2 focus:ring-primary transition-all"
                  value={runName}
                  onChange={(e) => setRunName(e.target.value)}
                />
             </div>

             <div className="space-y-4 p-3 bg-secondary/30 rounded-lg border border-border/50">
                <div className="text-[10px] font-bold uppercase text-muted-foreground border-b border-border pb-1 flex items-center gap-1">
                   <Settings2 className="h-3 w-3" /> Parameters
                </div>
                {Object.entries(strategyParams).map(([key, value]: [string, any]) => (
                  <div key={key} className="space-y-1.5">
                    <label className="text-[10px] font-medium text-muted-foreground capitalize">{key.replace(/_/g, ' ')}</label>
                    <input 
                      type={typeof value === 'number' ? "number" : "text"}
                      step="0.01"
                      className="w-full h-8 rounded border border-input bg-background px-2 text-xs font-mono"
                      value={strategyParams[key]}
                      onChange={e => setStrategyParams({...strategyParams, [key]: typeof value === 'number' ? parseFloat(e.target.value) : e.target.value})}
                    />
                  </div>
                ))}
                <div className="space-y-1.5">
                    <label className="text-[10px] font-medium text-muted-foreground uppercase">Horizon (Days)</label>
                    <input 
                      type="number" 
                      className="w-full h-8 rounded border border-input bg-background px-2 text-xs font-mono"
                      value={days}
                      onChange={(e) => setDays(Number(e.target.value))}
                    />
                </div>
             </div>

             <Button 
                className="w-full shadow-md" 
                onClick={handleRunExperiment} 
                disabled={runBacktest.isPending}
             >
                {runBacktest.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <PlayCircle className="h-4 w-4 mr-2" />}
                {runBacktest.isPending ? "Simulating..." : "Execute Test"}
             </Button>
          </CardContent>
        </Card>

        {/* Results & Leaderboard */}
        <div className="md:col-span-3 space-y-6">
          {/* Top Models */}
          <div className="grid grid-cols-3 gap-4">
             {leaderboard.map((run, i) => (
               <Card key={run.run_id} className={`border-l-4 ${i === 0 ? 'border-l-yellow-500' : i === 1 ? 'border-l-gray-400' : 'border-l-amber-700'}`}>
                  <CardContent className="pt-4 px-4 pb-3">
                     <div className="flex justify-between items-start mb-2">
                        <Trophy className={`h-4 w-4 ${i === 0 ? 'text-yellow-500' : 'text-muted-foreground opacity-50'}`} />
                        <span className="text-[10px] font-bold text-muted-foreground uppercase">Rank #{i+1}</span>
                     </div>
                     <div className="font-bold truncate text-sm">{run.name}</div>
                     <div className="flex items-baseline gap-1 mt-1">
                        <span className="text-xl font-black text-primary">{run.metrics?.sharpe?.toFixed(2)}</span>
                        <span className="text-[10px] text-muted-foreground font-medium uppercase">Sharpe</span>
                     </div>
                  </CardContent>
               </Card>
             ))}
             {leaderboard.length === 0 && (
               <div className="col-span-3 h-24 flex items-center justify-center border border-dashed rounded-lg bg-secondary/5 text-muted-foreground text-xs italic">
                  Run experiments to populate the leaderboard.
               </div>
             )}
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between py-4">
              <div>
                <CardTitle className="text-lg flex items-center gap-2"><Activity className="h-4 w-4" /> Experiment Registry</CardTitle>
                <CardDescription>Comprehensive audit log of all model variations.</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {experiments && experiments.length > 0 ? (
                <div className="border border-border rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-secondary/50 border-b border-border text-[10px] uppercase text-muted-foreground">
                      <tr>
                        <th className="py-2 px-4 text-left font-bold">Run / Strategy</th>
                        <th className="py-2 px-4 text-left font-bold">Status</th>
                        <th className="py-2 px-4 text-center font-bold">Risk Adj. Perf</th>
                        <th className="py-2 px-4 text-right font-bold">Timeline</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {experiments.map((run: any) => (
                        <tr key={run.run_id} className="hover:bg-secondary/10 transition-colors group">
                          <td className="py-3 px-4">
                            <div className="font-bold text-foreground group-hover:text-primary transition-colors">{run.name}</div>
                            <div className="text-[10px] text-muted-foreground font-mono flex items-center gap-2">
                               <span className="bg-secondary px-1 rounded uppercase">{run.params?.strategy_type || "unknown"}</span>
                               <span>{run.run_id.slice(0, 8)}</span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-black uppercase ${
                              run.status === 'FINISHED' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 
                              run.status === 'RUNNING' ? 'bg-blue-500/10 text-blue-500 border border-blue-500/20' : 'bg-destructive/10 text-destructive border border-destructive/20'
                            }`}>
                              {run.status}
                            </span>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex justify-center gap-4">
                               <div className="text-center">
                                  <div className="text-xs font-black">{run.metrics?.sharpe?.toFixed(2) || "0.00"}</div>
                                  <div className="text-[8px] text-muted-foreground uppercase font-bold">Sharpe</div>
                               </div>
                               <div className="text-center">
                                  <div className={`text-xs font-black ${run.metrics?.ann_ret > 0 ? 'text-emerald-500' : 'text-destructive'}`}>
                                    {(run.metrics?.ann_ret * 100)?.toFixed(1) || 0}%
                                  </div>
                                  <div className="text-[8px] text-muted-foreground uppercase font-bold">Ann. Ret</div>
                               </div>
                            </div>
                          </td>
                          <td className="py-3 px-4 text-right">
                             <div className="flex flex-col items-end gap-2">
                                <div className="flex items-center gap-1 text-[10px] text-muted-foreground font-medium">
                                   <Clock className="h-3 w-3" />
                                   {format(new Date(run.start_time), "MMM dd, HH:mm")}
                                </div>
                                {run.status === 'FINISHED' && (
                                   <Button 
                                      size="sm" 
                                      variant="outline" 
                                      className="h-7 text-[10px] px-2 font-bold hover:bg-emerald-500 hover:text-white transition-all group/btn"
                                      onClick={() => {
                                        if(confirm("Apply this model's parameters to your live profile? This will overwrite the strategy configuration in " + profile + ".yaml")) {
                                          deployModel.mutate(run.run_id, {
                                            onSuccess: (data) => alert(data.message)
                                          });
                                        }
                                      }}
                                      disabled={deployModel.isPending}
                                   >
                                      {deployModel.isPending ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Rocket className="h-3 w-3 mr-1 group-hover/btn:animate-bounce" />}
                                      DEPLOY TO LIVE
                                   </Button>
                                )}
                             </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-16 text-muted-foreground border border-dashed border-border rounded-lg bg-secondary/5 flex flex-col items-center">
                  <BarChart2 className="h-12 w-12 opacity-10 mb-4" />
                  <p className="text-sm">Start your research by execution a test in the Model Designer.</p>
                  <code className="mt-6 text-[10px] bg-black p-2 rounded text-emerald-500 w-full max-w-sm overflow-x-auto text-center">
                    mlflow ui --backend-store-uri sqlite:///data/mlflow.db
                  </code>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
