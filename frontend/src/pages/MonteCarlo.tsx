import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const MonteCarlo: React.FC = () => {
  const [paths, setPaths] = useState(5000);
  const [data, setData] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>(`/api/monte-carlo?paths=${paths}`));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, [paths]);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-3">
      <label className="text-xs text-[#8b949e] flex items-center gap-2">
        Paths
        <input
          type="number"
          min={100}
          max={20000}
          step={100}
          value={paths}
          onChange={(e) => setPaths(Number(e.target.value) || 5000)}
          className="bg-gray-bg border border-border rounded px-2 py-1 w-28 text-sm"
        />
      </label>
      <JsonPanel title="Monte Carlo" data={data} />
    </div>
  );
};

export default MonteCarlo;
