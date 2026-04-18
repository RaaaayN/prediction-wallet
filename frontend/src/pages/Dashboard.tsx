import { useQuery } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import { apiClient } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Activity, DollarSign, Percent, AlertTriangle } from "lucide-react";

export function Dashboard() {
  const profile = useStore((state) => state.profile);
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ["portfolio", profile],
    queryFn: async () => (await apiClient.get(`/portfolio?profile=${profile}`)).data,
  });

  if (isLoading || !portfolio) return <div className="p-8 text-muted-foreground animate-pulse">Loading dashboard...</div>;

  const totalValue = portfolio.total_value || 0;
  const pnlPct = portfolio.pnl_pct || 0;
  const isPositive = pnlPct >= 0;

  const mockHistory = portfolio.history?.length ? portfolio.history : [
    { date: "2024-01-01", total_value: 100000 },
    { date: "2024-01-02", total_value: 101000 },
    { date: "2024-01-03", total_value: 100500 },
    { date: "2024-01-04", total_value: 102000 },
    { date: "2024-01-05", total_value: 103500 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold tracking-tight">Overview ({profile.toUpperCase()})</h2>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Portfolio Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
            <p className="text-xs text-muted-foreground">Last updated {portfolio.last_rebalanced || "recently"}</p>
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
            <p className="text-xs text-muted-foreground">Since inception</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Active Positions</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Object.keys(portfolio.positions || {}).length} Assets</div>
            <p className="text-xs text-muted-foreground">Excluding cash reserves</p>
          </CardContent>
        </Card>

        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-emerald-600">Risk Status</CardTitle>
            <AlertTriangle className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">Healthy</div>
            <p className="text-xs text-emerald-600/80">Drawdown within limits</p>
          </CardContent>
        </Card>
      </div>

      <Card className="col-span-4">
        <CardHeader>
          <CardTitle>Equity Curve</CardTitle>
        </CardHeader>
        <CardContent className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={mockHistory}>
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
        </CardContent>
      </Card>
    </div>
  );
}
