import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { AgentRun, DecisionTrace, JsonRecord } from '../types';

const Audit: React.FC = () => {
  const [traces, setTraces] = useState<DecisionTrace[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [events, setEvents] = useState<JsonRecord[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [t, r, e] = await Promise.all([
          ApiService.get<DecisionTrace[]>('/api/traces?limit=15'),
          ApiService.get<AgentRun[]>('/api/runs?limit=15'),
          ApiService.get<JsonRecord[]>('/api/events?limit=20'),
        ]);
        setTraces(t);
        setRuns(r);
        setEvents(e);
      } catch (ex) {
        setErr(ex instanceof Error ? ex.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#8b949e]">
        Governance audit slice: recent traces, runs, and event log. Full trace UI:{' '}
        <Link className="text-primary underline" to="/traces">Agent Trace</Link>.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <JsonPanel title="Latest traces (15)" data={traces} />
        <JsonPanel title="Latest runs (15)" data={runs} />
        <JsonPanel title="Recent events (20)" data={events} />
      </div>
    </div>
  );
};

export default Audit;
