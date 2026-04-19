import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useStrategies, useUpdateStrategyParams, useSentiment } from "@/api/queries";
import { Cpu, CheckCircle2, Circle, Settings2, RefreshCw, MessageSquare, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";

export function StrategyLab() {
  const profile = useStore((state) => state.profile);
  const { data: strategies, isLoading } = useStrategies();
  const { data: sentiment, isLoading: sentimentLoading } = useSentiment(profile);
  const updateParams = useUpdateStrategyParams();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [editData, setEditEditData] = useState<any>({});

  const handleEdit = (strat: any) => {
    setEditing(strat.name);
    setEditEditData({ ...strat.params });
  };

  const handleSave = async () => {
    if (!editing) return;
    await updateParams.mutateAsync({ strategy: editing, params: editData });
    setEditing(null);
    queryClient.invalidateQueries({ queryKey: ['strategies'] });
  };

  if (isLoading) return <div className="p-8 animate-pulse text-muted-foreground">Loading strategy registry...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Strategy Lab</h2>
          <p className="text-muted-foreground mt-1">Configure and combine predictive signals and rebalancing logic.</p>
        </div>
        <Button variant="outline" disabled>
          <Cpu className="h-4 w-4 mr-2" /> Custom Strategy (Coming Soon)
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {strategies?.map((strat: any) => (
          <Card key={strat.name} className={strat.is_active ? "border-primary ring-1 ring-primary/50" : ""}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <CardTitle className="text-lg capitalize">{strat.name}</CardTitle>
                {strat.is_active ? (
                  <span className="flex items-center gap-1 text-[10px] bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded-full font-bold uppercase">
                    <CheckCircle2 className="h-3 w-3" /> Active
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] bg-secondary text-muted-foreground px-2 py-0.5 rounded-full font-bold uppercase">
                    <Circle className="h-3 w-3" /> Inactive
                  </span>
                )}
              </div>
              <CardDescription className="text-xs min-h-[40px]">{strat.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 pt-2">
                <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider border-b border-border pb-1 mb-2">Parameters</div>
                
                {editing === strat.name ? (
                  <div className="space-y-4">
                    {Object.entries(strat.params).map(([key, value]: [string, any]) => (
                      <div key={key} className="space-y-1">
                        <label className="text-[10px] font-medium uppercase text-muted-foreground">{key.replace(/_/g, ' ')}</label>
                        {typeof value === 'number' ? (
                          <input 
                            type="number" 
                            step="0.01"
                            className="w-full h-8 rounded border border-input bg-background px-2 text-xs"
                            value={editData[key]}
                            onChange={e => setEditEditData({...editData, [key]: parseFloat(e.target.value)})}
                          />
                        ) : (
                          <input 
                            type="text" 
                            className="w-full h-8 rounded border border-input bg-background px-2 text-xs"
                            value={editData[key]}
                            onChange={e => setEditEditData({...editData, [key]: e.target.value})}
                          />
                        )}
                      </div>
                    ))}
                    <div className="flex gap-2 pt-2">
                      <Button size="sm" className="flex-1 h-8 text-xs" onClick={handleSave} disabled={updateParams.isPending}>
                        {updateParams.isPending ? <RefreshCw className="h-3 w-3 animate-spin mr-1" /> : "Save"}
                      </Button>
                      <Button size="sm" variant="ghost" className="flex-1 h-8 text-xs" onClick={() => setEditing(null)}>Cancel</Button>
                    </div>
                  </div>
                ) : (
                  <>
                    {Object.entries(strat.params).map(([key, value]: [string, any]) => (
                      <div key={key} className="flex justify-between items-center">
                        <span className="text-xs font-medium capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="text-xs font-mono bg-secondary/30 px-2 py-0.5 rounded">
                          {typeof value === 'object' ? `${Object.keys(value).length} items` : String(value)}
                        </span>
                      </div>
                    ))}
                    <Button 
                      variant="outline" 
                      className="w-full mt-6 text-xs h-8" 
                      onClick={() => handleEdit(strat)}
                    >
                      <Settings2 className="h-3 w-3 mr-2" /> Configure Parameters
                    </Button>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
         <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><MessageSquare className="h-4 w-4" /> Live NLP Sentiment</CardTitle>
            <CardDescription>Aggregate scores from FinBERT analysis of latest news</CardDescription>
          </CardHeader>
          <CardContent>
            {sentimentLoading ? (
               <div className="space-y-4 animate-pulse py-4">
                  {[1,2,3].map(i => <div key={i} className="h-10 bg-secondary/50 rounded" />)}
               </div>
            ) : sentiment && sentiment.length > 0 ? (
               <div className="space-y-3">
                  {sentiment.map((s: any) => (
                    <div key={s.ticker} className="flex items-center justify-between p-3 border border-border rounded-lg hover:bg-secondary/10 transition-colors">
                       <div className="flex items-center gap-3">
                          <div className="font-mono font-bold text-xs bg-secondary px-2 py-1 rounded">{s.ticker}</div>
                          <div className="text-[10px] text-muted-foreground uppercase">{s.count} articles scanned</div>
                       </div>
                       <div className="flex items-center gap-2">
                          <span className={`text-sm font-mono font-bold ${s.score > 0.1 ? 'text-emerald-500' : s.score < -0.1 ? 'text-destructive' : 'text-muted-foreground'}`}>
                             {s.score > 0 ? '+' : ''}{s.score.toFixed(2)}
                          </span>
                          {s.score > 0.1 ? <TrendingUp className="h-3 w-3 text-emerald-500" /> : s.score < -0.1 ? <TrendingDown className="h-3 w-3 text-destructive" /> : <Minus className="h-3 w-3 text-muted-foreground" />}
                       </div>
                    </div>
                  ))}
               </div>
            ) : (
              <div className="py-12 text-center text-muted-foreground border border-dashed rounded-lg bg-secondary/5">
                <p className="text-sm italic">Sentiment data unavailable. Trigger a market refresh to sync news.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-secondary/10 border-dashed border-2">
          <CardContent className="py-12 flex flex-col items-center justify-center text-center">
            <div className="h-12 w-12 rounded-full bg-secondary flex items-center justify-center mb-4">
              <Cpu className="h-6 w-6 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-medium">New Signal Integration</h3>
            <p className="text-sm text-muted-foreground max-w-md mt-2">
              The Prediction Wallet framework allows for easy integration of new signals like 
              Macro Regimes, Order Flow Imbalance, or Alternative Data.
            </p>
            <Button variant="outline" className="mt-4 text-primary border-primary/20">View Documentation</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
