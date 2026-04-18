import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ShieldCheck } from "lucide-react";

export function RiskCenter() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Risk Center</h2>
          <p className="text-muted-foreground mt-1">Monitor institutional risk limits and tail-risk metrics.</p>
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
            <div className="text-2xl font-bold text-emerald-600">INACTIVE</div>
            <p className="text-xs text-emerald-600/80 mt-1">Current drawdown is well below 10% threshold.</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Max Single Ticker Cap</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">20.0%</div>
            <div className="w-full h-2 bg-secondary mt-2 rounded-full overflow-hidden">
              <div className="h-full bg-primary w-[75%]"></div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">Highest exposure: AAPL (15.0%)</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Max Sector Concentration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">55.0%</div>
            <div className="w-full h-2 bg-secondary mt-2 rounded-full overflow-hidden">
              <div className="h-full bg-primary w-[80%]"></div>
            </div>
            <p className="text-xs text-muted-foreground mt-2">Highest sector: Technology (44.0%)</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tail Risk Metrics (Basel III Aligned)</CardTitle>
          <CardDescription>Value at Risk and Expected Shortfall</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="flex flex-col space-y-2">
              <span className="text-sm font-medium text-muted-foreground">Correlation-Adjusted VaR (95%)</span>
              <span className="text-3xl font-bold">1.24%</span>
              <span className="text-xs text-muted-foreground">Daily expected max loss</span>
            </div>
            <div className="flex flex-col space-y-2">
              <span className="text-sm font-medium text-muted-foreground">Conditional VaR / CVaR (95%)</span>
              <span className="text-3xl font-bold">1.89%</span>
              <span className="text-xs text-muted-foreground">Average loss beyond VaR threshold</span>
            </div>
            <div className="flex flex-col space-y-2">
              <span className="text-sm font-medium text-muted-foreground">Gross Exposure</span>
              <span className="text-3xl font-bold text-amber-500">100.0%</span>
              <span className="text-xs text-muted-foreground">Limit: 150.0%</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
