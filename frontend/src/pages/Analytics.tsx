import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { JsonRecord } from '../types';

function asRecord(x: unknown): JsonRecord {
  return x !== null && typeof x === 'object' && !Array.isArray(x) ? (x as JsonRecord) : {};
}

const Analytics: React.FC = () => {
  const [backtest, setBacktest] = useState<JsonRecord | null>(null);
  const [corr, setCorr] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [b, c] = await Promise.all([
          ApiService.get<JsonRecord>('/api/backtest?days=90'),
          ApiService.get<JsonRecord>('/api/correlation?days=90'),
        ]);
        setBacktest(b);
        setCorr(c);
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  const strategies = backtest ? Object.keys(backtest).filter((k) => !['error', 'detail'].includes(k)) : [];
  const safeCorr = corr ?? {};
  const matrix = (safeCorr.matrix as unknown[][]) || [];
  const tickers = (safeCorr.tickers as string[]) || [];

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-[#8b949e]">
        Synthèse quantitative. Pages dédiées :{' '}
        <Link className="text-primary hover:underline" to="/backtest">
          Backtest
        </Link>
        ,{' '}
        <Link className="text-primary hover:underline" to="/correlation">
          Correlation
        </Link>
        ,{' '}
        <Link className="text-primary hover:underline" to="/montecarlo">
          Monte Carlo
        </Link>
        .
      </p>

      <SectionCard title="Backtest (90 jours)" subtitle="Seuil vs calendrier vs buy-and-hold">
        {strategies.length === 0 ? (
          <p className="text-sm text-[#8b949e]">Pas de résultats (données marché ou portefeuille insuffisants).</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {strategies.map((name) => {
              const s = asRecord(backtest![name]);
              return (
                <div key={name} className="rounded-lg border border-[#21262d] p-4 space-y-2">
                  <div className="text-sm font-semibold text-primary capitalize">{name.replace(/_/g, ' ')}</div>
                  <StatCard label="Sharpe" value={fmt(s.sharpe)} />
                  <StatCard label="Max DD" value={fmt(s.max_dd)} />
                  <StatCard label="Trades" value={String(s.n_trades ?? '—')} />
                  <StatCard label="Coûts" value={fmt(s.costs)} />
                </div>
              );
            })}
          </div>
        )}
        <CollapsibleRaw label="JSON backtest" data={backtest} />
      </SectionCard>

      <SectionCard title="Corrélation (aperçu)" subtitle={`${safeCorr.n_obs ?? 0} obs.`}>
        {tickers.length >= 2 && matrix.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="text-xs">
              <thead>
                <tr>
                  <th />
                  {tickers.map((t) => (
                    <th key={t} className="font-mono">
                      {t}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {matrix.map((row, i) => (
                  <tr key={tickers[i] ?? i}>
                    <td className="font-mono text-primary">{tickers[i]}</td>
                    {row.map((cell, j) => (
                      <td key={`${i}-${j}`} className="text-center font-mono">
                        {typeof cell === 'number' ? cell.toFixed(2) : String(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[#8b949e]">
            {(safeCorr.detail as string) || 'Matrice indisponible (positions ou historique insuffisants).'}
          </p>
        )}
        <CollapsibleRaw label="JSON correlation" data={corr ?? {}} />
      </SectionCard>
    </div>
  );
};

function fmt(n: unknown): string {
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  return n.toFixed(3);
}

export default Analytics;
