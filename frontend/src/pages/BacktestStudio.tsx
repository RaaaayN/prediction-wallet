import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PlayCircle, Loader2, FlaskConical, AlertCircle } from "lucide-react";
import { useStore } from "@/store/useStore";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useRunBacktest } from "@/api/queries";

export function BacktestStudio() {
  const profile = useStore((state) => state.profile);
  const [strategy, setStrategy] = useState("ensemble");
  const [days, setDays] = useState(90);
  const [results, setResults] = useState<any>(null);

  const runBacktest = useRunBacktest();

  const handleRunBacktest = () => {
    setResults(null);
    runBacktest.mutate(
      { strategy, days, profile },
      {
        onSuccess: (data) => setResults(data),
      }
    );
  };

  const errorMessage = runBacktest.error instanceof Error ? runBacktest.error.message : null;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Backtesting Studio</h2>
          <p className="text-muted-foreground mt-1">Run institutional-grade, event-driven simulations (v2).</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-[300px_1fr]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>Setup your simulation parameters</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Strategy Type</label>
              <select 
                className="flex h-9 w-full items-center justify-between whitespace-nowrap rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                value={strategy}
                onChange={e => setStrategy(e.target.value)}
              >
                <option value="threshold">Threshold (Drift-based)</option>
                <option value="calendar">Calendar (Time-based)</option>
                <option value="ensemble">Ensemble (Drift + NLP Sentiment)</option>
              </select>
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Lookback Period (Days)</label>
              <input 
                type="number" 
                value={days}
                onChange={e => setDays(parseInt(e.target.value))}
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            <Button 
              className="w-full mt-4" 
              onClick={handleRunBacktest}
              disabled={runBacktest.isPending}
            >
              {runBacktest.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
              Run Simulation
            </Button>
            {errorMessage && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Backtest failed: {errorMessage}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {results ? (
          <div className="space-y-6">
            <div className="grid gap-4 grid-cols-5">
              <Card>
                <CardHeader className="pb-2 px-4"><CardTitle className="text-[10px] uppercase text-muted-foreground">Ann. Return</CardTitle></CardHeader>
                <CardContent className="px-4 pb-4"><span className="text-lg font-bold text-emerald-500">{(results.metrics.annualized_return * 100).toFixed(2)}%</span></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 px-4"><CardTitle className="text-[10px] uppercase text-muted-foreground">Sharpe</CardTitle></CardHeader>
                <CardContent className="px-4 pb-4"><span className="text-lg font-bold">{results.metrics.sharpe.toFixed(2)}</span></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 px-4"><CardTitle className="text-[10px] uppercase text-muted-foreground">Max DD</CardTitle></CardHeader>
                <CardContent className="px-4 pb-4"><span className="text-lg font-bold text-destructive">{(results.metrics.max_drawdown * 100).toFixed(2)}%</span></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 px-4"><CardTitle className="text-[10px] uppercase text-muted-foreground">Alpha (Ann.)</CardTitle></CardHeader>
                <CardContent className="px-4 pb-4"><span className="text-lg font-bold text-emerald-400">{(results.metrics.alpha * 100).toFixed(2)}%</span></CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2 px-4"><CardTitle className="text-[10px] uppercase text-muted-foreground">Beta</CardTitle></CardHeader>
                <CardContent className="px-4 pb-4"><span className="text-lg font-bold text-amber-400">{results.metrics.beta.toFixed(2)}</span></CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Simulated Equity Curve</CardTitle>
                <CardDescription>Event-driven backtest results mapped against {results.data_hash || "live data"}</CardDescription>
              </CardHeader>
              <CardContent className="h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={results.history}>
                    <defs>
                      <linearGradient id="colorVal" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={v => `$${v.toLocaleString()}`}/>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#27272a" />
                    <Tooltip contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a" }} itemStyle={{ color: "#fafafa" }} formatter={(v: any) => `$${v.toLocaleString()}`}/>
                    <Area type="monotone" dataKey="total_value" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorVal)" />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card className="flex items-center justify-center border-dashed bg-card/50">
            <div className="text-center p-12 text-muted-foreground">
              <FlaskConical className="mx-auto h-12 w-12 opacity-20 mb-4" />
              <h3 className="text-lg font-medium text-foreground">No Results Yet</h3>
              <p className="text-sm">Configure and run a simulation to see performance metrics.</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
