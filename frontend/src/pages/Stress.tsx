import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import StressScenariosView from '../components/StressScenariosView';

const Stress: React.FC = () => {
  const [data, setData] = useState<unknown>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<unknown>('/api/stress'));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;
  return <StressScenariosView rows={data} />;
};

export default Stress;
