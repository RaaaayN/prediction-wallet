import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import StatCard from '../components/StatCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { PortfolioSnapshot, SnapshotRow } from '../types';

const Perf: React.FC = () => {
  const [snapshots, setSnapshots] = useState<SnapshotRow[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [s, p] = await Promise.all([
          ApiService.get<SnapshotRow[]>('/api/snapshots?limit=120'),
          ApiService.get<PortfolioSnapshot>('/api/portfolio'),
        ]);
        setSnapshots(s);
        setPortfolio(p);
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  const last = snapshots[snapshots.length - 1];

  return (
    <div className="flex flex-col gap-6">
      <SectionCard title="Performance (snapshots)" subtitle="Valeur et drawdown récents">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <StatCard
            label="Valeur actuelle"
            value={portfolio?.total_value != null ? fmtUsd(portfolio.total_value) : '—'}
          />
          <StatCard label="P&amp;L %" value={portfolio?.pnl_pct != null ? `${(portfolio.pnl_pct * 100).toFixed(2)}%` : '—'} />
          <StatCard label="Snapshots" value={String(snapshots.length)} />
          <StatCard label="DD dernier" value={typeof last?.drawdown === 'number' ? `${(last.drawdown * 100).toFixed(2)}%` : '—'} />
        </div>
        <CollapsibleRaw label="Série snapshots (extrait)" data={snapshots.slice(-20)} />
      </SectionCard>
    </div>
  );
};

function fmtUsd(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

export default Perf;
