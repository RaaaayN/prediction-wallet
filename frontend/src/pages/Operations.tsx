import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ApiService } from '../api/service';
import type { TradePreview, TradeOpinion, ExecutionResult } from '../types';
import { Brain, CheckCircle2, XCircle, AlertTriangle, RefreshCw } from 'lucide-react';

const OPINION_COLORS = {
  APPROVE: { bg: 'bg-[#1a4731]', text: 'text-[#3fb950]', icon: <CheckCircle2 size={14} /> },
  CAUTION: { bg: 'bg-[#3d2e0a]', text: 'text-[#d29922]', icon: <AlertTriangle size={14} /> },
  REJECT: { bg: 'bg-[#3d1a1a]', text: 'text-[#f85149]', icon: <XCircle size={14} /> },
};

const Operations: React.FC = () => {
  const [ticker, setTicker] = useState('');
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [quantity, setQuantity] = useState('');
  const [preview, setPreview] = useState<TradePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');
  const [opinion, setOpinion] = useState<TradeOpinion | null>(null);
  const [opinionLoading, setOpinionLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [executing, setExecuting] = useState(false);
  const [recentTrades, setRecentTrades] = useState<ExecutionResult[]>([]);
  const [stressResults, setStressResults] = useState<any[]>([]);
  const [stressLoading, setStressLoading] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchStress = async () => {
    if (!ticker) {
      setStressResults([]);
      return;
    }
    setStressLoading(true);
    try {
      // For now we use the global stress endpoint as a proxy for 'current status'
      // In a real What-If, we'd pass the proposed trade to the backend.
      const data = await ApiService.get<any[]>('/api/stress');
      setStressResults(data);
    } catch {
      setStressResults([]);
    } finally {
      setStressLoading(false);
    }
  };

  const fetchPreview = useCallback(() => {
    const qty = parseFloat(quantity);
    if (!ticker || qty <= 0) {
      setPreview(null);
      setPreviewError('');
      return;
    }
    setPreviewLoading(true);
    setPreviewError('');
    ApiService.postJson<TradePreview>('/api/trade/preview', { action: side, ticker: ticker.toUpperCase(), quantity: qty })
      .then((data) => {
        setPreview(data);
        setPreviewLoading(false);
      })
      .catch((err) => {
        setPreviewError(err?.message ?? 'Could not fetch preview');
        setPreview(null);
        setPreviewLoading(false);
      });
  }, [ticker, side, quantity]);

  useEffect(() => {
    setOpinion(null);
    setResult(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(fetchPreview, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [fetchPreview]);

  useEffect(() => {
    ApiService.get<ExecutionResult[]>('/api/executions?limit=50')
      .then((data) => setRecentTrades(data.filter((t) => t.cycle_id?.startsWith('manual-'))))
      .catch(() => {});
  }, [result]);

  const handleGetOpinion = async () => {
    if (!preview) return;
    setOpinionLoading(true);
    setOpinion(null);
    try {
      const data = await ApiService.postJson<TradeOpinion>('/api/trade/opinion', {
        action: side,
        ticker: ticker.toUpperCase(),
        quantity: parseFloat(quantity),
        current_price: preview.current_price,
      });
      setOpinion(data);
    } catch {
      setOpinion({ recommendation: 'CAUTION', rationale: 'Could not get AI opinion.', confidence: 0.5, risk_flags: [], market_context: '' });
    } finally {
      setOpinionLoading(false);
    }
  };

  const handleExecute = async () => {
    setExecuting(true);
    setShowConfirm(false);
    try {
      const data = await ApiService.postJson<Record<string, unknown>>('/api/trade/execute', {
        action: side,
        ticker: ticker.toUpperCase(),
        quantity: parseFloat(quantity),
        reason: 'Manual trade via Operations page',
      });
      const ok = data.success === true || data.success === 1;
      setResult({ success: ok, message: ok ? `Trade executed: ${side.toUpperCase()} ${quantity} ${ticker.toUpperCase()} @ $${(data.fill_price as number)?.toFixed(2)}` : String(data.error ?? 'Execution failed') });
      if (ok) {
        setTicker('');
        setQuantity('');
        setPreview(null);
        setOpinion(null);
      }
    } catch (err: unknown) {
      setResult({ success: false, message: (err as Error)?.message ?? 'Execution failed' });
    } finally {
      setExecuting(false);
    }
  };

  const canExecute = !!preview && !executing && !previewError && parseFloat(quantity) > 0;

  return (
    <div>
      <h1 className="text-xl font-bold text-[#e6edf3] mb-1">Operations</h1>
      <p className="text-[#8b949e] text-sm mb-6">Execute manual trades on any asset. Get an AI opinion before committing.</p>

      {result && (
        <div className={`mb-4 p-3 rounded-lg border text-sm flex items-center gap-2 ${result.success ? 'bg-[#1a4731] border-[#3fb950] text-[#3fb950]' : 'bg-[#3d1a1a] border-[#f85149] text-[#f85149]'}`}>
          {result.success ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          {result.message}
          <button onClick={() => setResult(null)} className="ml-auto text-current opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT — Order Entry */}
        <div className="flex flex-col gap-4">
          <div className="bg-card-bg border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-4">Order Entry</h2>

            <div className="flex flex-col gap-4">
              <div>
                <label className="text-xs text-[#8b949e] mb-1 block">Ticker</label>
                <input
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value.toUpperCase())}
                  placeholder="e.g. AAPL, MSFT, BTC-USD"
                  className="w-full bg-gray-bg border border-border rounded-lg px-3 py-2 text-[#e6edf3] text-sm placeholder-[#8b949e] focus:outline-none focus:border-primary uppercase"
                />
              </div>

              <div>
                <label className="text-xs text-[#8b949e] mb-1 block">Side</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSide('buy')}
                    className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-all ${side === 'buy' ? 'bg-[#1a4731] border-[#3fb950] text-[#3fb950]' : 'border-border text-[#8b949e] hover:border-[#3fb950]'}`}
                  >
                    BUY
                  </button>
                  <button
                    onClick={() => setSide('sell')}
                    className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-all ${side === 'sell' ? 'bg-[#3d1a1a] border-[#f85149] text-[#f85149]' : 'border-border text-[#8b949e] hover:border-[#f85149]'}`}
                  >
                    SELL
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs text-[#8b949e] mb-1 block">Quantity (shares)</label>
                <input
                  type="number"
                  min="0"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  placeholder="0"
                  className="w-full bg-gray-bg border border-border rounded-lg px-3 py-2 text-[#e6edf3] text-sm placeholder-[#8b949e] focus:outline-none focus:border-primary"
                />
              </div>
            </div>
          </div>

          {/* Trade Preview */}
          <div className="bg-card-bg border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Trade Preview</h2>
              {previewLoading && <RefreshCw size={14} className="text-primary animate-spin" />}
            </div>

            {previewError && (
              <p className="text-xs text-[#f85149]">{previewError}</p>
            )}

            {!preview && !previewLoading && !previewError && (
              <p className="text-xs text-[#8b949e]">Enter ticker and quantity to see a preview.</p>
            )}

            {preview && (
              <div className="grid grid-cols-2 gap-2 text-xs">
                {[
                  ['Current Price', `$${preview.current_price.toFixed(2)}`],
                  ['Estimated Cost', `$${preview.estimated_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`],
                  ['Current Holding', `${preview.current_holding.toFixed(2)} sh`],
                  ['Current Weight', `${(preview.current_weight * 100).toFixed(2)}%`],
                  ['New Weight', `${(preview.new_weight * 100).toFixed(2)}%`],
                  ['Cash After', `$${preview.cash_after.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`],
                  ['Available Cash', `$${preview.available_cash.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`],
                  ['Portfolio Value', `$${preview.portfolio_value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`],
                ].map(([k, v]) => (
                  <div key={k} className="bg-gray-bg border border-border rounded p-2">
                    <div className="text-[#8b949e]">{k}</div>
                    <div className={`font-medium ${k === 'Cash After' && preview.cash_after < 0 ? 'text-[#f85149]' : 'text-[#e6edf3]'}`}>{v}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Opinion */}
          <div className="bg-card-bg border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">AI Opinion</h2>
              <button
                onClick={handleGetOpinion}
                disabled={!preview || opinionLoading}
                className="flex items-center gap-1.5 text-xs bg-primary/10 border border-primary text-primary px-3 py-1 rounded-lg hover:bg-primary/20 disabled:opacity-40 transition-all"
              >
                {opinionLoading ? <RefreshCw size={12} className="animate-spin" /> : <Brain size={12} />}
                {opinionLoading ? 'Analyzing…' : 'Get AI Opinion'}
              </button>
            </div>

            {!opinion && !opinionLoading && (
              <p className="text-xs text-[#8b949e]">Ask the AI what it thinks about this trade before executing.</p>
            )}

            {opinion && (() => {
              const style = OPINION_COLORS[opinion.recommendation] ?? OPINION_COLORS.CAUTION;
              return (
                <div className="flex flex-col gap-3">
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${style.bg} ${style.text}`}>
                    {style.icon} {opinion.recommendation}
                    <span className="ml-2 opacity-70">confidence {Math.round(opinion.confidence * 100)}%</span>
                  </div>
                  <p className="text-xs text-[#e6edf3] leading-relaxed">{opinion.rationale}</p>
                  {opinion.market_context && (
                    <p className="text-xs text-[#8b949e] italic">{opinion.market_context}</p>
                  )}
                  {opinion.risk_flags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {opinion.risk_flags.map((flag, i) => (
                        <span key={i} className="text-[10px] bg-[#3d2e0a] text-[#d29922] px-2 py-0.5 rounded-full">{flag}</span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
          </div>

          {/* Execute */}
          <button
            onClick={() => setShowConfirm(true)}
            disabled={!canExecute}
            className={`w-full py-3 rounded-lg font-semibold text-sm transition-all ${
              side === 'buy'
                ? 'bg-[#1a4731] hover:bg-[#238636] text-[#3fb950] border border-[#3fb950] disabled:opacity-30'
                : 'bg-[#3d1a1a] hover:bg-[#da3633] text-[#f85149] border border-[#f85149] disabled:opacity-30'
            }`}
          >
            {executing ? 'Executing…' : `${side === 'buy' ? 'Buy' : 'Sell'} ${quantity || '–'} ${ticker || 'shares'}`}
          </button>
        </div>

        {/* RIGHT — Context */}
        <div className="flex flex-col gap-4">
          {/* Current Position */}
          <div className="bg-card-bg border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Current Position</h2>
            {preview ? (
              <div className="flex flex-col gap-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[#8b949e]">Ticker</span>
                  <span className="font-mono font-bold text-[#e6edf3]">{ticker.toUpperCase()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#8b949e]">Shares held</span>
                  <span className="text-[#e6edf3]">{preview.current_holding.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#8b949e]">Portfolio weight</span>
                  <span className="text-[#e6edf3]">{(preview.current_weight * 100).toFixed(2)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#8b949e]">Market price</span>
                  <span className="text-[#e6edf3]">${preview.current_price.toFixed(2)}</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-[#8b949e]">Enter a ticker to see current position.</p>
            )}
          </div>

          {/* Recent Manual Trades */}
          <div className="bg-card-bg border border-border rounded-lg p-4">
            <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-3">Recent Manual Trades</h2>
            {recentTrades.length === 0 ? (
              <p className="text-xs text-[#8b949e]">No manual trades yet.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {recentTrades.slice(0, 10).map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-gray-bg border border-border rounded p-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${t.action === 'buy' ? 'bg-[#1a4731] text-[#3fb950]' : 'bg-[#3d1a1a] text-[#f85149]'}`}>
                        {t.action?.toUpperCase()}
                      </span>
                      <span className="font-mono text-[#e6edf3]">{t.ticker}</span>
                      <span className="text-[#8b949e]">{t.quantity?.toFixed(2)} sh</span>
                    </div>
                    <div className="text-right">
                      <div className="text-[#e6edf3]">${t.fill_price?.toFixed(2)}</div>
                      <div className="text-[#8b949e]">{t.timestamp?.slice(0, 10)}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Risk Stress Check */}
          <div className="bg-card-bg border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Pre-Trade Risk Check</h2>
              <button 
                onClick={fetchStress} 
                disabled={stressLoading || !ticker}
                className="text-[10px] bg-primary/10 border border-primary/30 text-primary px-2 py-0.5 rounded hover:bg-primary/20 disabled:opacity-30"
              >
                {stressLoading ? 'Running...' : 'Run Stress Test'}
              </button>
            </div>
            
            {stressResults.length > 0 ? (
              <div className="flex flex-col gap-2">
                {stressResults.map((s, i) => (
                  <div key={i} className="bg-gray-bg border border-border rounded p-2 text-[11px]">
                    <div className="flex justify-between items-center mb-1">
                      <span className="font-bold text-[#e6edf3] capitalize">{s.scenario.replace('_', ' ')}</span>
                      <span className={s.pnl_pct < 0 ? 'text-red' : 'text-green'}>
                        {(s.pnl_pct * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-[10px] text-[#8b949e] mb-1">{s.description}</div>
                    <div className="w-full bg-border/30 h-1 rounded-full overflow-hidden">
                      <div 
                        className={`h-full ${s.pnl_pct < -0.1 ? 'bg-red' : 'bg-orange'}`} 
                        style={{ width: `${Math.min(Math.abs(s.pnl_pct) * 200, 100)}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[10px] text-[#8b949e]">Check how the current portfolio holds up under crisis scenarios.</p>
            )}
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirm && preview && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center px-4">
          <div className="bg-[#161b22] border border-[#30363d] rounded-2xl p-6 w-full max-w-sm">
            <h3 className="text-base font-bold text-[#e6edf3] mb-4">Confirm Trade</h3>
            <div className="flex flex-col gap-2 text-sm mb-6">
              {[
                ['Action', `${side.toUpperCase()} ${quantity} shares of ${ticker.toUpperCase()}`],
                ['Price', `~$${preview.current_price.toFixed(2)}`],
                ['Estimated Cost', `$${preview.estimated_cost.toLocaleString()}`],
                ['New Weight', `${(preview.new_weight * 100).toFixed(2)}%`],
                ['Cash After', `$${preview.cash_after.toLocaleString()}`],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-[#8b949e]">{k}</span>
                  <span className={`font-medium ${k === 'Cash After' && preview.cash_after < 0 ? 'text-[#f85149]' : 'text-[#e6edf3]'}`}>{v}</span>
                </div>
              ))}
            </div>
            {opinion?.recommendation === 'REJECT' && (
              <div className="bg-[#3d1a1a] border border-[#f85149] rounded p-2 text-xs text-[#f85149] mb-4 flex items-start gap-2">
                <XCircle size={12} className="mt-0.5 shrink-0" />
                AI recommends rejecting this trade. Proceeding overrides the recommendation.
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 border border-border text-[#8b949e] hover:text-[#e6edf3] py-2 rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleExecute}
                className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-colors ${side === 'buy' ? 'bg-[#238636] hover:bg-[#2ea043] text-white' : 'bg-[#da3633] hover:bg-[#f85149] text-white'}`}
              >
                Confirm {side === 'buy' ? 'Buy' : 'Sell'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Operations;
