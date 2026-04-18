import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { PortfolioSnapshot, AgentRun, ReconciliationBreak } from '../types';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { ShieldCheck, ShieldAlert } from 'lucide-react';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const Dashboard: React.FC = () => {
  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [breaks, setBreaks] = useState<ReconciliationBreak[]>([]);
  const [stress, setStress] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [pfData, runsData, bData, sData] = await Promise.all([
          ApiService.get<PortfolioSnapshot>('/api/portfolio'),
          ApiService.get<AgentRun[]>('/api/runs?limit=20'),
          ApiService.get<ReconciliationBreak[]>('/api/middle-office/reconcile').catch(() => []),
          ApiService.get<any[]>('/api/stress').catch(() => []),
        ]);
        setPortfolio(pfData);
        setRuns(runsData);
        setBreaks(bData || []);
        setStress(sData || []);
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const pnlWaterfallData = {
    labels: [...runs].reverse().map(r => r.cycle_id),
    datasets: [
      {
        label: 'P&L per Cycle',
        data: [...runs].reverse().map((r) => (typeof r.trades_count === 'number' ? r.trades_count : 0)),
        backgroundColor: (context: { raw?: unknown }) => {
          const value = typeof context.raw === 'number' ? context.raw : 0;
          return value >= 0 ? '#3fb95099' : '#f8514999';
        },
        borderColor: (context: { raw?: unknown }) => {
          const value = typeof context.raw === 'number' ? context.raw : 0;
          return value >= 0 ? '#3fb950' : '#f85149';
        },
        borderWidth: 1,
      },
    ],
  };

  const fmtUSD = (n: number | undefined) => n == null ? '--' : '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtPct = (n: number | undefined) => n == null ? '--' : (n * 100).toFixed(1) + '%';

  if (loading) return <div className="text-gray-500">Loading Dashboard...</div>;

  const lastRun = runs[0];
  const tv = portfolio?.total_value;
  const pk = portfolio?.peak_value;
  const drawdown = pk != null && pk !== 0 && tv != null ? (tv - pk) / pk : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* KPI CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Total Value</div>
          <div className="text-xl font-bold text-primary">{fmtUSD(portfolio?.total_value)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">P&L ($)</div>
          <div className={`text-xl font-bold ${(portfolio?.pnl_dollars ?? 0) >= 0 ? 'text-green' : 'text-red'}`}>
            {fmtUSD(portfolio?.pnl_dollars)}
          </div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">P&L (%)</div>
          <div className={`text-xl font-bold ${(portfolio?.pnl_pct ?? 0) >= 0 ? 'text-green' : 'text-red'}`}>
            {fmtPct(portfolio?.pnl_pct)}
          </div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Max Drawdown</div>
          <div className="text-xl font-bold text-red">{fmtPct(drawdown)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Last Cycle</div>
          <div className="text-sm font-bold text-[#e6edf3]">{lastRun?.cycle_id || '--'}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4 flex flex-col justify-between">
          <div className="text-xs text-[#8b949e] mb-1">Agent Status</div>
          <div>
            <span className="bg-[#1b2a3d] text-primary text-[10px] px-2 py-0.5 rounded-full font-medium uppercase">
              {loading ? 'BUSY' : 'IDLE'}
            </span>
          </div>
        </div>
      </div>

      {/* CHART */}
      <div className="bg-card-bg border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Trades per cycle (recent runs)</h2>
        </div>
        <div className="h-[240px]">
          <Bar
            data={pnlWaterfallData}
            options={{
              responsive: true,
              maintainAspectRatio: false,
              plugins: { legend: { display: false } },
              scales: {
                x: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { display: false } },
                y: { ticks: { color: '#8b949e', font: { size: 10 } }, grid: { color: '#21262d' } },
              },
            }}
          />
        </div>
      </div>

      {/* LOWER GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Last 5 Cycles</h2>
          <div className="flex flex-col gap-2">
            {runs.slice(0, 5).map((run) => (
              <div key={run.cycle_id} className="flex items-center justify-between text-sm py-1 border-b border-[#21262d] last:border-0">
                <span className="font-mono text-primary">{run.cycle_id}</span>
                <span className="text-xs text-[#8b949e]">{run.timestamp.slice(0, 16).replace('T', ' ')}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${run.signal ? 'bg-[#1a4731] text-green' : 'bg-[#3d2d0a] text-yellow'}`}>
                  {run.signal ? 'REBALANCE' : 'IDLE'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card-bg border border-border rounded-lg p-4">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Risk & Middle Office</h2>
          <div className="flex flex-col gap-3">
             <div className={`p-2 rounded border flex items-center gap-2 text-xs font-bold ${breaks.length === 0 ? 'bg-green/10 border-green/30 text-green' : 'bg-red/10 border-red/30 text-red'}`}>
               {breaks.length === 0 ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
               {breaks.length === 0 ? 'RECONCILIATION MATCH' : `${breaks.length} RECON BREAKS`}
             </div>
             
             <div className="flex flex-col gap-1.5">
               <div className="text-[10px] text-[#8b949e] uppercase font-semibold">Crisis Stress Check</div>
               {stress.slice(0, 2).map((s, i) => (
                 <div key={i} className="bg-gray-bg border border-border/40 rounded p-1.5 text-[10px]">
                   <div className="flex justify-between items-center mb-1">
                     <span className="font-mono">{s.scenario.replace('_', ' ')}</span>
                     <span className={s.pnl_pct < 0 ? 'text-red' : 'text-green'}>{(s.pnl_pct * 100).toFixed(1)}%</span>
                   </div>
                   <div className="w-full bg-border/20 h-1 rounded-full">
                     <div className="h-full bg-orange" style={{ width: `${Math.min(Math.abs(s.pnl_pct) * 200, 100)}%` }}></div>
                   </div>
                 </div>
               ))}
             </div>
          </div>
        </div>

        <div className="bg-card-bg border border-border rounded-lg p-4">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Kill Switch Status</h2>
          <div className={`p-3 rounded-lg border font-semibold text-sm ${lastRun?.kill_switch ? 'bg-[#3d1a1a] border-red text-red' : 'bg-[#1a4731] border-green text-green'}`}>
            {lastRun?.kill_switch ? '⚠️ KILL SWITCH ACTIVE' : '✓ KILL SWITCH NOMINAL'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
