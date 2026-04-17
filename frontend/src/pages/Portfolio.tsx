import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { PortfolioSnapshot, Position } from '../types';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';

ChartJS.register(ArcElement, Tooltip, Legend);

const Portfolio: React.FC = () => {
  const [portfolio, setPortfolio] = useState<PortfolioSnapshot | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [pfData, posData] = await Promise.all([
          ApiService.get<PortfolioSnapshot>('/api/portfolio'),
          ApiService.get<Position[]>('/api/positions'),
        ]);
        setPortfolio(pfData);
        setPositions(posData);
      } catch (err) {
        console.error('Error fetching portfolio:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const fmtUSD = (n: number | undefined) => n == null ? '--' : '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtPct = (n: number | undefined) => n == null ? '--' : (n * 100).toFixed(1) + '%';

  const chartColors = ['#58a6ff', '#3fb950', '#e3b341', '#f85149', '#8957e5', '#79c0ff', '#56d364', '#ffa657', '#ff7b72'];

  const doughnutData = {
    labels: positions.map(p => p.ticker),
    datasets: [{
      data: positions.map(p => (p.weight || 0) * 100),
      backgroundColor: chartColors.map(c => c + '99'),
      borderColor: chartColors,
      borderWidth: 1.5,
    }]
  };

  if (loading) return <div className="text-gray-500">Loading Portfolio...</div>;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Total Value</div>
          <div className="text-xl font-bold text-primary">{fmtUSD(portfolio?.total_value)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Cash</div>
          <div className="text-xl font-bold text-green">{fmtUSD(portfolio?.cash)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">PnL ($)</div>
          <div className={`text-xl font-bold ${(portfolio?.pnl_dollars ?? 0) >= 0 ? 'text-green' : 'text-red'}`}>{fmtUSD(portfolio?.pnl_dollars)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">PnL (%)</div>
          <div className={`text-xl font-bold ${(portfolio?.pnl_pct ?? 0) >= 0 ? 'text-green' : 'text-red'}`}>{fmtPct(portfolio?.pnl_pct)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Peak Value</div>
          <div className="text-lg font-bold text-[#e6edf3]">{fmtUSD(portfolio?.peak_value)}</div>
        </div>
        <div className="bg-card-bg border border-border rounded-lg p-4">
          <div className="text-xs text-[#8b949e] mb-1">Drawdown</div>
          <div className="text-lg font-bold text-red">
            {fmtPct(
              portfolio?.peak_value != null &&
                portfolio.peak_value !== 0 &&
                portfolio.total_value != null
                ? (portfolio.total_value - portfolio.peak_value) / portfolio.peak_value
                : 0,
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="bg-card-bg border border-border rounded-lg p-4 lg:col-span-1">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Allocation</h2>
          <div className="h-[220px]">
            <Doughnut
              data={doughnutData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: { legend: { display: false } }
              }}
            />
          </div>
          <div className="mt-4 flex flex-col gap-2">
            {positions.map((p, i) => (
              <div key={p.ticker} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: chartColors[i % chartColors.length] }}></div>
                  <span className="font-mono text-[#c9d1d9]">{p.ticker}</span>
                </div>
                <span className="text-[#8b949e]">{fmtPct(p.weight)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card-bg border border-border rounded-lg p-4 lg:col-span-3">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Positions</h2>
          <div className="overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th className="text-left">Ticker</th>
                  <th className="text-right">Qty</th>
                  <th className="text-right">Price</th>
                  <th className="text-right">Value</th>
                  <th className="text-right">Weight</th>
                  <th className="text-right">Target</th>
                  <th className="text-right">Drift</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const driftPct = (p.drift || 0) * 100;
                  return (
                    <tr key={p.ticker}>
                      <td className="font-mono font-semibold text-primary">{p.ticker}</td>
                      <td className="text-right font-mono text-xs">{p.quantity.toFixed(4)}</td>
                      <td className="text-right">{fmtUSD(p.price)}</td>
                      <td className="text-right">{fmtUSD(p.value)}</td>
                      <td className="text-right">{fmtPct(p.weight)}</td>
                      <td className="text-right text-[#8b949e]">{fmtPct(p.target_weight)}</td>
                      <td className={`text-right font-semibold ${driftPct > 1.5 ? 'text-red' : driftPct < -1.5 ? 'text-green' : 'text-[#8b949e]'}`}>
                        {driftPct >= 0 ? '+' : ''}{driftPct.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Portfolio;
