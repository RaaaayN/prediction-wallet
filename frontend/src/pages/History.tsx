import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { SnapshotRow } from '../types';

const History: React.FC = () => {
  const [rows, setRows] = useState<SnapshotRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRows(await ApiService.get<SnapshotRow[]>('/api/snapshots?limit=200'));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="bg-card-bg border border-border rounded-lg p-4 overflow-x-auto">
      <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Portfolio snapshots</h2>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Cycle</th>
            <th className="text-right">Total</th>
            <th className="text-right">Cash</th>
            <th className="text-right">DD</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.id ?? r.cycle_id}-${r.timestamp}`}>
              <td className="font-mono text-xs whitespace-nowrap">{r.timestamp?.slice(0, 19)}</td>
              <td className="font-mono text-xs text-primary">{r.cycle_id}</td>
              <td className="text-right font-mono text-xs">{r.total_value?.toFixed?.(2)}</td>
              <td className="text-right font-mono text-xs">{r.cash?.toFixed?.(2)}</td>
              <td className="text-right text-xs">{(Number(r.drawdown) * 100).toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default History;
