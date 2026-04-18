import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TestTube, ExternalLink } from "lucide-react";

export function Experiments() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Experiments (MLflow)</h2>
          <p className="text-muted-foreground mt-1">View tracked research runs and model registry.</p>
        </div>
        <Button variant="outline" onClick={() => window.open('http://localhost:5000', '_blank')}>
          <ExternalLink className="mr-2 h-4 w-4" />
          Open MLflow UI
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Model Registry: Champions</CardTitle>
          <CardDescription>Strategies promoted to production</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="border border-border rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50 text-secondary-foreground border-b border-border">
                <tr>
                  <th className="py-3 px-4 text-left font-medium">Model Name</th>
                  <th className="py-3 px-4 text-left font-medium">Version</th>
                  <th className="py-3 px-4 text-left font-medium">Stage</th>
                  <th className="py-3 px-4 text-left font-medium">Run ID</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                <tr>
                  <td className="py-3 px-4 font-medium">Rebalancing_Strategy</td>
                  <td className="py-3 px-4">v3</td>
                  <td className="py-3 px-4"><span className="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-500 rounded-full">Production</span></td>
                  <td className="py-3 px-4 text-muted-foreground font-mono text-xs">8b2a3c9f</td>
                </tr>
                <tr>
                  <td className="py-3 px-4 font-medium">Ensemble_NLP_Overlay</td>
                  <td className="py-3 px-4">v1</td>
                  <td className="py-3 px-4"><span className="text-xs px-2 py-1 bg-amber-500/20 text-amber-500 rounded-full">Staging</span></td>
                  <td className="py-3 px-4 text-muted-foreground font-mono text-xs">e9f1a2b4</td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Runs</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center py-12 border-dashed border border-border m-6 rounded-md">
          <div className="text-center text-muted-foreground">
            <TestTube className="mx-auto h-12 w-12 opacity-20 mb-4" />
            <p>Runs are fetched via MLflow API. View full details in the MLflow UI.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
