import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { AgentRun, DecisionTrace, JsonRecord, ReconciliationBreak, TCAReport } from '../types';

const Audit: React.FC = () => {
  const [traces, setTraces] = useState<DecisionTrace[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [events, setEvents] = useState<JsonRecord[]>([]);
  const [breaks, setBreaks] = useState<ReconciliationBreak[]>([]);
  const [tca, setTca] = useState<TCAReport | null>(null);
  const [tcaLoading, setTcaLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [t, r, e, b] = await Promise.all([
          ApiService.get<DecisionTrace[]>('/api/traces?limit=15'),
          ApiService.get<AgentRun[]>('/api/runs?limit=15'),
          ApiService.get<JsonRecord[]>('/api/events?limit=20'),
          ApiService.get<ReconciliationBreak[]>('/api/middle-office/reconcile').catch(() => []),
        ]);
        setTraces(t);
        setRuns(r);
        setEvents(e);
        setBreaks(b || []);
      } catch (ex) {
        setErr(ex instanceof Error ? ex.message : 'Failed to load');
      }
    })();
  }, []);

  const handleSync = async () => {
    if (!window.confirm('Forcer la synchronisation du state legacy vers le Ledger ?')) return;
    try {
      await ApiService.post('/api/middle-office/sync', {});
      const b = await ApiService.get<ReconciliationBreak[]>('/api/middle-office/reconcile');
      setBreaks(b);
      alert('Synchronisation réussie.');
    } catch (ex) {
      alert(ex instanceof Error ? ex.message : 'Échec de la synchronisation');
    }
  };

  const loadTCA = async (cycleId: string) => {
    setTcaLoading(true);
    try {
      const report = await ApiService.get<TCAReport>(`/api/middle-office/tca/${cycleId}`);
      setTca(report);
    } catch (ex) {
      console.warn('TCA not found', ex);
      setTca(null);
    } finally {
      setTcaLoading(false);
    }
  };

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <p className="text-sm text-[#8b949e]">
          Audit gouvernance : traces, exécutions et journal d&apos;événements récents.
        </p>
        <div className="flex gap-2">
          {breaks.length > 0 ? (
            <div className="bg-red/10 border border-red/20 text-red px-3 py-1 rounded text-xs flex items-center gap-2">
              ⚠️ {breaks.length} Breaks MO
              <button onClick={handleSync} className="underline font-bold hover:text-red-400">Sync Ledger</button>
            </div>
          ) : (
            <div className="bg-green/10 border border-green/20 text-green px-3 py-1 rounded text-xs">
              ✓ Middle Office OK
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* ... (Traces Section) */}
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
                  <th className="py-2 pr-2 font-medium">TCA</th>
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
                      <td className="py-2 pr-2">
                         <button 
                          onClick={() => loadTCA(r.cycle_id)} 
                          className="text-primary hover:text-white underline text-[10px]"
                        >
                          Analyze
                        </button>
                      </td>
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

      {(tcaLoading || tca) && (
        <SectionCard 
          title={`TCA Report: ${tca?.cycle_id || '...'}`} 
          subtitle="Transaction Cost Analysis & Slippage"
        >
          {tcaLoading ? (
            <div className="text-xs text-[#8b949e] animate-pulse">Computing metrics...</div>
          ) : tca ? (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-bg/50 p-2 rounded border border-border/40">
                  <div className="text-[10px] text-[#8b949e] uppercase">Total Notional</div>
                  <div className="text-sm font-mono">${tca.total_notional.toLocaleString()}</div>
                </div>
                <div className="bg-bg/50 p-2 rounded border border-border/40">
                  <div className="text-[10px] text-[#8b949e] uppercase">Slippage Cost</div>
                  <div className="text-sm font-mono text-red">${tca.total_slippage_dollars.toFixed(2)}</div>
                </div>
                <div className="bg-bg/50 p-2 rounded border border-border/40">
                  <div className="text-[10px] text-[#8b949e] uppercase">Avg Slippage</div>
                  <div className="text-sm font-mono text-orange">{tca.avg_slippage_bps.toFixed(1)} bps</div>
                </div>
                <div className="bg-bg/50 p-2 rounded border border-border/40">
                  <div className="text-[10px] text-[#8b949e] uppercase">Executions</div>
                  <div className="text-sm font-mono">{tca.total_trades}</div>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="text-left text-[#8b949e] border-b border-border">
                      <th className="pb-1">Ticker</th>
                      <th className="pb-1">Side</th>
                      <th className="pb-1 text-right">Market</th>
                      <th className="pb-1 text-right">Fill</th>
                      <th className="pb-1 text-right">Slippage (bps)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tca.trade_details.map((d, i) => (
                      <tr key={i} className="border-b border-border/40">
                        <td className="py-1 font-mono font-bold">{d.symbol}</td>
                        <td className={`py-1 uppercase ${d.side === 'buy' ? 'text-green' : 'text-orange'}`}>{d.side}</td>
                        <td className="py-1 text-right font-mono">${d.market_price.toFixed(2)}</td>
                        <td className="py-1 text-right font-mono">${d.fill_price.toFixed(2)}</td>
                        <td className="py-1 text-right font-mono text-orange">{d.slippage_bps.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </SectionCard>
      )}
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
