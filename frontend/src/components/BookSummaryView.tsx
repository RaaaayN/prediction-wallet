import React from 'react';
import type { JsonRecord } from '../types';
import SectionCard from './SectionCard';
import StatCard from './StatCard';
import KeyValueTable from './KeyValueTable';
import CollapsibleRaw from './CollapsibleRaw';

function pct(n: unknown, digits = 1): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return `${(n * 100).toFixed(digits)}%`;
}

function num(n: unknown, digits = 2): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: digits });
}

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

function chipList(items: unknown, tone: 'red' | 'yellow' | 'blue'): React.ReactNode {
  if (!Array.isArray(items) || items.length === 0) {
    return <span className="text-xs text-[#6e7681]">Aucun</span>;
  }
  const bg =
    tone === 'red' ? 'bg-[#3d1a1a] border-red text-red' : tone === 'yellow' ? 'bg-[#3d2d0a] border-yellow text-yellow' : 'bg-[#1b2a3d] border-primary text-primary';
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((x) => (
        <span key={String(x)} className={`text-xs px-2 py-1 rounded-md border ${bg}`}>
          {String(x)}
        </span>
      ))}
    </div>
  );
}

interface BookSummaryViewProps {
  summary: JsonRecord | null;
}

const BookSummaryView: React.FC<BookSummaryViewProps> = ({ summary }) => {
  if (!summary) {
    return <p className="text-sm text-[#8b949e]">Chargement du livre…</p>;
  }

  const exposures = asRecord(summary.exposures);
  const risk = asRecord(summary.risk);
  const pnl = asRecord(summary.pnl_attribution);

  return (
    <div className="flex flex-col gap-6">
      <SectionCard title="Expositions" subtitle="Gross / net / secteurs / concentration">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <StatCard label="Gross" value={pct(exposures.gross_exposure)} />
          <StatCard label="Net" value={pct(exposures.net_exposure)} />
          <StatCard label="Long" value={pct(exposures.long_exposure)} variant="green" />
          <StatCard label="Short" value={pct(exposures.short_exposure)} variant="yellow" />
          <StatCard label="Beta adj." value={num(exposures.beta_adjusted_exposure, 3)} />
          <StatCard label="Top 5 conc." value={pct(exposures.top5_concentration)} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <KeyValueTable title="Secteur (gross)" rows={mapNumRecord(asRecord(exposures.sector_gross), pct)} />
          <KeyValueTable title="Secteur (net)" rows={mapNumRecord(asRecord(exposures.sector_net), pct)} />
        </div>
        <div className="mt-4">
          <h3 className="text-xs font-semibold text-[#8b949e] uppercase tracking-wide mb-2">Concentration par ligne</h3>
          <div className="max-h-48 overflow-y-auto rounded-lg border border-[#21262d]">
            <table>
              <thead>
                <tr>
                  <th className="text-left">Ticker</th>
                  <th className="text-right">Poids</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(asRecord(exposures.single_name_concentration))
                  .sort((a, b) => Number(b[1]) - Number(a[1]))
                  .slice(0, 12)
                  .map(([t, v]) => (
                    <tr key={t}>
                      <td className="font-mono text-primary">{t}</td>
                      <td className="text-right font-mono text-sm">{pct(v)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Risque livre" subtitle="Politique vs expositions synthétiques">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <h3 className="text-xs font-semibold text-[#8b949e] uppercase mb-2">Violations</h3>
            {chipList(risk.breaches, 'red')}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-[#8b949e] uppercase mb-2">Alertes proches</h3>
            {chipList(risk.near_breaches, 'yellow')}
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div>
            <h3 className="text-xs font-semibold text-[#8b949e] uppercase mb-2">Crowded</h3>
            {chipList(risk.crowded_names, 'blue')}
          </div>
          <div>
            <h3 className="text-xs font-semibold text-[#8b949e] uppercase mb-2">Short squeeze</h3>
            {chipList(risk.short_squeeze_names, 'yellow')}
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Attribution P&amp;L" subtitle="Réalisé / non réalisé / par secteur">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <StatCard
            label="Réalisé"
            value={num(pnl.realized_total)}
            variant={typeof pnl.realized_total === 'number' && pnl.realized_total < 0 ? 'red' : 'green'}
          />
          <StatCard
            label="Non réalisé"
            value={num(pnl.unrealized_total)}
            variant={typeof pnl.unrealized_total === 'number' && pnl.unrealized_total < 0 ? 'red' : 'green'}
          />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <KeyValueTable title="Par côté" rows={mapNumRecord(asRecord(pnl.by_side), (v) => num(v))} />
          <KeyValueTable title="Par secteur" rows={mapNumRecord(asRecord(pnl.by_sector), (v) => num(v))} />
          <KeyValueTable title="Par sleeve" rows={mapNumRecord(asRecord(pnl.by_sleeve), (v) => num(v))} />
        </div>
      </SectionCard>

      <CollapsibleRaw label="Réponse API complète (book-summary)" data={summary} />
    </div>
  );
};

function mapNumRecord(rec: JsonRecord, fmt: (v: unknown) => string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(rec)) {
    out[k] = fmt(v);
  }
  return out;
}

export default BookSummaryView;
