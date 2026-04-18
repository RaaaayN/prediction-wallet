import React from 'react';
import type { JsonRecord } from '../types';
import SectionCard from './SectionCard';
import CollapsibleRaw from './CollapsibleRaw';

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

interface ConfigStripProps {
  cfg: JsonRecord | null;
}

const ConfigStrip: React.FC<ConfigStripProps> = ({ cfg }) => {
  if (!cfg) {
    return <p className="text-sm text-[#8b949e]">Chargement config…</p>;
  }

  const alloc = asRecord(cfg.target_allocation);
  const entries = Object.entries(alloc).sort((a, b) => Number(b[1]) - Number(a[1]));

  return (
    <SectionCard title="Configuration agent" subtitle="Profil actif et allocation cible">
      <div className="flex flex-wrap gap-2 mb-4">
        <span className="text-xs px-2 py-1 rounded-full bg-[#1b2a3d] border border-primary text-primary">
          {String(cfg.ai_provider ?? '—')}
        </span>
        <span className="text-xs px-2 py-1 rounded-full bg-[#21262d] border border-border text-[#c9d1d9]">
          {String(cfg.agent_backend ?? '—')}
        </span>
        <span className="text-xs px-2 py-1 rounded-full bg-[#21262d] border border-border text-[#c9d1d9]">
          mode: {String(cfg.execution_mode ?? '—')}
        </span>
        <span
          className={`text-xs px-2 py-1 rounded-full border ${
            cfg.hedge_fund_enabled ? 'bg-[#1a4731] border-green text-green' : 'bg-[#21262d] border-border text-[#8b949e]'
          }`}
        >
          hedge fund: {cfg.hedge_fund_enabled ? 'oui' : 'non'}
        </span>
      </div>

      <h3 className="text-xs font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Allocation cible</h3>
      <div className="space-y-2">
        {entries.length === 0 ? (
          <p className="text-sm text-[#8b949e]">Pas d’allocation dans le profil.</p>
        ) : (
          entries.map(([ticker, w]) => {
            const pct = typeof w === 'number' ? Math.min(100, w * 100) : 0;
            return (
              <div key={ticker} className="flex items-center gap-3">
                <span className="font-mono text-xs text-primary w-24 shrink-0">{ticker}</span>
                <div className="flex-1 h-2 bg-[#21262d] rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${pct}%` }} />
                </div>
                <span className="text-xs font-mono text-[#8b949e] w-12 text-right">{pct.toFixed(1)}%</span>
              </div>
            );
          })
        )}
      </div>
      <CollapsibleRaw label="Config JSON complet" data={cfg} />
    </SectionCard>
  );
};

export default ConfigStrip;
