import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useExperiments } from "@/api/queries";
import { ExternalLink, Clock, Activity, BarChart2 } from "lucide-react";
import { format } from "date-fns";

export function Experiments() {
  const { data: experiments, isLoading } = useExperiments();

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

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Activity className="h-4 w-4" /> Recent Training & Backtest Runs</CardTitle>
            <CardDescription>Experiment metadata synced from local MLflow store.</CardDescription>
          </CardHeader>
          <CardContent>
            {experiments && experiments.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left font-bold">Run Name</th>
                      <th className="py-2 px-4 text-left font-bold">Status</th>
                      <th className="py-2 px-4 text-left font-bold">Metrics</th>
                      <th className="py-2 px-4 text-left font-bold">Parameters</th>
                      <th className="py-2 px-4 text-right font-bold">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {experiments.map((run: any) => (
                      <tr key={run.run_id} className="hover:bg-secondary/20">
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
                            {Object.entries(run.metrics || {}).slice(0, 3).map(([k, v]: [string, any]) => (
                              <div key={k} className="text-[10px] bg-secondary/50 px-1.5 py-0.5 rounded border border-border">
                                <span className="text-muted-foreground mr-1">{k}:</span>
                                <span className="font-bold">{typeof v === 'number' ? v.toFixed(3) : v}</span>
                              </div>
                            ))}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                           <div className="flex flex-wrap gap-2">
                            {Object.entries(run.params || {}).slice(0, 2).map(([k, v]: [string, any]) => (
                              <div key={k} className="text-[10px] text-muted-foreground italic">
                                {k}={v}
                              </div>
                            ))}
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
                  Run training scripts or backtests with MLflow tracking enabled to see results here.
                </p>
                <div className="mt-6 flex justify-center gap-3">
                  <code className="text-[10px] bg-black p-2 rounded text-emerald-500">python main.py research-backtest --strategy ensemble</code>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
