import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function StrategyLab() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Strategy Lab</h2>
          <p className="text-muted-foreground mt-1">Configure and combine predictive signals.</p>
        </div>
        <Button>Create Strategy</Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Ensemble Strategy</CardTitle>
            <CardDescription>Quantitative Drift + NLP Sentiment</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center border-b border-border pb-2">
                <span className="text-sm font-medium">Status</span>
                <span className="text-xs px-2 py-1 bg-emerald-500/20 text-emerald-500 rounded-full">Active</span>
              </div>
              <div className="flex justify-between items-center border-b border-border pb-2">
                <span className="text-sm font-medium">Drift Threshold</span>
                <span className="text-sm text-muted-foreground">5.0%</span>
              </div>
              <div className="flex justify-between items-center border-b border-border pb-2">
                <span className="text-sm font-medium">Sentiment Weight</span>
                <span className="text-sm text-muted-foreground">20% (FinBERT)</span>
              </div>
            </div>
            <Button variant="outline" className="w-full mt-4">Edit Parameters</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Threshold Strategy</CardTitle>
            <CardDescription>Pure quantitative rebalancing</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center border-b border-border pb-2">
                <span className="text-sm font-medium">Status</span>
                <span className="text-xs px-2 py-1 bg-secondary text-secondary-foreground rounded-full">Inactive</span>
              </div>
              <div className="flex justify-between items-center border-b border-border pb-2">
                <span className="text-sm font-medium">Drift Threshold</span>
                <span className="text-sm text-muted-foreground">5.0%</span>
              </div>
            </div>
            <Button variant="outline" className="w-full mt-4">Edit Parameters</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
