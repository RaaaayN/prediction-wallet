import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
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
        Audit gouvernance : traces, exécutions et journal d&apos;événements récents. Détail par cycle :{' '}
        <Link className="text-primary underline" to="/traces">
          Agent Trace
        </Link>
        .
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SectionCard title="Traces (15)" subtitle="Étapes agent par cycle">
          <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card-bg border-b border-border">
                <tr className="text-left text-[#8b949e]">
                  <th className="py-2 pr-2 font-medium">Cycle</th>
                  <th className="py-2 pr-2 font-medium">Étape</th>
                  <th className="py-2 pr-2 font-medium">Heure</th>
                </tr>
              </thead>
              <tbody>
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-3 text-[#8b949e]">
                      Aucune trace
                    </td>
                  </tr>
                ) : (
                  traces.map((t) => (
                    <tr key={t.id} className="border-b border-border/60 align-top">
                      <td className="py-2 pr-2 font-mono text-[11px]">
                        <Link className="text-primary hover:underline break-all" to={`/traces?cycle=${encodeURIComponent(t.cycle_id)}`}>
                          {shortId(t.cycle_id)}
                        </Link>
                      </td>
                      <td className="py-2 pr-2 text-[#c9d1d9]">{t.stage}</td>
                      <td className="py-2 pr-2 text-[#8b949e] whitespace-nowrap">{fmtTime(t.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <CollapsibleRaw label="JSON traces" data={traces} />
        </SectionCard>

        <SectionCard title="Runs (15)" subtitle="Cycles agent récents">
          <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card-bg border-b border-border">
                <tr className="text-left text-[#8b949e]">
                  <th className="py-2 pr-2 font-medium">Cycle</th>
                  <th className="py-2 pr-2 font-medium">Signal</th>
                  <th className="py-2 pr-2 font-medium">Trades</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-3 text-[#8b949e]">
                      Aucun run
                    </td>
                  </tr>
                ) : (
                  runs.map((r) => (
                    <tr key={`${r.cycle_id}-${r.timestamp}`} className="border-b border-border/60 align-top">
                      <td className="py-2 pr-2 font-mono text-[11px]">
                        <Link className="text-primary hover:underline break-all" to={`/traces?cycle=${encodeURIComponent(r.cycle_id)}`}>
                          {shortId(r.cycle_id)}
                        </Link>
                      </td>
                      <td className="py-2 pr-2 font-mono">{fmtSignal(r.signal)}</td>
                      <td className="py-2 pr-2">{r.trades_count}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <CollapsibleRaw label="JSON runs" data={runs} />
        </SectionCard>

        <SectionCard title="Événements (20)" subtitle="Journal cycle_events">
          <div className="overflow-x-auto max-h-[420px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-card-bg border-b border-border">
                <tr className="text-left text-[#8b949e]">
                  <th className="py-2 pr-2 font-medium">Type</th>
                  <th className="py-2 pr-2 font-medium">Cycle</th>
                  <th className="py-2 pr-2 font-medium">Heure</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-3 text-[#8b949e]">
                      Aucun événement
                    </td>
                  </tr>
                ) : (
                  events.map((ev) => {
                    const id = typeof ev.id === 'number' || typeof ev.id === 'string' ? String(ev.id) : JSON.stringify(ev);
                    return (
                      <tr key={id} className="border-b border-border/60 align-top">
                        <td className="py-2 pr-2 text-[#c9d1d9]">{String(ev.event_type ?? '—')}</td>
                        <td className="py-2 pr-2 font-mono text-[11px]">
                          {typeof ev.cycle_id === 'string' ? (
                            <Link className="text-primary hover:underline break-all" to={`/traces?cycle=${encodeURIComponent(ev.cycle_id)}`}>
                              {shortId(ev.cycle_id)}
                            </Link>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="py-2 pr-2 text-[#8b949e] whitespace-nowrap">{fmtTime(ev.created_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <CollapsibleRaw label="JSON events" data={events} />
        </SectionCard>
      </div>
    </div>
  );
};

function shortId(id: string, max = 14): string {
  if (id.length <= max) return id;
  return `${id.slice(0, max)}…`;
}

function fmtTime(v: unknown): string {
  if (typeof v !== 'string') return '—';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function fmtSignal(signal: boolean | number | undefined): string {
  if (signal === undefined) return '—';
  if (typeof signal === 'boolean') return signal ? 'oui' : 'non';
  return String(signal);
}

export default Audit;
