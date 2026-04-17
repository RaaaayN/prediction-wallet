import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { AgentRun } from '../types';

const Runs: React.FC = () => {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRuns(await ApiService.get<AgentRun[]>('/api/runs?limit=50'));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="bg-card-bg border border-border rounded-lg p-4 overflow-x-auto">
      <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Agent runs</h2>
      <table>
        <thead>
          <tr>
            <th>Cycle</th>
            <th>Time</th>
            <th>Strategy</th>
            <th>Signal</th>
            <th className="text-right">Trades</th>
            <th>Kill</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.cycle_id}>
              <td className="font-mono text-xs text-primary">{r.cycle_id}</td>
              <td className="font-mono text-xs whitespace-nowrap">{r.timestamp?.slice(0, 19)}</td>
              <td className="text-xs">{r.strategy ?? '—'}</td>
              <td>{r.signal === true || r.signal === 1 ? 'Y' : 'N'}</td>
              <td className="text-right">{r.trades_count}</td>
              <td>{r.kill_switch ? 'Y' : 'N'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Runs;
