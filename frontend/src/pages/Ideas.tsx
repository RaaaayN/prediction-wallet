import React, { startTransition, useCallback, useEffect, useState } from 'react';
import { ApiService, ApiError } from '../api/service';
import type { IdeaBookRow } from '../types';

const Ideas: React.FC = () => {
  const [rows, setRows] = useState<IdeaBookRow[]>([]);
  const [status, setStatus] = useState('');
  const [reviewStatus, setReviewStatus] = useState('');
  const [llmOnly, setLlmOnly] = useState<boolean | ''>('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [cycleId, setCycleId] = useState('');
  const [maxCand, setMaxCand] = useState(3);

  const load = useCallback(async () => {
    setLoading(true);
    setMsg(null);
    try {
      const params = new URLSearchParams();
      if (status) params.set('status', status);
      if (reviewStatus) params.set('review_status', reviewStatus);
      if (llmOnly !== '') params.set('llm_generated', String(llmOnly));
      const q = params.toString();
      const path = q ? `/api/idea-book?${q}` : '/api/idea-book';
      setRows(await ApiService.get<IdeaBookRow[]>(path));
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : 'Failed to load ideas');
    } finally {
      setLoading(false);
    }
  }, [status, reviewStatus, llmOnly]);

  useEffect(() => {
    startTransition(() => {
      void load();
    });
  }, [load]);

  const generate = async () => {
    setLoading(true);
    setMsg(null);
    try {
      await ApiService.postJson<IdeaBookRow[]>('/api/idea-book/generate', {
        cycle_id: cycleId || null,
        max_candidates: maxCand,
      });
      await load();
      setMsg('Generation complete.');
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : 'Generate failed');
    } finally {
      setLoading(false);
    }
  };

  const review = async (ideaId: string, rs: 'pending_review' | 'approved' | 'rejected') => {
    setLoading(true);
    setMsg(null);
    try {
      await ApiService.postJson<{ ok: boolean }>(`/api/idea-book/${ideaId}/review`, { review_status: rs });
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : 'Review failed');
    } finally {
      setLoading(false);
    }
  };

  const promote = async (ideaId: string, st: 'candidate' | 'watchlist' | 'investable' | 'portfolio') => {
    setLoading(true);
    setMsg(null);
    try {
      await ApiService.postJson<{ ok: boolean }>(`/api/idea-book/${ideaId}/promote`, { status: st });
      await load();
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : 'Promote failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-3 items-end bg-card-bg border border-border rounded-lg p-4">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-[#8b949e] uppercase">status</span>
          <input
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            placeholder="any"
            className="bg-gray-bg border border-border rounded px-2 py-1 text-sm w-32"
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-[#8b949e] uppercase">review_status</span>
          <input
            value={reviewStatus}
            onChange={(e) => setReviewStatus(e.target.value)}
            placeholder="any"
            className="bg-gray-bg border border-border rounded px-2 py-1 text-sm w-36"
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-[#8b949e] uppercase">llm_generated</span>
          <select
            value={llmOnly === '' ? '' : llmOnly ? 'true' : 'false'}
            onChange={(e) => {
              const v = e.target.value;
              setLlmOnly(v === '' ? '' : v === 'true');
            }}
            className="bg-gray-bg border border-border rounded px-2 py-1 text-sm"
          >
            <option value="">any</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => void load()}
          className="px-3 py-1.5 rounded bg-[#21262d] border border-border text-sm hover:border-primary"
        >
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-3 items-end bg-card-bg border border-border rounded-lg p-4">
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-[#8b949e] uppercase">cycle_id (optional)</span>
          <input
            value={cycleId}
            onChange={(e) => setCycleId(e.target.value)}
            className="bg-gray-bg border border-border rounded px-2 py-1 text-sm w-48"
          />
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[11px] text-[#8b949e] uppercase">max_candidates</span>
          <input
            type="number"
            min={1}
            max={10}
            value={maxCand}
            onChange={(e) => setMaxCand(Number(e.target.value) || 1)}
            className="bg-gray-bg border border-border rounded px-2 py-1 text-sm w-20"
          />
        </div>
        <button
          type="button"
          disabled={loading}
          onClick={() => void generate()}
          className="px-3 py-1.5 rounded bg-primary text-white text-sm font-semibold disabled:opacity-50"
        >
          Generate candidates
        </button>
      </div>

      {msg && <div className="text-sm text-yellow">{msg}</div>}

      <div className="bg-card-bg border border-border rounded-lg p-4 overflow-x-auto">
        <table>
          <thead>
            <tr>
              <th>Idea</th>
              <th>Ticker</th>
              <th>Side</th>
              <th>Status</th>
              <th>Review</th>
              <th>LLM</th>
              <th className="text-left">Thesis</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.idea_id}>
                <td className="font-mono text-xs text-primary whitespace-nowrap">{row.idea_id}</td>
                <td className="font-mono">{row.ticker}</td>
                <td>{row.side}</td>
                <td className="text-xs">{row.status}</td>
                <td className="text-xs">{row.review_status ?? '—'}</td>
                <td>{row.llm_generated ? 'Y' : 'N'}</td>
                <td className="max-w-md text-xs text-[#c9d1d9]">{row.thesis}</td>
                <td className="text-xs whitespace-nowrap">
                  <div className="flex flex-col gap-1">
                    <button
                      type="button"
                      className="text-primary hover:underline"
                      onClick={() => void review(row.idea_id, 'approved')}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="text-yellow hover:underline"
                      onClick={() => void review(row.idea_id, 'rejected')}
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      className="text-green hover:underline"
                      onClick={() => void promote(row.idea_id, 'watchlist')}
                    >
                      → watchlist
                    </button>
                    <button
                      type="button"
                      className="text-green hover:underline"
                      onClick={() => void promote(row.idea_id, 'investable')}
                    >
                      → investable
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Ideas;
