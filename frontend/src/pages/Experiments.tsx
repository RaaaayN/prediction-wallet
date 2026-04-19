import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useExperiments, useStrategies, useRunBacktest } from "@/api/queries";
import { ExternalLink, Clock, Activity, BarChart2, PlayCircle, Loader2 } from "lucide-react";
import { format } from "date-fns";
import { useQueryClient } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";

export function Experiments() {
  const profile = useStore((state) => state.profile);
  const { data: experiments, isLoading } = useExperiments();
  const { data: strategies, isLoading: stratsLoading } = useStrategies();
  const runBacktest = useRunBacktest();
  const queryClient = useQueryClient();

  const [selectedStrategy, setSelectedStrategy] = useState("ensemble");
  const [days, setDays] = useState(90);

  const handleRunExperiment = async () => {
    try {
      await runBacktest.mutateAsync({ strategy: selectedStrategy, days, profile });
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
    } catch (e) {
      alert("Failed to run experiment. Ensure MLflow tracking URI is accessible.");
    }
  };

  if (isLoading) return <div className="p-8 animate-pulse text-muted-foreground">Connecting to MLflow Tracking Server...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Model Registry & Experiments</h2>
          <p className="text-muted-foreground mt-1">Track training runs, backtest metrics, and champion models via MLflow.</p>
        </div>
        <a 
          href="http://localhost:5000" 
          target="_blank" 
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-primary hover:underline font-medium"
        >
          <ExternalLink className="h-4 w-4" /> Open MLflow UI
        </a>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        {/* Launch Panel */}
        <Card className="md:col-span-1">
          <CardHeader>
             <CardTitle className="flex items-center gap-2"><PlayCircle className="h-4 w-4" /> New Experiment</CardTitle>
             <CardDescription>Run a backtest and log metrics to MLflow.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
             <div className="space-y-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Strategy Configuration</label>
                <select 
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm focus:ring-1 focus:ring-primary capitalize"
                  value={selectedStrategy}
                  onChange={(e) => setSelectedStrategy(e.target.value)}
                  disabled={stratsLoading}
                >
                  {strategies?.map((s: any) => (
                    <option key={s.name} value={s.name}>{s.name} ({s.is_active ? 'Active' : 'Inactive'})</option>
                  ))}
                </select>
             </div>
             <div className="space-y-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Time Horizon (Days)</label>
                <input 
                  type="number" 
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm font-mono"
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                  min={10}
                  max={365}
                />
             </div>
             <Button 
                className="w-full" 
                onClick={handleRunExperiment} 
                disabled={runBacktest.isPending}
             >
                {runBacktest.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <PlayCircle className="h-4 w-4 mr-2" />}
                {runBacktest.isPending ? "Running simulation..." : "Launch Experiment"}
             </Button>
          </CardContent>
        </Card>

        {/* Runs Table */}
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Activity className="h-4 w-4" /> Recent Training & Backtest Runs</CardTitle>
            <CardDescription>Experiment metadata synced from local MLflow store.</CardDescription>
          </CardHeader>
          <CardContent>
            {experiments && experiments.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden h-[350px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground sticky top-0 z-10">
                    <tr>
                      <th className="py-2 px-4 text-left font-bold">Run Name</th>
                      <th className="py-2 px-4 text-left font-bold">Status</th>
                      <th className="py-2 px-4 text-left font-bold">Metrics (Sharpe / Return)</th>
                      <th className="py-2 px-4 text-right font-bold">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {experiments.map((run: any) => (
                      <tr key={run.run_id} className="hover:bg-secondary/20 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-medium">{run.name}</div>
                          <div className="text-[10px] text-muted-foreground font-mono">{run.run_id.slice(0, 8)}...</div>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                            run.status === 'FINISHED' ? 'bg-emerald-500/10 text-emerald-500' : 
                            run.status === 'RUNNING' ? 'bg-blue-500/10 text-blue-500' : 'bg-destructive/10 text-destructive'
                          }`}>
                            {run.status}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex flex-wrap gap-2">
                             <div className="text-[10px] bg-secondary/50 px-1.5 py-0.5 rounded border border-border">
                                <span className="text-muted-foreground mr-1">Sharpe:</span>
                                <span className="font-bold">{run.metrics?.sharpe?.toFixed(2) || "N/A"}</span>
                             </div>
                             <div className="text-[10px] bg-secondary/50 px-1.5 py-0.5 rounded border border-border">
                                <span className="text-muted-foreground mr-1">Ret:</span>
                                <span className={`font-bold ${run.metrics?.ann_ret > 0 ? 'text-emerald-500' : 'text-destructive'}`}>
                                  {(run.metrics?.ann_ret * 100)?.toFixed(1) || 0}%
                                </span>
                             </div>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right text-xs text-muted-foreground whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1">
                            <Clock className="h-3 w-3" />
                            {format(new Date(run.start_time), "MMM dd, HH:mm")}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-16 text-muted-foreground border border-dashed border-border rounded-lg bg-secondary/5">
                <BarChart2 className="mx-auto h-12 w-12 opacity-20 mb-4" />
                <h3 className="text-lg font-medium text-foreground">No experiments found</h3>
                <p className="max-w-xs mx-auto mt-2 text-sm">
                  Launch a new experiment using the panel to log your first run.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
