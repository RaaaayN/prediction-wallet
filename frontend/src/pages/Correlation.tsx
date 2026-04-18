import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import CollapsibleRaw from '../components/CollapsibleRaw';
import type { JsonRecord } from '../types';

const Correlation: React.FC = () => {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>(`/api/correlation?days=${days}`));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, [days]);

  if (err) return <div className="text-red text-sm">{err}</div>;

  const tickers = (data?.tickers as string[]) || [];
  const matrix = (data?.matrix as number[][]) || [];

  return (
    <div className="flex flex-col gap-4">
      <label className="text-xs text-[#8b949e] flex items-center gap-2">
        Jours
        <input
          type="number"
          min={30}
          max={365}
          value={days}
          onChange={(e) => setDays(Number(e.target.value) || 90)}
          className="bg-gray-bg border border-border rounded px-2 py-1 w-24 text-sm"
        />
      </label>
      <SectionCard title="Corrélation roulante" subtitle={`${data?.n_obs ?? 0} observations`}>
        {tickers.length >= 2 && matrix.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="text-sm">
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
                        {cell.toFixed(2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-[#8b949e]">
            {(data?.detail as string) || 'Données insuffisantes pour la matrice.'}
          </p>
        )}
        <CollapsibleRaw label="JSON correlation" data={data} />
      </SectionCard>
    </div>
  );
};

export default Correlation;
