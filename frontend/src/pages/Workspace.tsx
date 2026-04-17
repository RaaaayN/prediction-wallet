import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const Workspace: React.FC = () => {
  const [summary, setSummary] = useState<JsonRecord | null>(null);
  const [cfg, setCfg] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [s, c] = await Promise.all([
          ApiService.get<JsonRecord>('/api/book-summary'),
          ApiService.get<JsonRecord>('/api/config'),
        ]);
        setSummary(s);
        setCfg(c);
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-[#8b949e]">
        Hedge-fund book view: exposures, risk classification, and P&amp;L attribution. Open{' '}
        <Link className="text-primary underline" to="/book">Book Summary</Link>,{' '}
        <Link className="text-primary underline" to="/ideas">Idea Book</Link>, or{' '}
        <Link className="text-primary underline" to="/blotter">Blotter</Link>.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <JsonPanel title="Book summary (/api/book-summary)" data={summary} />
        <JsonPanel title="Config (/api/config)" data={cfg} />
      </div>
    </div>
  );
};

export default Workspace;
