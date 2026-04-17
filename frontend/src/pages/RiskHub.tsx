import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const RiskHub: React.FC = () => {
  const [risk, setRisk] = useState<JsonRecord | null>(null);
  const [stress, setStress] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [r, s] = await Promise.all([
          ApiService.get<JsonRecord>('/api/book-risk'),
          ApiService.get<JsonRecord>('/api/stress'),
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
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#8b949e]">
        Portfolio risk posture and stress scenarios. See also{' '}
        <Link className="text-primary underline" to="/risk">Risk detail</Link> and{' '}
        <Link className="text-primary underline" to="/stress">Stress</Link>.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <JsonPanel title="Book risk (/api/book-risk)" data={risk} />
        <JsonPanel title="Stress test (/api/stress)" data={stress} />
      </div>
    </div>
  );
};

export default RiskHub;
