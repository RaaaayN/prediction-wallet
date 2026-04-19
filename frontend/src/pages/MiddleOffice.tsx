import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useReconciliation, useTCA } from "@/api/queries";
import { FileCheck, ShieldCheck, PieChart, Activity } from "lucide-react";

export function MiddleOffice() {
  const profile = useStore((state) => state.profile);
  const { data: reconciliation, isLoading: recLoading } = useReconciliation(profile);
  const { data: tca, isLoading: tcaLoading } = useTCA(profile);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Middle Office</h2>
          <p className="text-muted-foreground mt-1">Reconciliation breaks, NAV calculation, and Transaction Cost Analysis (TCA).</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Reconciliation Breaks</CardTitle>
            <CardDescription>Mismatches between Trading Core (OMS) and Portfolio State</CardDescription>
          </CardHeader>
          <CardContent>
            {recLoading ? (
              <div className="text-center py-6 text-muted-foreground animate-pulse">Running reconciliation...</div>
            ) : reconciliation && reconciliation.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left">Ticker</th>
                      <th className="py-2 px-4 text-left">Break Type</th>
                      <th className="py-2 px-4 text-right">Expected</th>
                      <th className="py-2 px-4 text-right">Actual</th>
                      <th className="py-2 px-4 text-center">Severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {reconciliation.map((breakItem: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-4 font-mono font-bold text-xs">{breakItem.ticker}</td>
                        <td className="py-2 px-4 text-xs text-muted-foreground">{breakItem.break_type}</td>
                        <td className="py-2 px-4 text-right font-mono">{breakItem.expected_value}</td>
                        <td className="py-2 px-4 text-right font-mono">{breakItem.actual_value}</td>
                        <td className="py-2 px-4 text-center">
                          <span className={`text-[10px] px-2 py-1 rounded-full uppercase font-bold ${
                            breakItem.severity === 'CRITICAL' ? 'bg-destructive/20 text-destructive' : 
                            breakItem.severity === 'HIGH' ? 'bg-amber-500/20 text-amber-500' : 'bg-blue-500/20 text-blue-500'
                          }`}>
                            {breakItem.severity}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
               <div className="text-center py-12 border border-dashed border-emerald-500/30 bg-emerald-500/5 rounded-lg">
                <FileCheck className="mx-auto h-12 w-12 text-emerald-500/50 mb-4" />
                <h3 className="text-lg font-medium text-emerald-500">Perfect Match</h3>
                <p className="text-sm text-muted-foreground mt-1">No reconciliation breaks found between systems.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><PieChart className="h-4 w-4" /> Transaction Cost Analysis (TCA)</CardTitle>
            <CardDescription>Execution quality and slippage against arrival price</CardDescription>
          </CardHeader>
          <CardContent>
             {tcaLoading ? (
              <div className="text-center py-6 text-muted-foreground animate-pulse">Calculating TCA...</div>
            ) : tca && tca.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left">Cycle ID</th>
                      <th className="py-2 px-4 text-left">Ticker</th>
                      <th className="py-2 px-4 text-right">Arrival Price</th>
                      <th className="py-2 px-4 text-right">Fill Price</th>
                      <th className="py-2 px-4 text-right">Slippage (bps)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {tca.map((report: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-4 font-mono text-xs text-muted-foreground">{report.cycle_id}</td>
                        <td className="py-2 px-4 font-mono font-bold text-xs">{report.ticker}</td>
                        <td className="py-2 px-4 text-right font-mono">${report.arrival_price?.toFixed(2)}</td>
                        <td className="py-2 px-4 text-right font-mono">${report.fill_price?.toFixed(2)}</td>
                        <td className={`py-2 px-4 text-right font-mono font-bold ${report.slippage_bps > 0 ? 'text-destructive' : 'text-emerald-500'}`}>
                          {report.slippage_bps > 0 ? "+" : ""}{report.slippage_bps?.toFixed(1)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground border border-dashed border-border rounded-lg">
                <Activity className="mx-auto h-12 w-12 opacity-20 mb-4" />
                <p>No recent executions available for TCA.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
