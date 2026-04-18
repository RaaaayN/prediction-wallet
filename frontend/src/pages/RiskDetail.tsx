import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import RiskBookPanel from '../components/RiskBookPanel';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import KeyValueTable from '../components/KeyValueTable';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { JsonRecord } from '../types';

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

function pctRecord(rec: JsonRecord): Record<string, string> {
  const o: Record<string, string> = {};
  for (const [k, v] of Object.entries(rec)) {
    o[k] = typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : String(v);
  }
  return o;
}

const RiskDetail: React.FC = () => {
  const [risk, setRisk] = useState<JsonRecord | null>(null);
  const [exp, setExp] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [r, e] = await Promise.all([
          ApiService.get<JsonRecord>('/api/book-risk'),
          ApiService.get<JsonRecord>('/api/exposures'),
        ]);
        setRisk(r);
        setExp(e);
      } catch (ex) {
        setErr(ex instanceof Error ? ex.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  const e = asRecord(exp);

  return (
    <div className="flex flex-col gap-6">
      <RiskBookPanel risk={risk} />
      <SectionCard title="Expositions brutes" subtitle="Même moteur que /api/exposures">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <StatCard label="Gross" value={typeof e.gross_exposure === 'number' ? `${(e.gross_exposure * 100).toFixed(1)}%` : '—'} />
          <StatCard label="Net" value={typeof e.net_exposure === 'number' ? `${(e.net_exposure * 100).toFixed(1)}%` : '—'} />
          <StatCard label="Long" value={typeof e.long_exposure === 'number' ? `${(e.long_exposure * 100).toFixed(1)}%` : '—'} />
          <StatCard label="Short" value={typeof e.short_exposure === 'number' ? `${(e.short_exposure * 100).toFixed(1)}%` : '—'} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <KeyValueTable title="Secteur gross" rows={pctRecord(asRecord(e.sector_gross))} />
          <KeyValueTable title="Secteur net" rows={pctRecord(asRecord(e.sector_net))} />
        </div>
        <CollapsibleRaw label="JSON exposures" data={exp} />
      </SectionCard>
    </div>
  );
};

export default RiskDetail;
