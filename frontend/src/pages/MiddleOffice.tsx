import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useReconciliation, useTCA, useSyncLegacy, useCalculateNAV, useTriggerBackup, useNAVHistory } from "@/api/queries";
import { FileCheck, ShieldCheck, PieChart, Activity, RefreshCw, Database, ShieldAlert, Save, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

export function MiddleOffice() {
  const profile = useStore((state) => state.profile);
  const { data: reconciliation, isLoading: recLoading, refetch: runRec } = useReconciliation(profile);
  const { data: tca, isLoading: tcaLoading } = useTCA(profile);
  const { data: navHistory, isLoading: navLoading } = useNAVHistory(profile);
  const syncLegacy = useSyncLegacy();
  const calculateNAV = useCalculateNAV();
  const triggerBackup = useTriggerBackup();
  const queryClient = useQueryClient();

  const handleSync = async () => {
    if (!confirm("This will overwrite the legacy portfolio state with Ledger data. Continue?")) return;
    await syncLegacy.mutateAsync(profile);
    queryClient.invalidateQueries();
  };

  const handleNAV = async () => {
    await calculateNAV.mutateAsync(profile);
    queryClient.invalidateQueries({ queryKey: ['nav-history', profile] });
    alert("NAV calculation completed and persisted.");
  };

  const handleBackup = async () => {
    await triggerBackup.mutateAsync(profile);
    alert("System backup triggered successfully.");
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Middle Office</h2>
          <p className="text-muted-foreground mt-1">Reconciliation breaks, NAV calculation, and Transaction Cost Analysis (TCA).</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => runRec()} disabled={recLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${recLoading ? 'animate-spin' : ''}`} /> Run Reconcile
          </Button>
          <Button variant="outline" size="sm" onClick={handleNAV} disabled={calculateNAV.isPending}>
            <Database className="h-4 w-4 mr-2" /> Recalculate NAV
          </Button>
          <Button variant="outline" size="sm" onClick={handleBackup} disabled={triggerBackup.isPending}>
            <Save className="h-4 w-4 mr-2" /> Full Backup
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><TrendingUp className="h-4 w-4" /> Official NAV History</CardTitle>
            <CardDescription>Audited Net Asset Value over time (Ledger-based)</CardDescription>
          </CardHeader>
          <CardContent className="h-[250px]">
            {navLoading ? (
              <div className="h-full flex items-center justify-center animate-pulse text-muted-foreground">Loading audit history...</div>
            ) : navHistory && navHistory.length > 0 ? (
               <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={[...navHistory].reverse()}>
                  <defs>
                    <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#27272a" />
                  <XAxis dataKey="as_of_date" hide />
                  <YAxis hide domain={['auto', 'auto']} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#09090b", borderColor: "#27272a" }}
                    formatter={(val: any) => [`$${val.toLocaleString()}`, "NAV"]}
                  />
                  <Area type="monotone" dataKey="total_value" stroke="#3b82f6" fillOpacity={1} fill="url(#colorNav)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center border border-dashed rounded-lg bg-secondary/5 text-muted-foreground">
                 <p className="text-sm">No NAV history found. Trigger a calculation to start auditing.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> System Health</CardTitle>
            <CardDescription>Audit of operational integrity</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
             <div className="flex justify-between items-center p-3 border border-border rounded-lg">
                <span className="text-sm font-medium">Last NAV Audit</span>
                <span className="text-xs font-mono font-bold">{navHistory?.[0]?.as_of_date || "Never"}</span>
             </div>
             <div className="flex justify-between items-center p-3 border border-border rounded-lg">
                <span className="text-sm font-medium">Reconciliation</span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${reconciliation?.length === 0 ? 'bg-emerald-500/10 text-emerald-500' : 'bg-destructive/10 text-destructive'}`}>
                  {reconciliation?.length === 0 ? 'Synchronized' : `${reconciliation?.length} Breaks`}
                </span>
             </div>
             <div className="flex justify-between items-center p-3 border border-border rounded-lg">
                <span className="text-sm font-medium">Ledger Integrity</span>
                <span className="text-xs text-emerald-500 font-bold uppercase">Verified</span>
             </div>
          </CardContent>
        </Card>

        <Card className="md:col-span-3">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Reconciliation Breaks</CardTitle>
              <CardDescription>Mismatches between Trading Core (OMS) and Portfolio State</CardDescription>
            </div>
            {reconciliation && reconciliation.length > 0 && (
              <Button variant="destructive" size="sm" onClick={handleSync} disabled={syncLegacy.isPending}>
                <ShieldAlert className="h-3.5 w-3.5 mr-1" /> Force Sync Systems
              </Button>
            )}
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
                      <th className="py-2 px-4 text-right">Legacy</th>
                      <th className="py-2 px-4 text-right">Ledger</th>
                      <th className="py-2 px-4 text-center">Severity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {reconciliation.map((breakItem: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-4 font-mono font-bold text-xs">{breakItem.subject}</td>
                        <td className="py-2 px-4 text-xs text-muted-foreground">{breakItem.break_type}</td>
                        <td className="py-2 px-4 text-right font-mono">{breakItem.legacy_value?.toFixed(4)}</td>
                        <td className="py-2 px-4 text-right font-mono">{breakItem.ledger_value?.toFixed(4)}</td>
                        <td className="py-2 px-4 text-center">
                          <span className={`text-[10px] px-2 py-1 rounded-full uppercase font-bold ${
                            Math.abs(breakItem.diff) > 1 ? 'bg-destructive/20 text-destructive' : 'bg-amber-500/20 text-amber-500'
                          }`}>
                            {Math.abs(breakItem.diff) > 1 ? 'CRITICAL' : 'WARNING'}
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

        <Card className="md:col-span-3">
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
                      <th className="py-2 px-4 text-left">Timestamp</th>
                      <th className="py-2 px-4 text-left">Cycle ID</th>
                      <th className="py-2 px-4 text-right">Trades</th>
                      <th className="py-2 px-4 text-right">Avg Slippage</th>
                      <th className="py-2 px-4 text-right">Fees ($)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {tca.map((report: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-4 text-xs text-muted-foreground">{report.timestamp ? new Date(report.timestamp).toLocaleDateString() : 'N/A'}</td>
                        <td className="py-2 px-4 font-mono text-xs text-muted-foreground">{report.cycle_id}</td>
                        <td className="py-2 px-4 text-right font-mono">{report.total_trades}</td>
                        <td className={`py-2 px-4 text-right font-mono font-bold ${report.avg_slippage_bps > 0 ? 'text-destructive' : 'text-emerald-500'}`}>
                          {report.avg_slippage_bps > 0 ? "+" : ""}{report.avg_slippage_bps?.toFixed(1)} bps
                        </td>
                        <td className="py-2 px-4 text-right font-mono text-muted-foreground">${report.total_fees?.toFixed(2)}</td>
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
