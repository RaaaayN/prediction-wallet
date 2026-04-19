import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useTradingCoreOrders, useTradingCoreExecutions, useTradingCorePositions } from "@/api/queries";
import { Database, AlertCircle, ShoppingCart, List, Activity } from "lucide-react";
import { format } from "date-fns";

export function TradingCore() {
  const profile = useStore((state) => state.profile);
  const { data: orders, isLoading: ordersLoading } = useTradingCoreOrders(profile);
  const { data: executions, isLoading: executionsLoading } = useTradingCoreExecutions(profile);
  const { data: positions, isLoading: positionsLoading } = useTradingCorePositions(profile);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Trading Core</h2>
          <p className="text-muted-foreground mt-1">View the Order Management System (OMS) ledger and Security Master data.</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><ShoppingCart className="h-4 w-4" /> Live Orders</CardTitle>
            <CardDescription>Orders submitted to the OMS</CardDescription>
          </CardHeader>
          <CardContent>
            {ordersLoading ? (
              <div className="text-center py-6 text-muted-foreground animate-pulse">Loading orders...</div>
            ) : orders && orders.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-3 text-left">Ticker</th>
                      <th className="py-2 px-3 text-left">Side</th>
                      <th className="py-2 px-3 text-right">Quantity</th>
                      <th className="py-2 px-3 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {orders.map((order: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-3 font-mono font-bold text-xs">{order.ticker}</td>
                        <td className={`py-2 px-3 text-xs ${order.side === 'BUY' ? 'text-emerald-500' : 'text-destructive'}`}>{order.side}</td>
                        <td className="py-2 px-3 text-right font-mono">{order.quantity}</td>
                        <td className="py-2 px-3 text-right text-xs">{order.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground border border-dashed border-border rounded-lg">
                <AlertCircle className="mx-auto h-8 w-8 opacity-20 mb-2" />
                <p className="text-sm">No active orders</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Activity className="h-4 w-4" /> Executions</CardTitle>
            <CardDescription>Completed trade executions</CardDescription>
          </CardHeader>
          <CardContent>
            {executionsLoading ? (
              <div className="text-center py-6 text-muted-foreground animate-pulse">Loading executions...</div>
            ) : executions && executions.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-3 text-left">Ticker</th>
                      <th className="py-2 px-3 text-left">Side</th>
                      <th className="py-2 px-3 text-right">Price</th>
                      <th className="py-2 px-3 text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {executions.slice(0, 10).map((exec: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-3 font-mono font-bold text-xs">{exec.ticker}</td>
                        <td className={`py-2 px-3 text-xs ${exec.side === 'BUY' ? 'text-emerald-500' : 'text-destructive'}`}>{exec.side}</td>
                        <td className="py-2 px-3 text-right font-mono">${exec.fill_price?.toFixed(2)}</td>
                        <td className="py-2 px-3 text-right text-xs text-muted-foreground">
                          {exec.created_at ? format(new Date(exec.created_at), "MMM dd, HH:mm") : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground border border-dashed border-border rounded-lg">
                <AlertCircle className="mx-auto h-8 w-8 opacity-20 mb-2" />
                <p className="text-sm">No recent executions</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><List className="h-4 w-4" /> Trading Core Positions</CardTitle>
            <CardDescription>Authoritative ledger positions</CardDescription>
          </CardHeader>
          <CardContent>
             {positionsLoading ? (
              <div className="text-center py-6 text-muted-foreground animate-pulse">Loading positions...</div>
            ) : positions && positions.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left">Ticker</th>
                      <th className="py-2 px-4 text-right">Quantity</th>
                      <th className="py-2 px-4 text-right">Avg Price</th>
                      <th className="py-2 px-4 text-right">Cost Basis</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {positions.map((pos: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20">
                        <td className="py-2 px-4 font-mono font-bold text-xs">{pos.ticker}</td>
                        <td className="py-2 px-4 text-right font-mono">{pos.quantity}</td>
                        <td className="py-2 px-4 text-right font-mono">${pos.average_price?.toFixed(2) || "0.00"}</td>
                        <td className="py-2 px-4 text-right font-mono text-muted-foreground">${((pos.quantity || 0) * (pos.average_price || 0)).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground border border-dashed border-border rounded-lg">
                <Database className="mx-auto h-12 w-12 opacity-20 mb-4" />
                <p>No positions in the Trading Core Ledger.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
