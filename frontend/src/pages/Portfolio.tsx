import { useQuery } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import { apiClient } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

const COLORS = ['#10b981', '#3b82f6', '#8b5cf6', '#6366f1', '#ec4899', '#f43f5e', '#f59e0b', '#eab308'];

export function Portfolio() {
  const profile = useStore((state) => state.profile);
  const { data: portfolio, isLoading } = useQuery({
    queryKey: ["portfolio", profile],
    queryFn: async () => (await apiClient.get(`/portfolio?profile=${profile}`)).data,
  });

  if (isLoading || !portfolio) return <div className="p-8 text-muted-foreground">Loading portfolio...</div>;

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
          <CardContent>
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
                    <div className="h-2 w-full bg-secondary rounded-full overflow-hidden flex">
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
    </div>
  );
}
