import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";
import { useStore } from "@/store/useStore";

export function Reports() {
  const profile = useStore((state) => state.profile);
  
  const { data, isLoading } = useQuery({
    queryKey: ["governance", profile],
    queryFn: async () => {
      try {
        const res = await apiClient.get(`/audit/governance?profile=${profile}`);
        return res.data;
      } catch {
        return null;
      }
    },
    retry: false
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Reports & Compliance</h2>
          <p className="text-muted-foreground mt-1">Governance audits and PDF generation.</p>
        </div>
        <Button>Generate PDF Report</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Governance Report</CardTitle>
          <CardDescription>Latest compliance audit status</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="animate-pulse text-muted-foreground">Loading governance data...</div>
          ) : data ? (
            <div className="space-y-6">
              <div className="grid grid-cols-2 gap-4">
                <div className="border border-border p-4 rounded-lg bg-secondary/10">
                  <div className="text-sm text-muted-foreground mb-1">Data Lineage</div>
                  <div className="text-xl font-bold text-emerald-500 uppercase">{data.data_lineage_status || "Healthy"}</div>
                </div>
                <div className="border border-border p-4 rounded-lg bg-secondary/10">
                  <div className="text-sm text-muted-foreground mb-1">Recent Violations</div>
                  <div className={`text-xl font-bold ${data.risk_violations_count > 0 ? 'text-amber-500' : 'text-emerald-500'}`}>
                    {data.risk_violations_count || 0}
                  </div>
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium mb-2">Champion Strategy</h4>
                <div className="text-sm font-mono bg-secondary p-2 rounded">{data.champion_strategy || "None"}</div>
              </div>
            </div>
          ) : (
             <div className="text-center py-12 text-muted-foreground border border-dashed border-border rounded-lg">
              <FileText className="mx-auto h-12 w-12 opacity-20 mb-4" />
              <p>Governance endpoint not reachable or no data available.</p>
              <p className="text-xs mt-2">Run `python main.py governance-report` via CLI</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
