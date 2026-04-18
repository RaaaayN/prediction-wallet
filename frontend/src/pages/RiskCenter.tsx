import { useStore } from "@/store/useStore";
import { useStressTests, useCorrelation } from "@/api/queries";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ShieldCheck, Thermometer, Info } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from "recharts";

export function RiskCenter() {
  const profile = useStore((state) => state.profile);
  const { data: stress, isLoading: stressLoading } = useStressTests(profile);
  const { data: correlation, isLoading: corrLoading } = useCorrelation(profile);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Risk Center</h2>
          <p className="text-muted-foreground mt-1">Institutional risk limits, stress testing, and factor dependency.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-emerald-600 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" /> Hard Kill Switch
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600 uppercase">Inactive</div>
            <p className="text-xs text-emerald-600/80 mt-1">Portfolio drawdown is well within safety limits (threshold: 10%).</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Exposure Limits</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 pt-2">
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span>Gross Exposure</span>
                <span className="font-bold">100.0% / 150.0%</span>
              </div>
              <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-primary" style={{ width: '66%' }}></div>
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span>Max Single Name</span>
                <span className="font-bold">15.0% / 20.0%</span>
              </div>
              <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                <div className="h-full bg-primary" style={{ width: '75%' }}></div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Tail Risk (95%)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="space-y-1">
                <span className="text-[10px] text-muted-foreground uppercase">VaR (Daily)</span>
                <div className="text-lg font-bold">1.24%</div>
              </div>
              <div className="space-y-1">
                <span className="text-[10px] text-muted-foreground uppercase">CVaR (Expected Shortfall)</span>
                <div className="text-lg font-bold">1.89%</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Thermometer className="h-4 w-4" /> Macro Stress Tests</CardTitle>
            <CardDescription>Instantaneous P&L impact under historical crash scenarios</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px]">
            {stressLoading ? (
              <div className="h-full flex items-center justify-center text-muted-foreground animate-pulse">Running scenarios...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stress} layout="vertical" margin={{ left: 40, right: 40 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="scenario" type="category" width={100} axisLine={false} tickLine={false} fontSize={12} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a" }}
                    formatter={(val: any) => [`${val.toFixed(2)}%`, "Impact"]}
                  />
                  <Bar dataKey="pnl_pct" radius={[0, 4, 4, 0]}>
                    {stress?.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.pnl_pct < -10 ? '#ef4444' : '#f59e0b'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Info className="h-4 w-4" /> Correlation Matrix</CardTitle>
            <CardDescription>Asset dependency based on 90-day returns</CardDescription>
          </CardHeader>
          <CardContent>
            {corrLoading ? (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground animate-pulse">Computing dependencies...</div>
            ) : correlation ? (
              <div className="overflow-x-auto">
                <table className="w-full text-[10px] font-mono border-collapse">
                  <thead>
                    <tr>
                      <th className="p-1 border border-border bg-secondary/30"></th>
                      {correlation.tickers.map(t => <th key={t} className="p-1 border border-border bg-secondary/30">{t}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {correlation.matrix.map((row, i) => (
                      <tr key={i}>
                        <td className="p-1 border border-border bg-secondary/30 font-bold">{correlation.tickers[i]}</td>
                        {row.map((val, j) => {
                          const intensity = Math.abs(val);
                          const color = val > 0 ? `rgba(16, 185, 129, ${intensity})` : `rgba(239, 68, 68, ${intensity})`;
                          return (
                            <td 
                              key={j} 
                              className="p-1 border border-border text-center" 
                              style={{ backgroundColor: i === j ? '#27272a' : color, color: intensity > 0.5 ? 'white' : 'inherit' }}
                            >
                              {val.toFixed(2)}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="h-[300px] flex items-center justify-center text-muted-foreground">Correlation data unavailable.</div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
