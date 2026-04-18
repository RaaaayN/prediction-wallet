import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Database } from "lucide-react";

export function DataExplorer() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Data Explorer</h2>
          <p className="text-muted-foreground mt-1">Inspect Parquet Data Lake (Bronze/Silver/Gold) and Market Features.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Database className="h-4 w-4 text-amber-600" /> Bronze Layer</CardTitle>
            <CardDescription>Raw ingested snapshots</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm space-y-2">
              <div className="flex justify-between"><span>AAPL.parquet</span><span className="text-muted-foreground">2.1 MB</span></div>
              <div className="flex justify-between"><span>MSFT.parquet</span><span className="text-muted-foreground">1.8 MB</span></div>
              <div className="flex justify-between"><span>BTC-USD.parquet</span><span className="text-muted-foreground">4.5 MB</span></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Database className="h-4 w-4 text-gray-400" /> Silver Layer</CardTitle>
            <CardDescription>Cleaned data & signals</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm space-y-2">
              <div className="flex justify-between"><span>AAPL_features.parquet</span><span className="text-muted-foreground">3.2 MB</span></div>
              <div className="flex justify-between"><span>sentiment_latest.parquet</span><span className="text-emerald-500 text-xs px-2 rounded-full bg-emerald-500/10">Fresh</span></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Database className="h-4 w-4 text-yellow-500" /> Gold Layer</CardTitle>
            <CardDescription>Strategy-ready datasets (DVC Versioned)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-sm space-y-2">
              <div className="flex flex-col">
                <span className="font-medium">baseline_2024_v1</span>
                <span className="text-xs text-muted-foreground break-all">Hash: 8b2a3c...</span>
              </div>
              <div className="flex flex-col mt-2">
                <span className="font-medium">ensemble_test_v2</span>
                <span className="text-xs text-muted-foreground break-all">Hash: e9f1a2...</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
