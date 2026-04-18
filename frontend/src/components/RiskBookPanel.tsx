import React from 'react';
import type { JsonRecord } from '../types';
import SectionCard from './SectionCard';
import StatCard from './StatCard';
import CollapsibleRaw from './CollapsibleRaw';

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

function chipList(items: unknown, kind: 'bad' | 'warn'): React.ReactNode {
  if (!Array.isArray(items) || items.length === 0) {
    return <span className="text-xs text-[#6e7681]">—</span>;
  }
  const cls =
    kind === 'bad' ? 'bg-[#3d1a1a] border-red text-red' : 'bg-[#3d2d0a] border-yellow text-yellow';
  return (
    <ul className="space-y-1">
      {items.map((x) => (
        <li key={String(x)} className={`text-xs px-2 py-1.5 rounded border ${cls}`}>
          {String(x)}
        </li>
      ))}
    </ul>
  );
}

interface RiskBookPanelProps {
  risk: JsonRecord | null;
}

const RiskBookPanel: React.FC<RiskBookPanelProps> = ({ risk }) => {
  if (!risk) {
    return <p className="text-sm text-[#8b949e]">Chargement risque…</p>;
  }
  const inner = asRecord(risk.exposure);

  return (
    <SectionCard title="Classification risque" subtitle="Breaches policy vs book">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <StatCard label="Gross" value={pct(inner.gross_exposure)} />
        <StatCard label="Net" value={pct(inner.net_exposure)} />
        <StatCard label="Top 5" value={pct(inner.top5_concentration)} />
        <StatCard label="Beta adj." value={num(inner.beta_adjusted_exposure)} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="text-xs font-semibold text-[#8b949e] uppercase mb-2">Violations</h3>
          {chipList(risk.breaches, 'bad')}
        </div>
        <div>
          <h3 className="text-xs font-semibold text-[#8b949e] uppercase mb-2">Proches limites</h3>
          {chipList(risk.near_breaches, 'warn')}
        </div>
      </div>
      <CollapsibleRaw label="JSON book-risk" data={risk} />
    </SectionCard>
  );
};

function pct(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return `${(n * 100).toFixed(1)}%`;
}

function num(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toFixed(3);
}

export default RiskBookPanel;
