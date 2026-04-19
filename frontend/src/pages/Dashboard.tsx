import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { DollarSign, Percent, ShieldCheck, Database, History, TrendingUp, RefreshCw } from "lucide-react";
import { usePortfolio, useSystemStatus, useMonteCarlo } from "@/api/queries";
import { format } from "date-fns";

export function Dashboard() {
  const profile = useStore((state) => state.profile);
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(profile);
  const { data: status, isLoading: statusLoading } = useSystemStatus(profile);
  const { data: mc, refetch: runMC, isFetching: mcFetching } = useMonteCarlo(profile);

  if (portfolioLoading || statusLoading || !portfolio) return <div className="p-8 text-muted-foreground animate-pulse">Loading dashboard...</div>;

  const totalValue = portfolio.total_value || 0;
  const pnlPct = portfolio.pnl_pct || 0;
  const isPositive = pnlPct >= 0;

  const history = portfolio.history || [];

  const healthStatus = status?.health?.status || "unknown";

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold tracking-tight">Executive Dashboard</h2>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-3 py-1 bg-secondary rounded-full">
            <Database className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">Profile: {profile.toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              {healthStatus === "up" && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${healthStatus === "up" ? "bg-emerald-500" : "bg-destructive"}`}></span>
            </span>
            <span className="text-xs font-medium text-muted-foreground uppercase">{healthStatus}</span>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Portfolio Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            <p className="text-xs text-muted-foreground">Peak: ${portfolio.peak_value?.toLocaleString()}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Net P&L</CardTitle>
            <Percent className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive ? "text-emerald-500" : "text-destructive"}`}>
              {isPositive ? "+" : ""}{(pnlPct * 100).toFixed(2)}%
            </div>
            <p className="text-xs text-muted-foreground">${portfolio.pnl_dollars?.toLocaleString()} net</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Last Rebalance</CardTitle>
            <History className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold truncate">
              {status?.last_rebalance?.timestamp ? format(new Date(status.last_rebalance.timestamp), "MMM dd, HH:mm") : "None"}
            </div>
            <p className="text-xs text-muted-foreground">{status?.last_rebalance?.strategy || "No strategy run"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Reconciliation</CardTitle>
            <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-xl font-bold uppercase">
              {status?.last_reconciliation?.status || "Pending"}
            </div>
            <p className="text-xs text-muted-foreground">
              {status?.last_reconciliation?.breaks_count === 0 ? "Perfect Match" : `${status?.last_reconciliation?.breaks_count} Breaks Found`}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Equity Curve</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px]">
            {history.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" stroke="#52525b" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis 
                    stroke="#52525b" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    tickFormatter={(value) => `$${value.toLocaleString()}`}
                    domain={['auto', 'auto']}
                  />
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#27272a" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", borderRadius: "8px" }}
                    itemStyle={{ color: "#fafafa" }}
                    formatter={(value: any) => [`$${value.toLocaleString()}`, "Value"]}
                  />
                  <Area type="monotone" dataKey="total_value" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorValue)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground bg-secondary/10 rounded-lg border border-dashed">
                <TrendingUp className="h-10 w-10 opacity-20 mb-2" />
                <p className="text-sm">No performance history yet. Runs several rebalancing cycles to see the curve.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="col-span-3">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Monte Carlo Projection</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">90-day forward distribution</p>
            </div>
            <button 
              onClick={() => runMC()} 
              disabled={mcFetching}
              className="text-xs bg-primary text-primary-foreground px-2 py-1 rounded hover:bg-primary/90 disabled:opacity-50"
            >
              {mcFetching ? "Running..." : "Simulate"}
            </button>
          </CardHeader>
          <CardContent className="min-h-[300px] flex flex-col">
            {mcFetching ? (
              <div className="flex-1 flex flex-col items-center justify-center py-12 text-muted-foreground animate-pulse">
                <RefreshCw className="h-8 w-8 animate-spin mb-4 opacity-20" />
                <p className="text-sm">Simulating 1,000 forward paths...</p>
              </div>
            ) : mc ? (
              <div className="space-y-6 pt-4 flex-1">
                <div className="flex flex-col items-center justify-center text-center">
                  <TrendingUp className="h-8 w-8 text-emerald-500 mb-2" />
                  <span className="text-sm font-medium text-muted-foreground">Expected Value (252d)</span>
                  <span className="text-3xl font-bold">${mc.expected_value?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1 p-3 bg-secondary/20 rounded-lg border border-border">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">95% Low</span>
                    <div className="text-sm font-bold text-destructive">${mc.var_95?.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                  </div>
                  <div className="space-y-1 p-3 bg-secondary/20 rounded-lg border border-border">
                    <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider">95% High</span>
                    <div className="text-sm font-bold text-emerald-500">${mc.percentiles?.["p95"] ? mc.percentiles["p95"].toLocaleString(undefined, { maximumFractionDigits: 0 }) : mc.percentiles?.["95"]?.toLocaleString()}</div>
                  </div>
                </div>

                <div className="border-t border-border pt-4">
                  <div className="flex justify-between text-xs mb-3">
                    <span className="text-muted-foreground font-medium uppercase tracking-tighter">Distribution Percentiles</span>
                  </div>
                  <div className="grid grid-cols-5 gap-1 text-[10px] text-center font-mono">
                    <div className="flex flex-col gap-1"><span className="opacity-50">5%</span><span className="font-bold">{(mc.percentiles?.["p5"] || mc.percentiles?.["5"] || 0) > 0 ? ((mc.percentiles?.["p5"] || mc.percentiles?.["5"]) / 1000).toFixed(0) : "-"}k</span></div>
                    <div className="flex flex-col gap-1"><span className="opacity-50">25%</span><span className="font-bold">{(mc.percentiles?.["p25"] || mc.percentiles?.["25"] || 0) > 0 ? ((mc.percentiles?.["p25"] || mc.percentiles?.["25"]) / 1000).toFixed(0) : "-"}k</span></div>
                    <div className="flex flex-col gap-1"><span className="bg-primary/10 rounded py-0.5 px-1 underline underline-offset-2">50%</span><span className="font-bold">{(mc.percentiles?.["p50"] || mc.percentiles?.["50"] || 0) > 0 ? ((mc.percentiles?.["p50"] || mc.percentiles?.["50"]) / 1000).toFixed(0) : "-"}k</span></div>
                    <div className="flex flex-col gap-1"><span className="opacity-50">75%</span><span className="font-bold">{(mc.percentiles?.["p75"] || mc.percentiles?.["75"] || 0) > 0 ? ((mc.percentiles?.["p75"] || mc.percentiles?.["75"]) / 1000).toFixed(0) : "-"}k</span></div>
                    <div className="flex flex-col gap-1"><span className="opacity-50">95%</span><span className="font-bold">{(mc.percentiles?.["p95"] || mc.percentiles?.["95"] || 0) > 0 ? ((mc.percentiles?.["p95"] || mc.percentiles?.["95"]) / 1000).toFixed(0) : "-"}k</span></div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center py-12 text-muted-foreground opacity-50">
                <TrendingUp className="h-12 w-12 mb-4" />
                <p className="text-sm text-center">Run a forward simulation to estimate future value distribution.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
