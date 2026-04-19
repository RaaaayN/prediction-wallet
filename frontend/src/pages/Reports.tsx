import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, AlertCircle, Download, Clock, RefreshCw, CheckCircle2 } from "lucide-react";
import { useStore } from "@/store/useStore";
import { useGovernanceReport, useReports, useGenerateReport } from "@/api/queries";
import { format } from "date-fns";
import { useQueryClient } from "@tanstack/react-query";

export function Reports() {
  const profile = useStore((state) => state.profile);
  const { data: gov, isLoading: govLoading, error: govError } = useGovernanceReport(profile);
  const { data: reports, isLoading: reportsLoading } = useReports(profile);
  const generateReport = useGenerateReport();
  const queryClient = useQueryClient();

  const handleGenerate = async () => {
    await generateReport.mutateAsync({ profile });
    queryClient.invalidateQueries({ queryKey: ['reports', profile] });
  };

  const govErrorMessage = govError instanceof Error ? govError.message : null;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Reports & Compliance</h2>
          <p className="text-muted-foreground mt-1">Institutional governance audits and automated PDF report generation.</p>
        </div>
        <Button onClick={handleGenerate} disabled={generateReport.isPending}>
          {generateReport.isPending ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <FileText className="mr-2 h-4 w-4" />}
          Generate New Report
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Governance Status</CardTitle>
            <CardDescription>Compliance audit summary</CardDescription>
          </CardHeader>
          <CardContent>
            {govLoading ? (
              <div className="animate-pulse space-y-4">
                <div className="h-12 bg-secondary/50 rounded-lg"></div>
                <div className="h-12 bg-secondary/50 rounded-lg"></div>
              </div>
            ) : govErrorMessage ? (
              <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>Error: {govErrorMessage}</span>
              </div>
            ) : gov ? (
              <div className="space-y-4">
                <div className="border border-border p-4 rounded-lg bg-secondary/10">
                  <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-1">Data Lineage</div>
                  <div className="text-lg font-bold text-emerald-500 uppercase">{gov.data_lineage_status || "Healthy"}</div>
                </div>
                <div className="border border-border p-4 rounded-lg bg-secondary/10">
                  <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-1">Risk Violations</div>
                  <div className={`text-lg font-bold ${gov.risk_violations_count > 0 ? 'text-amber-500' : 'text-emerald-500'}`}>
                    {gov.risk_violations_count || 0}
                  </div>
                </div>
                <div className="border border-border p-4 rounded-lg bg-secondary/10">
                   <div className="text-[10px] text-muted-foreground uppercase font-bold tracking-wider mb-1">Active Champion</div>
                   <div className="text-sm font-mono truncate">{gov.champion_strategy || "None"}</div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground italic text-xs">
                No governance data available.
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Clock className="h-4 w-4" /> Generated PDF Reports</CardTitle>
            <CardDescription>Download and audit historical portfolio reports</CardDescription>
          </CardHeader>
          <CardContent>
            {reportsLoading ? (
              <div className="py-12 text-center text-muted-foreground animate-pulse">Scanning reports directory...</div>
            ) : reports && reports.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left font-bold">Filename</th>
                      <th className="py-2 px-4 text-left font-bold">Generated At</th>
                      <th className="py-2 px-4 text-right font-bold">Size</th>
                      <th className="py-2 px-4 text-right font-bold">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {reports.map((report) => (
                      <tr key={report.filename} className="hover:bg-secondary/20">
                        <td className="py-3 px-4 font-medium flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          {report.filename}
                        </td>
                        <td className="py-3 px-4 text-xs text-muted-foreground">
                          {format(new Date(report.created_at), "MMM dd, yyyy HH:mm")}
                        </td>
                        <td className="py-3 px-4 text-right text-xs font-mono">
                          {(report.size_bytes / 1024).toFixed(1)} KB
                        </td>
                        <td className="py-3 px-4 text-right">
                          <a 
                            href={report.url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline font-bold"
                          >
                            <Download className="h-3 w-3" /> Download
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-20 text-muted-foreground border border-dashed border-border rounded-lg bg-secondary/5">
                <FileText className="mx-auto h-12 w-12 opacity-20 mb-4" />
                <h3 className="text-lg font-medium text-foreground">No reports found</h3>
                <p className="max-w-xs mx-auto mt-2 text-sm">
                  Click "Generate New Report" to create your first institutional PDF audit.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
