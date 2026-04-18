import { useStore } from "@/store/useStore";
import { useMarketSnapshot } from "@/api/queries";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Database, CheckCircle2, XCircle, Clock } from "lucide-react";
import { format } from "date-fns";

export function DataExplorer() {
  const profile = useStore((state) => state.profile);
  const { data: market, isLoading } = useMarketSnapshot(profile);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Data Explorer</h2>
          <p className="text-muted-foreground mt-1">Audit market data freshness, feature engineering, and Parquet Data Lake lineage.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        <Card className="md:col-span-3">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Clock className="h-4 w-4" /> Market Data Status</CardTitle>
            <CardDescription>Freshness monitoring for active universe tickers</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-12 text-center text-muted-foreground animate-pulse">Synchronizing with Data Lake...</div>
            ) : (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left font-medium">Ticker</th>
                      <th className="py-2 px-4 text-left font-medium">Last Refresh</th>
                      <th className="py-2 px-4 text-left font-medium">Price</th>
                      <th className="py-2 px-4 text-center font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {market?.refresh_status?.map((item) => (
                      <tr key={item.ticker}>
                        <td className="py-2 px-4 font-mono font-bold">{item.ticker}</td>
                        <td className="py-2 px-4 text-xs text-muted-foreground">
                          {item.refreshed_at ? format(new Date(item.refreshed_at), "MMM dd, HH:mm:ss") : "Never"}
                        </td>
                        <td className="py-2 px-4 font-mono">${market.prices[item.ticker]?.toFixed(2)}</td>
                        <td className="py-2 px-4 text-center">
                          {item.success ? (
                            <CheckCircle2 className="h-4 w-4 text-emerald-500 mx-auto" />
                          ) : (
                            <XCircle className="h-4 w-4 text-destructive mx-auto" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Database className="h-4 w-4" /> Lake Layers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <span className="text-xs font-bold text-amber-500 uppercase">Bronze (Raw)</span>
              <div className="p-2 border border-border rounded text-[10px] font-mono bg-secondary/20">
                /data/lake/bronze/*.parquet<br/>
                Retention: Indefinite
              </div>
            </div>
            <div className="space-y-2">
              <span className="text-xs font-bold text-gray-400 uppercase">Silver (Signals)</span>
              <div className="p-2 border border-border rounded text-[10px] font-mono bg-secondary/20">
                /data/lake/silver/*.parquet<br/>
                Features: RSI, SMA, FinBERT
              </div>
            </div>
            <div className="space-y-2">
              <span className="text-xs font-bold text-yellow-500 uppercase">Gold (Backtest)</span>
              <div className="p-2 border border-border rounded text-[10px] font-mono bg-secondary/20">
                /data/lake/gold/&lt;ds_name&gt;/<br/>
                Versioned via DVC
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
