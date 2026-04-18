import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { JsonRecord } from '../types';

const Regime: React.FC = () => {
  const [data, setData] = useState<JsonRecord | null>(null);
  const [days, setDays] = useState(180);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>(`/api/regime?days=${days}`));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, [days]);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-4">
      <label className="text-xs text-[#8b949e] flex items-center gap-2">
        Fenêtre (jours)
        <input
          type="number"
          min={30}
          max={365}
          value={days}
          onChange={(e) => setDays(Number(e.target.value) || 180)}
          className="bg-gray-bg border border-border rounded px-2 py-1 w-24 text-sm"
        />
      </label>
      <SectionCard title="Régime de marché" subtitle="Volatilité relative et momentum">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-3">
          <StatCard label="Régime" value={String(data?.regime ?? '—')} />
          <StatCard label="Vol percentile" value={fmtRatio(data?.vol_percentile)} />
          <StatCard label="Vol 30j" value={fmtRatio(data?.vol_30d)} hint="écart-type des rendements quotidiens" />
          <StatCard label="Vol 90j" value={fmtRatio(data?.vol_90d)} />
          <StatCard label="Ratio vol 30/90" value={fmtNumber(data?.vol_ratio)} />
          <StatCard label="Return 30j" value={fmtRatio(data?.return_30d)} />
          <StatCard
            label="Soft block"
            value={data?.soft_block_recommended ? 'oui' : 'non'}
            variant={data?.soft_block_recommended ? 'yellow' : 'default'}
          />
        </div>
        {data?.description ? (
          <p className="text-sm text-[#c9d1d9] leading-relaxed border-l-2 border-primary pl-3">{String(data.description)}</p>
        ) : null}
        {data?.error ? <p className="text-sm text-yellow mt-2">{String(data.error)}</p> : null}
        <CollapsibleRaw label="JSON regime" data={data} />
      </SectionCard>
    </div>
  );
};

function fmtRatio(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

function fmtNumber(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toFixed(3);
}

export default Regime;
