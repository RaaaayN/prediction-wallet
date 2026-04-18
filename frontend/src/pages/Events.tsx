import { useQuery } from "@tanstack/react-query";
import { useStore } from "@/store/useStore";
import { apiClient } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Database, RefreshCcw, History, ArrowRightCircle } from "lucide-react";
import { format } from "date-fns";

export function Events() {
  const profile = useStore((state) => state.profile);
  const { data: events, isLoading, refetch } = useQuery({
    queryKey: ["events", profile],
    queryFn: async () => {
      const { data } = await apiClient.get(`/events?profile=${profile}&limit=50`);
      return data;
    }
  });

  const replayEvent = (cycleId: string) => {
    window.open(`/api/events/replay/${cycleId}?profile=${profile}`, "_blank");
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Event Browser</h2>
          <p className="text-muted-foreground mt-1">Immutable event stream from the event-sourcing layer.</p>
        </div>
        <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCcw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><History className="h-4 w-4" /> Immutable Log</CardTitle>
          <CardDescription>Replay past cycles to reconstruct system state at any point in time.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="py-12 text-center animate-pulse text-muted-foreground">Reading event log...</div>
          ) : events && events.length > 0 ? (
            <div className="border border-border rounded-md overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-secondary/50 border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 px-4 text-left font-medium">Type</th>
                    <th className="py-2 px-4 text-left font-medium">Cycle ID</th>
                    <th className="py-2 px-4 text-left font-medium">Timestamp</th>
                    <th className="py-2 px-4 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {events.map((event: any, i: number) => (
                    <tr key={i} className="hover:bg-secondary/20 transition-colors">
                      <td className="py-2 px-4 font-mono font-bold text-xs text-primary">{event.event_type}</td>
                      <td className="py-2 px-4 font-mono text-xs text-muted-foreground">{event.cycle_id}</td>
                      <td className="py-2 px-4 text-xs text-muted-foreground">
                         {event.created_at ? format(new Date(event.created_at), "MMM dd, HH:mm:ss") : "N/A"}
                      </td>
                      <td className="py-2 px-4 text-right">
                        <Button variant="ghost" size="sm" onClick={() => replayEvent(event.cycle_id)} className="h-7 text-xs">
                          <ArrowRightCircle className="h-3.5 w-3.5 mr-1" /> Replay
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center text-muted-foreground">
              <Database className="mx-auto h-12 w-12 opacity-10 mb-4" />
              <p>No events found in the stream.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
