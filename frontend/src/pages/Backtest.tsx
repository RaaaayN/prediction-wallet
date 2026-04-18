import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { JsonRecord } from '../types';

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

const Backtest: React.FC = () => {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>(`/api/backtest?days=${days}`));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, [days]);

  if (err) return <div className="text-red text-sm">{err}</div>;

  const keys = data ? Object.keys(data).filter((k) => !['error', 'detail'].includes(k)) : [];

  return (
    <div className="flex flex-col gap-4">
      <label className="text-xs text-[#8b949e] flex items-center gap-2">
        Jours
        <input
          type="number"
          min={30}
          max={3650}
          value={days}
          onChange={(e) => setDays(Number(e.target.value) || 90)}
          className="bg-gray-bg border border-border rounded px-2 py-1 w-24 text-sm"
        />
      </label>
      <SectionCard title="Comparaison de stratégies" subtitle="Données historiques agrégées">
        {keys.length === 0 ? (
          <p className="text-sm text-[#8b949e]">Pas de données — vérifie le réseau et yfinance.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {keys.map((name) => {
              const s = asRecord(data![name]);
              return (
                <div key={name} className="rounded-lg border border-[#21262d] p-4 space-y-2">
                  <div className="text-sm font-semibold text-primary">{name}</div>
                  <StatCard label="Sharpe" value={num(s.sharpe)} />
                  <StatCard label="Max DD" value={num(s.max_dd)} />
                  <StatCard label="Trades" value={String(s.n_trades ?? '—')} />
                </div>
              );
            })}
          </div>
        )}
        <CollapsibleRaw label="JSON backtest" data={data} />
      </SectionCard>
    </div>
  );
};

function num(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toFixed(3);
}

export default Backtest;
