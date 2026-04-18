import React from 'react';
import SectionCard from './SectionCard';
import StatCard from './StatCard';
import CollapsibleRaw from './CollapsibleRaw';

interface StressRow {
  scenario?: string;
  description?: string;
  portfolio_value_before?: number;
  portfolio_value_after?: number;
  pnl_dollars?: number;
  pnl_pct?: number;
  kill_switch_triggered?: boolean;
}

interface StressScenariosViewProps {
  rows: unknown;
}

const StressScenariosView: React.FC<StressScenariosViewProps> = ({ rows }) => {
  const list = Array.isArray(rows) ? (rows as StressRow[]) : [];

  if (list.length === 0) {
    return (
      <SectionCard title="Stress test" subtitle="Scénarios de choc sur le portefeuille">
        <p className="text-sm text-[#8b949e]">Aucun scénario renvoyé (portefeuille vide ou valeur nulle).</p>
        <CollapsibleRaw label="Réponse brute" data={rows} />
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Stress test" subtitle="Impact P&amp;L par scénario (simulation)">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {list.map((r) => (
          <div key={r.scenario} className="rounded-lg border border-[#21262d] p-4 bg-[#0d1117]/80">
            <div className="text-sm font-semibold text-primary mb-1">{r.scenario}</div>
            <p className="text-xs text-[#8b949e] mb-3 leading-snug">{r.description}</p>
            <div className="grid grid-cols-2 gap-2">
              <StatCard label="Avant" value={fmtUsd(r.portfolio_value_before)} />
              <StatCard label="Après" value={fmtUsd(r.portfolio_value_after)} />
              <StatCard
                label="P&amp;L $"
                value={fmtUsd(r.pnl_dollars)}
                variant={typeof r.pnl_dollars === 'number' && r.pnl_dollars < 0 ? 'red' : 'green'}
              />
              <StatCard
                label="P&amp;L %"
                value={fmtPct(r.pnl_pct)}
                variant={typeof r.pnl_pct === 'number' && r.pnl_pct < 0 ? 'red' : 'green'}
              />
            </div>
            {r.kill_switch_triggered ? (
              <div className="mt-2 text-xs text-red font-semibold">Kill switch déclenché</div>
            ) : null}
          </div>
        ))}
      </div>
      <CollapsibleRaw label="JSON stress" data={rows} />
    </SectionCard>
  );
};

function fmtUsd(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

function fmtPct(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return `${(n * 100).toFixed(2)}%`;
}

export default StressScenariosView;
