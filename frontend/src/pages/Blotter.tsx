import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { ExecutionResult } from '../types';

const Blotter: React.FC = () => {
  const [rows, setRows] = useState<ExecutionResult[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setRows(await ApiService.get<ExecutionResult[]>('/api/executions?limit=200'));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="bg-card-bg border border-border rounded-lg p-4 overflow-x-auto">
      <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Executions</h2>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Cycle</th>
            <th>Ticker</th>
            <th>Action</th>
            <th className="text-right">Qty</th>
            <th className="text-right">Fill</th>
            <th className="text-right">Slippage %</th>
            <th>OK</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.cycle_id}-${r.timestamp}-${r.ticker}-${r.action}`}>
              <td className="font-mono text-xs whitespace-nowrap">{r.timestamp?.slice(0, 19)}</td>
              <td className="font-mono text-xs text-primary">{r.cycle_id}</td>
              <td className="font-mono">{r.ticker}</td>
              <td>{r.action}</td>
              <td className="text-right font-mono text-xs">{r.quantity?.toFixed?.(4)}</td>
              <td className="text-right font-mono text-xs">{r.fill_price?.toFixed?.(2)}</td>
              <td className="text-right text-xs">{(Number(r.slippage_pct) * 100).toFixed(3)}%</td>
              <td>{r.success === true || r.success === 1 ? '✓' : '✗'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Blotter;
