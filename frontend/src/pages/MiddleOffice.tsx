import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import type { TC_Position, CashMovement, TC_Execution } from '../types';

const MiddleOffice: React.FC = () => {
  const [positions, setPositions] = useState<TC_Position[]>([]);
  const [movements, setMovements] = useState<CashMovement[]>([]);
  const [executions, setExecutions] = useState<TC_Execution[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [p, m, e] = await Promise.all([
          ApiService.get<TC_Position[]>('/api/trading-core/positions'),
          ApiService.get<CashMovement[]>('/api/trading-core/cash-movements?limit=20'),
          ApiService.get<TC_Execution[]>('/api/trading-core/executions?limit=20'),
        ]);
        setPositions(p);
        setMovements(m);
        setExecutions(e);
      } catch (ex) {
        setErr(ex instanceof Error ? ex.message : 'Failed to load Middle Office data');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm p-4">Error: {err}</div>;
  if (loading) return <div className="text-primary text-sm p-4 animate-pulse">Loading Ledger state...</div>;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Position Ledger */}
        <SectionCard 
          title="Aggregate Position Ledger" 
          subtitle="Real-time source of truth for holdings"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#8b949e] border-b border-border">
                  <th className="pb-2 font-medium">Ticker</th>
                  <th className="pb-2 text-right font-medium">Quantity</th>
                  <th className="pb-2 text-right font-medium">Avg Cost</th>
                  <th className="pb-2 text-right font-medium">Market Value</th>
                </tr>
              </thead>
              <tbody>
                {positions.length === 0 ? (
                  <tr><td colSpan={4} className="py-4 text-center text-[#8b949e]">No open positions in ledger</td></tr>
                ) : (
                  positions.map((p) => (
                    <tr key={p.instrument_id} className="border-b border-border/40 hover:bg-white/5 transition-colors">
                      <td className="py-2 font-mono font-bold text-[#e6edf3]">{p.symbol}</td>
                      <td className="py-2 text-right font-mono">{p.quantity.toFixed(4)}</td>
                      <td className="py-2 text-right font-mono">${p.avg_cost.toFixed(2)}</td>
                      <td className="py-2 text-right font-mono font-bold">${p.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </SectionCard>

        {/* Cash Movements */}
        <SectionCard 
          title="Recent Cash Movements" 
          subtitle="Audit trail of all balance changes"
        >
          <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#8b949e] border-b border-border">
                  <th className="pb-2 font-medium">Time</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody>
                {movements.map((m) => (
                  <tr key={m.cash_movement_id} className="border-b border-border/40">
                    <td className="py-2 text-[#8b949e] whitespace-nowrap">{m.created_at.slice(5, 16).replace('T', ' ')}</td>
                    <td className="py-2">
                      <span className="text-[10px] uppercase font-bold text-[#e6edf3]">{m.movement_type.replace('trade_', '')}</span>
                      <div className="text-[10px] text-[#8b949e] truncate max-w-[120px]">{m.description}</div>
                    </td>
                    <td className={`py-2 text-right font-mono ${m.amount < 0 ? 'text-red' : 'text-green'}`}>
                      {m.amount < 0 ? '-' : '+'}${Math.abs(m.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      </div>

      {/* Executions V2 */}
      <SectionCard 
        title="Execution Blotter (Trading Core)" 
        subtitle="Detailed trade fulfillment with TCA metrics"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[#8b949e] border-b border-border">
                <th className="pb-2 font-medium">Time</th>
                <th className="pb-2 font-medium">Ticker</th>
                <th className="pb-2 font-medium">Side</th>
                <th className="pb-2 text-right font-medium">Qty</th>
                <th className="pb-2 text-right font-medium">Market</th>
                <th className="pb-2 text-right font-medium">Fill</th>
                <th className="pb-2 text-right font-medium">Slippage</th>
                <th className="pb-2 text-right font-medium">Fees</th>
                <th className="pb-2 text-right font-medium">Notional</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((e) => (
                <tr key={e.execution_id} className="border-b border-border/40 hover:bg-white/5 transition-colors">
                  <td className="py-2 text-[#8b949e] whitespace-nowrap">{e.executed_at.slice(5, 19).replace('T', ' ')}</td>
                  <td className="py-2 font-mono font-bold text-[#e6edf3]">{e.symbol}</td>
                  <td className={`py-2 uppercase font-bold ${e.side === 'buy' ? 'text-green' : 'text-orange'}`}>{e.side}</td>
                  <td className="py-2 text-right font-mono">{e.quantity.toFixed(4)}</td>
                  <td className="py-2 text-right font-mono">${e.market_price.toFixed(2)}</td>
                  <td className="py-2 text-right font-mono">${e.fill_price.toFixed(2)}</td>
                  <td className="py-2 text-right font-mono text-orange">${(Math.abs(e.fill_price - e.market_price) * e.quantity).toFixed(2)}</td>
                  <td className="py-2 text-right font-mono text-[#8b949e]">${e.fees.toFixed(2)}</td>
                  <td className="py-2 text-right font-mono font-bold">${e.notional.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
};

export default MiddleOffice;
