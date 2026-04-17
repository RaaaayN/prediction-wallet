import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const Analytics: React.FC = () => {
  const [backtest, setBacktest] = useState<JsonRecord | null>(null);
  const [corr, setCorr] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [b, c] = await Promise.all([
          ApiService.get<JsonRecord>('/api/backtest?days=90'),
          ApiService.get<JsonRecord>('/api/correlation?days=90'),
        ]);
        setBacktest(b);
        setCorr(c);
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#8b949e]">
        Quant analytics. Tune horizons via dedicated pages:{' '}
        <Link className="text-primary underline" to="/backtest">Backtest</Link>,{' '}
        <Link className="text-primary underline" to="/correlation">Correlation</Link>,{' '}
        <Link className="text-primary underline" to="/montecarlo">Monte Carlo</Link>.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <JsonPanel title="Backtest (90d)" data={backtest} />
        <JsonPanel title="Correlation (90d)" data={corr} />
      </div>
    </div>
  );
};

export default Analytics;
