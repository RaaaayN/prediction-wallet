import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import RiskBookPanel from '../components/RiskBookPanel';
import StressScenariosView from '../components/StressScenariosView';
import type { JsonRecord } from '../types';

const RiskHub: React.FC = () => {
  const [risk, setRisk] = useState<JsonRecord | null>(null);
  const [stress, setStress] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [r, s] = await Promise.all([
          ApiService.get<JsonRecord>('/api/book-risk'),
          ApiService.get<unknown>('/api/stress'),
        ]);
        setRisk(r);
        setStress(s);
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-[#8b949e]">
        Centre de risque. Détail :{' '}
        <Link className="text-primary hover:underline" to="/risk">
          Risk detail
        </Link>
        ,{' '}
        <Link className="text-primary hover:underline" to="/stress">
          Stress
        </Link>
        ,{' '}
        <Link className="text-primary hover:underline" to="/regime">
          Regime
        </Link>
        .
      </p>
      <RiskBookPanel risk={risk} />
      <StressScenariosView rows={stress} />
    </div>
  );
};

export default RiskHub;
