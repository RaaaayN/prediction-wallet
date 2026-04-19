import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Bot, PlayCircle, Loader2, CheckCircle2, XCircle, Lightbulb, ThumbsUp, ThumbsDown, AlertTriangle } from "lucide-react";
import { format } from "date-fns";
import { useIdeaBook, useReviewIdea, useGenerateIdeas, useTraces, useObserve } from "@/api/queries";

export function AgentsPanel() {
  const profile = useStore((state) => state.profile);
  const strategy = useStore((state) => state.strategy);
  const queryClient = useQueryClient();
  const observe = useObserve();

  const { data: tracesData, isLoading: tracesLoading } = useTraces(profile);
  const { data: ideas, isLoading: ideasLoading } = useIdeaBook(profile);

  const runCycle = useMutation({
    mutationFn: async () => observe.mutateAsync({ strategy, mode: "simulate", profile }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["traces", profile] });
      queryClient.invalidateQueries({ queryKey: ["portfolio", profile] });
    }
  });

  const generateIdeas = useGenerateIdeas();
  const reviewIdea = useReviewIdea();

  const traces = tracesData?.traces || [];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Agents Panel</h2>
          <p className="text-muted-foreground mt-1">Pydantic AI orchestrator research and execution oversight.</p>
        </div>
        <Button onClick={() => runCycle.mutate()} disabled={runCycle.isPending}>
          {runCycle.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
          Trigger Cycle
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><Lightbulb className="h-4 w-4 text-amber-500" /> Idea Book</CardTitle>
              <CardDescription>Review LLM-generated alpha candidates</CardDescription>
            </div>
            <Button 
              size="sm" 
              variant="outline" 
              onClick={() => generateIdeas.mutate({ profile })}
              disabled={generateIdeas.isPending}
            >
              {generateIdeas.isPending ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Bot className="h-3 w-3 mr-1" />}
              Generate
            </Button>
          </CardHeader>
          <CardContent>
            {ideasLoading ? (
              <div className="py-8 text-center text-muted-foreground animate-pulse">Scanning idea book...</div>
            ) : ideas && ideas.length > 0 ? (
              <div className="space-y-3">
                {ideas.filter(i => i.review_status === 'pending_review').map((idea) => (
                  <div key={idea.idea_id} className="border border-border rounded-md p-3 bg-secondary/10">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="font-bold font-mono text-sm">{idea.ticker}</span>
                        <span className="ml-2 text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded uppercase">{idea.status}</span>
                      </div>
                      <div className="flex gap-1">
                        <button 
                          onClick={() => reviewIdea.mutate({ idea_id: idea.idea_id, status: 'approved', profile })}
                          className="p-1 hover:bg-emerald-500/20 text-emerald-500 rounded transition-colors"
                        >
                          <ThumbsUp className="h-3.5 w-3.5" />
                        </button>
                        <button 
                          onClick={() => reviewIdea.mutate({ idea_id: idea.idea_id, status: 'rejected', profile })}
                          className="p-1 hover:bg-destructive/20 text-destructive rounded transition-colors"
                        >
                          <ThumbsDown className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-2 italic">"{idea.thesis}"</p>
                    <div className="mt-2 flex justify-between items-center text-[10px] text-muted-foreground">
                       <span>Conviction: {(idea.conviction * 100).toFixed(0)}%</span>
                       <span>{format(new Date(idea.created_at), "MMM dd")}</span>
                    </div>
                  </div>
                ))}
                {ideas.filter(i => i.review_status === 'pending_review').length === 0 && (
                   <p className="text-center py-4 text-xs text-muted-foreground italic text-opacity-50">No pending ideas. Generate some to see candidates.</p>
                )}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Lightbulb className="mx-auto h-12 w-12 opacity-10 mb-4" />
                <p className="text-sm italic">Idea book is empty.</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Bot className="h-4 w-4" /> Decision Traces</CardTitle>
            <CardDescription>Immutable audit log of agent actions</CardDescription>
          </CardHeader>
          <CardContent className="h-[500px] overflow-y-auto">
            {tracesLoading ? (
              <div className="py-8 text-center text-muted-foreground animate-pulse">Loading traces...</div>
            ) : traces.length > 0 ? (
              <div className="space-y-4 pr-2 font-mono">
                {traces.map((trace: any) => (
                  <div key={trace.id} className="border border-border rounded-lg p-3 bg-secondary/20 text-[11px]">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">[{trace.cycle_id}]</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                          trace.stage === 'validate' ? 'bg-amber-500/20 text-amber-500' : 
                          trace.stage === 'execute' ? 'bg-emerald-500/20 text-emerald-500' : 'bg-primary/20 text-primary'
                        }`}>
                          {trace.stage.toUpperCase()}
                        </span>
                      </div>
                      <span className="text-muted-foreground opacity-70">
                        {trace.created_at ? format(new Date(trace.created_at), "HH:mm:ss") : "--:--:--"}
                      </span>
                    </div>
                    <div>
                      {trace.event_type === "policy_violation" ? (
                        <div className="text-destructive flex items-center gap-1"><XCircle className="h-3 w-3"/> BLOCKED</div>
                      ) : trace.event_type === "kill_switch" ? (
                         <div className="text-destructive font-bold flex items-center gap-1 underline underline-offset-4"><AlertTriangle className="h-3 w-3"/> KILL SWITCH ACTIVE</div>
                      ) : (
                        <div className="text-emerald-500 flex items-center gap-1"><CheckCircle2 className="h-3 w-3"/> OK</div>
                      )}
                      <div className="mt-2 text-muted-foreground break-all bg-black/30 p-2 rounded leading-relaxed border border-white/5">
                        {trace.validation_json || trace.tags || "{}"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground h-full flex flex-col justify-center">
                <Bot className="mx-auto h-12 w-12 opacity-10 mb-4" />
                <p>No recent agent traces found for this profile.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
