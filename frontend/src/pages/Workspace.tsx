import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ApiService } from '../api/service';
import BookSummaryView from '../components/BookSummaryView';
import ConfigStrip from '../components/ConfigStrip';
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
    <div className="flex flex-col gap-6">
      <p className="text-sm text-[#8b949e] leading-relaxed">
        Vue <strong className="text-[#e6edf3]">livre hedge fund</strong> : expositions, risque et attribution. Enchaîne avec{' '}
        <Link className="text-primary hover:underline" to="/ideas">
          Idea Book
        </Link>
        ,{' '}
        <Link className="text-primary hover:underline" to="/blotter">
          Blotter
        </Link>{' '}
        ou{' '}
        <Link className="text-primary hover:underline" to="/risk">
          Risk detail
        </Link>
        .
      </p>
      <BookSummaryView summary={summary} />
      <ConfigStrip cfg={cfg} />
    </div>
  );
};

export default Workspace;
