import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { usePortfolio, useMarketSnapshot } from "@/api/queries";
import { AlertCircle, TrendingUp, TrendingDown } from "lucide-react";

const COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#6366f1', '#ec4899', '#f43f5e', '#f59e0b', '#eab308'];

export function Portfolio() {
  const profile = useStore((state) => state.profile);
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio(profile);
  const { data: market, isLoading: marketLoading } = useMarketSnapshot(profile);

  const isLoading = portfolioLoading || marketLoading;

  if (isLoading) return <div className="p-8 text-muted-foreground animate-pulse">Loading portfolio...</div>;

  if (!portfolio || !portfolio.positions || Object.keys(portfolio.positions).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
        <AlertCircle className="h-12 w-12 mb-4 opacity-20" />
        <h3 className="text-xl font-bold text-foreground">Portfolio Empty</h3>
        <p className="max-w-md text-center mt-2">No active positions found for {profile.toUpperCase()}. Go to Settings to initialize the fund or run an agent cycle.</p>
      </div>
    );
  }

  const weightsData = Object.entries(portfolio.current_weights || {}).map(([ticker, weight]) => ({
    name: ticker,
    value: (weight as number) * 100,
  }));

  const cashWeight = (portfolio.cash / portfolio.total_value) * 100;
  if (cashWeight > 0.01) {
    weightsData.push({ name: "CASH", value: cashWeight });
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold tracking-tight">Portfolio Allocation</h2>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Current Weights</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px] flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={weightsData}
                  cx="50%"
                  cy="50%"
                  innerRadius={80}
                  outerRadius={120}
                  paddingAngle={2}
                  dataKey="value"
                  stroke="none"
                >
                  {weightsData.map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value: any) => [`${value.toFixed(2)}%`, "Allocation"]}
                  contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a", borderRadius: "8px" }}
                />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Drift Analysis</CardTitle>
          </CardHeader>
          <CardContent className="h-[350px] overflow-auto pr-2">
            <div className="space-y-4">
              {Object.entries(portfolio.target_weights || {}).map(([ticker, targetW]) => {
                const currentW = portfolio.current_weights[ticker] || 0;
                const target = (targetW as number) * 100;
                const current = currentW * 100;
                const drift = current - target;
                const isOverweight = drift > 0;
                
                return (
                  <div key={ticker} className="flex flex-col space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium">{ticker}</span>
                      <span className={`${Math.abs(drift) > 5 ? "text-amber-500 font-bold" : "text-muted-foreground"}`}>
                        {current.toFixed(1)}% / {target.toFixed(1)}% (Drift: {drift > 0 ? "+" : ""}{drift.toFixed(2)}%)
                      </span>
                    </div>
                    <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden flex">
                      <div className="h-full bg-emerald-500" style={{ width: `${Math.min(current, target)}%` }} />
                      {isOverweight && (
                        <div className="h-full bg-amber-500" style={{ width: `${drift}%` }} />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Detailed Holdings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="border border-border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="py-2 px-4 text-left">Ticker</th>
                  <th className="py-2 px-4 text-right">Quantity</th>
                  <th className="py-2 px-4 text-right">Avg Cost</th>
                  <th className="py-2 px-4 text-right">Last Price</th>
                  <th className="py-2 px-4 text-right">Market Value</th>
                  <th className="py-2 px-4 text-right">Weight</th>
                  <th className="py-2 px-4 text-right">P&L (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {Object.entries(portfolio.positions).map(([ticker, qty]) => {
                  const avgCost = portfolio.average_costs?.[ticker] || 0;
                  const price = market?.prices?.[ticker] || 0;
                  const mktValue = qty * price;
                  const weight = (mktValue / portfolio.total_value) * 100;
                  const pnlPct = avgCost > 0 ? ((price / avgCost) - 1) * 100 : 0;
                  
                  return (
                    <tr key={ticker} className="hover:bg-secondary/20 transition-colors">
                      <td className="py-2 px-4 font-mono font-bold text-xs">{ticker}</td>
                      <td className="py-2 px-4 text-right font-mono">{qty.toFixed(4)}</td>
                      <td className="py-2 px-4 text-right font-mono">${avgCost.toFixed(2)}</td>
                      <td className="py-2 px-4 text-right font-mono">${price.toFixed(2)}</td>
                      <td className="py-2 px-4 text-right font-mono">${mktValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                      <td className="py-2 px-4 text-right font-mono">{weight.toFixed(2)}%</td>
                      <td className={`py-2 px-4 text-right font-mono font-bold ${pnlPct >= 0 ? 'text-emerald-500' : 'text-destructive'}`}>
                        <div className="flex items-center justify-end gap-1">
                          {pnlPct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                          {pnlPct.toFixed(2)}%
                        </div>
                      </td>
                    </tr>
                  );
                })}
                <tr className="bg-secondary/30 font-bold">
                   <td className="py-2 px-4">CASH</td>
                   <td className="py-2 px-4 text-right font-mono" colSpan={3}>-</td>
                   <td className="py-2 px-4 text-right font-mono">${portfolio.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                   <td className="py-2 px-4 text-right font-mono">{(portfolio.cash / portfolio.total_value * 100).toFixed(2)}%</td>
                   <td className="py-2 px-4 text-right">-</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
