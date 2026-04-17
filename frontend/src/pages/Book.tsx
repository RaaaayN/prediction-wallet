import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import JsonPanel from '../components/JsonPanel';
import type { JsonRecord } from '../types';

const Book: React.FC = () => {
  const [data, setData] = useState<JsonRecord | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setData(await ApiService.get<JsonRecord>('/api/book-summary'));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed to load');
      }
    })();
  }, []);

  if (err) return <div className="text-red text-sm">{err}</div>;
  return <JsonPanel title="Book summary" data={data} />;
};

export default Book;
