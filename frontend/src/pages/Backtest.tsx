import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const Backtest: React.FC = () => {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>(`/api/backtest?days=${days}`));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, [days]);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-3">
      <label className="text-xs text-[#8b949e] flex items-center gap-2">
        Days
        <input
          type="number"
          min={30}
          max={3650}
          value={days}
          onChange={(e) => setDays(Number(e.target.value) || 90)}
          className="bg-gray-bg border border-border rounded px-2 py-1 w-24 text-sm"
        />
      </label>
      <JsonPanel title="Backtest" data={data} />
    </div>
  );
};

export default Backtest;
