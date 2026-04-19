import { useState } from "react";
import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useTradingCoreOrders, useTradingCoreExecutions, useTradingCorePositions, useTCCashMovements, useCreateCashMovement } from "@/api/queries";
import { Database, AlertCircle, ShoppingCart, List, Activity, DollarSign, Plus, RefreshCw } from "lucide-react";
import { format } from "date-fns";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";

export function TradingCore() {
  const profile = useStore((state) => state.profile);
  const { data: orders, isLoading: ordersLoading } = useTradingCoreOrders(profile);
  const { data: executions, isLoading: executionsLoading } = useTradingCoreExecutions(profile);
  const { data: positions, isLoading: positionsLoading } = useTradingCorePositions(profile);
  const { data: cashMovements, isLoading: cashLoading } = useTCCashMovements(profile);
  const createCashMovement = useCreateCashMovement();
  const queryClient = useQueryClient();

  const [showAddCash, setShowAddCash] = useState(false);
  const [cashAmount, setCashAmount] = useState(10000);

  const handleAddCash = async () => {
    await createCashMovement.mutateAsync({ 
      profile, 
      amount: cashAmount, 
      type: 'deposit',
      description: 'Manual deposit via UI'
    });
    setShowAddCash(false);
    queryClient.invalidateQueries();
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Trading Core</h2>
          <p className="text-muted-foreground mt-1">View the Order Management System (OMS) ledger and Security Master data.</p>
        </div>
        <Button variant="outline" onClick={() => setShowAddCash(!showAddCash)}>
          <Plus className="h-4 w-4 mr-2" /> Add Cash
        </Button>
      </div>

      {showAddCash && (
        <Card className="border-primary/50 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Inject Capital into Ledger</CardTitle>
          </CardHeader>
          <CardContent className="flex gap-4 items-end">
            <div className="space-y-2 flex-1">
              <label className="text-xs font-bold uppercase text-muted-foreground">Amount ($)</label>
              <input 
                type="number" 
                value={cashAmount}
                onChange={(e) => setCashAmount(Number(e.target.value))}
                className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm font-mono"
              />
            </div>
            <Button onClick={handleAddCash} disabled={createCashMovement.isPending}>
              {createCashMovement.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : "Confirm Deposit"}
            </Button>
            <Button variant="ghost" onClick={() => setShowAddCash(false)}>Cancel</Button>
          </CardContent>
        </Card>
      )}

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
                        <td className="py-2 px-3 font-mono font-bold text-xs">{order.symbol}</td>
                        <td className={`py-2 px-3 text-xs ${order.side === 'buy' || order.side === 'BUY' ? 'text-emerald-500' : 'text-destructive'}`}>{order.side}</td>
                        <td className="py-2 px-3 text-right font-mono">{order.requested_quantity}</td>
                        <td className="py-2 px-3 text-right text-[10px] uppercase font-bold">{order.status}</td>
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
                      <tr key={i} className="hover:bg-secondary/20 transition-colors">
                        <td className="py-2 px-3 font-mono font-bold text-xs">{exec.symbol}</td>
                        <td className={`py-2 px-3 text-xs ${exec.side === 'buy' || exec.side === 'BUY' ? 'text-emerald-500' : 'text-destructive'}`}>{exec.side}</td>
                        <td className="py-2 px-3 text-right font-mono">${exec.fill_price?.toFixed(2)}</td>
                        <td className="py-2 px-3 text-right text-xs text-muted-foreground">
                          {exec.executed_at ? format(new Date(exec.executed_at), "MMM dd, HH:mm") : "-"}
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

        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><List className="h-4 w-4" /> Security Master Positions</CardTitle>
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
                      <th className="py-2 px-4 text-right">Avg Cost</th>
                      <th className="py-2 px-4 text-right">Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {positions.map((pos: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20 transition-colors">
                        <td className="py-2 px-4 font-mono font-bold text-xs">{pos.symbol}</td>
                        <td className="py-2 px-4 text-right font-mono">{pos.quantity.toFixed(4)}</td>
                        <td className="py-2 px-4 text-right font-mono">${pos.avg_cost?.toFixed(2) || "0.00"}</td>
                        <td className="py-2 px-4 text-right font-mono text-muted-foreground">${(pos.market_value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
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

        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><DollarSign className="h-4 w-4" /> Cash Movements</CardTitle>
            <CardDescription>Ledger deposits and withdrawals</CardDescription>
          </CardHeader>
          <CardContent>
             {cashLoading ? (
              <div className="text-center py-6 text-muted-foreground animate-pulse">Loading movements...</div>
            ) : cashMovements && cashMovements.length > 0 ? (
              <div className="border border-border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 px-4 text-left">Type</th>
                      <th className="py-2 px-4 text-right">Amount</th>
                      <th className="py-2 px-4 text-right">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {cashMovements.map((move: any, i: number) => (
                      <tr key={i} className="hover:bg-secondary/20 transition-colors">
                        <td className="py-2 px-4 font-bold text-[10px] uppercase text-muted-foreground">{move.movement_type.replace('_', ' ')}</td>
                        <td className={`py-2 px-4 text-right font-mono font-bold ${move.amount > 0 ? 'text-emerald-500' : 'text-destructive'}`}>
                          {move.amount > 0 ? '+' : ''}{move.amount.toLocaleString()}
                        </td>
                        <td className="py-2 px-4 text-right text-[10px] text-muted-foreground">
                           {format(new Date(move.created_at), "MMM dd, HH:mm")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground border border-dashed border-border rounded-lg">
                <DollarSign className="mx-auto h-12 w-12 opacity-20 mb-4" />
                <p>No cash movements recorded.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
