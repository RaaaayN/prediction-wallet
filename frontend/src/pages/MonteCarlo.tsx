import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { JsonRecord } from '../types';

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

const MonteCarlo: React.FC = () => {
  const [paths, setPaths] = useState(5000);
  const [data, setData] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>(`/api/monte-carlo?paths=${paths}`));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, [paths]);

  if (err) return <div className="text-red text-sm">{err}</div>;

  const ci = asRecord(data?.confidence_intervals as unknown);
  const sharpe = asRecord(ci.sharpe as unknown);
  const mdd = asRecord(ci.max_drawdown as unknown);

  return (
    <div className="flex flex-col gap-4">
      <label className="text-xs text-[#8b949e] flex items-center gap-2">
        Chemins simulés
        <input
          type="number"
          min={100}
          max={20000}
          step={100}
          value={paths}
          onChange={(e) => setPaths(Number(e.target.value) || 5000)}
          className="bg-gray-bg border border-border rounded px-2 py-1 w-28 text-sm"
        />
      </label>
      <SectionCard title="Monte Carlo" subtitle="Distribution forward (synthèse)">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Sharpe p5" value={num(sharpe.p5)} />
          <StatCard label="Sharpe p50" value={num(sharpe.p50)} />
          <StatCard label="Sharpe p95" value={num(sharpe.p95)} />
          <StatCard label="Valeur init." value={num(data?.initial_value)} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3">
          <StatCard label="Max DD p5" value={num(mdd.p5)} variant="green" />
          <StatCard label="Max DD p50" value={num(mdd.p50)} />
          <StatCard label="Max DD p95" value={num(mdd.p95)} variant="red" />
        </div>
        <CollapsibleRaw label="JSON monte-carlo" data={data} />
      </SectionCard>
    </div>
  );
};

function num(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toFixed(3);
}

export default MonteCarlo;
