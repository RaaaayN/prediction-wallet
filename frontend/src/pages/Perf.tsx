import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord, PortfolioSnapshot, SnapshotRow } from '../types';

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

  const summary: JsonRecord = {
    current_total: portfolio?.total_value,
    snapshot_count: snapshots.length,
    first_ts: snapshots[0]?.timestamp,
    last_ts: snapshots[snapshots.length - 1]?.timestamp,
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <JsonPanel title="Performance snapshot" data={summary} />
      <JsonPanel title="Snapshots (120)" data={snapshots} />
    </div>
  );
};

export default Perf;
