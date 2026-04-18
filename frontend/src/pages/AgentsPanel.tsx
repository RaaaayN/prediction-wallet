import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import { apiClient } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bot, PlayCircle, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { format } from "date-fns";

export function AgentsPanel() {
  const profile = useStore((state) => state.profile);
  const strategy = useStore((state) => state.strategy);
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["traces", profile],
    queryFn: async () => (await apiClient.get(`/audit/traces?profile=${profile}`)).data,
  });

  const runCycle = useMutation({
    mutationFn: async () => {
      // Mocking for now if the endpoint is not fully ready for frontend consumption
      const response = await apiClient.post(`/runner/observe?profile=${profile}`, { strategy_name: strategy, execution_mode: "simulate" });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["traces"] });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    }
  });

  const traces = data?.traces || [];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Agents Panel</h2>
          <p className="text-muted-foreground mt-1">Pydantic AI orchestrator logs and controls.</p>
        </div>
        <Button onClick={() => runCycle.mutate()} disabled={runCycle.isPending}>
          {runCycle.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
          Trigger Cycle
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Decision Traces</CardTitle>
          <CardDescription>Immutable audit log of agent actions</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="py-8 text-center text-muted-foreground animate-pulse">Loading traces...</div>
          ) : traces.length > 0 ? (
            <div className="space-y-4">
              {traces.map((trace: any) => (
                <div key={trace.id} className="border border-border rounded-lg p-4 bg-secondary/20">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{trace.cycle_id}</span>
                      <span className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded">{trace.stage.toUpperCase()}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {trace.created_at ? format(new Date(trace.created_at), "yyyy-MM-dd HH:mm:ss") : "Unknown"}
                    </span>
                  </div>
                  <div className="text-sm">
                    {trace.event_type === "policy_violation" ? (
                      <div className="text-destructive flex items-center gap-1"><XCircle className="h-4 w-4"/> Policy Violation Blocked</div>
                    ) : (
                      <div className="text-emerald-500 flex items-center gap-1"><CheckCircle2 className="h-4 w-4"/> Cycle Proceeded</div>
                    )}
                    <div className="mt-2 text-muted-foreground text-xs font-mono break-all line-clamp-2">
                      {trace.tags || "[]"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <Bot className="mx-auto h-12 w-12 opacity-20 mb-4" />
              <p>No recent agent traces found for this profile.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
