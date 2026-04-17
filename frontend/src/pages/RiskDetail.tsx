import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const RiskDetail: React.FC = () => {
  const [risk, setRisk] = useState<JsonRecord | null>(null);
  const [exp, setExp] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [r, e] = await Promise.all([
          ApiService.get<JsonRecord>('/api/book-risk'),
          ApiService.get<JsonRecord>('/api/exposures'),
        ]);
        setRisk(r);
        setExp(e);
      } catch (ex) {
        setErr(ex instanceof Error ? ex.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <JsonPanel title="Book risk" data={risk} />
      <JsonPanel title="Exposures" data={exp} />
    </div>
  );
};

export default RiskDetail;
