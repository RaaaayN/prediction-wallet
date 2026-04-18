import React, { useState, useEffect, useRef } from 'react';
import { ApiService } from '../api/service';
import type { OnboardingProfile } from '../types';
import { ChevronRight, ChevronLeft, Rocket, CheckCircle2, History } from 'lucide-react';

interface Props {
  onComplete: () => void;
}

const RISK_COLORS: Record<string, string> = {
  Low: 'bg-[#1a4731] text-[#3fb950]',
  Medium: 'bg-[#3d2e0a] text-[#d29922]',
  High: 'bg-[#3d2200] text-[#f0883e]',
  'Very High': 'bg-[#3d1a1a] text-[#f85149]',
};

interface LogEntry {
  text: string;
  type: 'info' | 'error' | 'warning' | 'cmd';
}

const LOG_COLORS: Record<LogEntry['type'], string> = {
  cmd: 'text-[#8b949e]',
  info: 'text-[#e6edf3]',
  warning: 'text-[#d29922]',
  error: 'text-[#f85149]',
};

const Onboarding: React.FC<Props> = ({ onComplete }) => {
  const [step, setStep] = useState(0);
  const [fundName, setFundName] = useState('');
  const [profiles, setProfiles] = useState<OnboardingProfile[]>([]);
  const [selectedProfile, setSelectedProfile] = useState<OnboardingProfile | null>(null);
  const [capital, setCapital] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [launching, setLaunching] = useState(false);
  const [launched, setLaunched] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ApiService.get<OnboardingProfile[]>('/api/onboarding/profiles').then((data) => {
      setProfiles(data);
      if (data.length > 0) {
        setSelectedProfile(data[0]);
        setCapital(String(data[0].initial_capital));
      }
    });
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = (text: string, type: LogEntry['type'] = 'info') =>
    setLogs((prev) => [...prev, { text, type }]);

  const handleSelectProfile = (p: OnboardingProfile) => {
    setSelectedProfile(p);
    setCapital(String(p.initial_capital));
  };

  const handleResume = async () => {
    if (!selectedProfile) return;
    setLaunching(true);
    try {
      const res = await ApiService.post<{ ok: boolean }>('/api/onboarding/resume', {
        profile: selectedProfile.name
      });
      if (res.ok) {
        onComplete();
      }
    } catch (err: any) {
      addLog(`Error resuming fund: ${err.message}`, 'error');
    } finally {
      setLaunching(false);
    }
  };

  const handleLaunch = () => {
    if (!selectedProfile) return;
    setLaunching(true);
    addLog(`Initializing ${selectedProfile.label}…`, 'cmd');
    ApiService.stream(
      '/api/run/init',
      { 
        strategy: 'threshold', 
        mode: 'simulate', 
        profile: selectedProfile.name,
        initial_capital: parseFloat(capital)
      },
      (msg) => {
        const line = msg.line;
        if (typeof line === 'string') {
          let type: LogEntry['type'] = 'info';
          if (line.includes('ERROR') || line.includes('error')) type = 'error';
          else if (line.includes('WARNING')) type = 'warning';
          addLog(line, type);
        }
      },
      (exitCode) => {
        addLog(`-- exit ${exitCode} --`, exitCode === 0 ? 'info' : 'error');
        setLaunching(false);
        if (exitCode === 0) setLaunched(true);
      },
    );
  };

  const canNext =
    (step === 0) ||
    (step === 1 && selectedProfile !== null) ||
    (step === 2 && parseFloat(capital) > 0);

  return (
    <div className="fixed inset-0 z-50 bg-[#0d1117] flex flex-col items-center justify-center px-4">
      {/* Progress bar */}
      <div className="flex gap-2 mb-10">
        {['Welcome', 'Strategy', 'Capital', 'Launch'].map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border transition-all ${
                i < step
                  ? 'bg-primary border-primary text-white'
                  : i === step
                  ? 'border-primary text-primary bg-primary/10'
                  : 'border-[#30363d] text-[#8b949e]'
              }`}
            >
              {i < step ? <CheckCircle2 size={14} /> : i + 1}
            </div>
            <span
              className={`text-xs hidden sm:block ${
                i === step ? 'text-[#e6edf3]' : 'text-[#8b949e]'
              }`}
            >
              {label}
            </span>
            {i < 3 && <div className="w-6 h-px bg-[#30363d] hidden sm:block" />}
          </div>
        ))}
      </div>

      <div className="w-full max-w-2xl bg-[#161b22] border border-[#30363d] rounded-2xl p-8 min-h-[440px] flex flex-col">
        {/* STEP 0 — Welcome */}
        {step === 0 && (
          <div className="flex flex-col items-center gap-6 flex-1 justify-center text-center">
            <div className="w-20 h-20 rounded-full bg-primary flex items-center justify-center text-3xl font-bold text-white shadow-lg shadow-primary/30">
              PW
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[#e6edf3] mb-1">Welcome to Prediction Wallet</h1>
              <p className="text-[#8b949e] text-sm">Your governed portfolio agent. Let's set up your fund.</p>
            </div>
            <div className="w-full max-w-sm flex flex-col gap-3">
              <input
                value={fundName}
                onChange={(e) => setFundName(e.target.value)}
                placeholder="Fund name (e.g. Apex Capital)"
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-4 py-2.5 text-[#e6edf3] placeholder-[#8b949e] text-sm focus:outline-none focus:border-primary"
              />
              <input
                placeholder="Tagline (optional)"
                className="w-full bg-[#0d1117] border border-[#30363d] rounded-lg px-4 py-2.5 text-[#e6edf3] placeholder-[#8b949e] text-sm focus:outline-none focus:border-primary"
              />
            </div>
          </div>
        )}

        {/* STEP 1 — Strategy */}
        {step === 1 && (
          <div className="flex flex-col gap-4 flex-1">
            <h2 className="text-lg font-semibold text-[#e6edf3]">Choose your strategy</h2>
            <p className="text-[#8b949e] text-xs">Select the investment mandate that best fits your objectives.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 overflow-y-auto max-h-80 pr-1">
              {profiles.map((p) => (
                <button
                  key={p.name}
                  onClick={() => handleSelectProfile(p)}
                  className={`text-left p-4 rounded-lg border transition-all relative ${
                    selectedProfile?.name === p.name
                      ? 'border-primary bg-primary/10'
                      : 'border-[#30363d] bg-[#0d1117] hover:border-[#8b949e]'
                  }`}
                >
                  {p.has_existing_data && (
                    <div className="absolute top-2 right-2 flex items-center gap-1 text-[9px] font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded border border-primary/30 uppercase">
                      <History size={10} /> Existing
                    </div>
                  )}
                  <div className="flex items-start justify-between mb-2 mr-12">
                    <span className="font-semibold text-sm text-[#e6edf3]">{p.label}</span>
                  </div>
                  <div className={`inline-block text-[10px] px-2 py-0.5 rounded-full font-medium mb-2 ${RISK_COLORS[p.risk_level] ?? 'text-[#8b949e]'}`}>
                    {p.risk_level}
                  </div>
                  <p className="text-[11px] text-[#8b949e] mb-2 leading-relaxed">{p.description}</p>
                  <div className="flex flex-wrap gap-1">
                    {p.tickers.slice(0, 5).map((t) => (
                      <span key={t} className="text-[9px] bg-[#21262d] text-[#8b949e] px-1.5 py-0.5 rounded">
                        {t}
                      </span>
                    ))}
                    {p.tickers.length > 5 && (
                      <span className="text-[9px] text-[#8b949e]">+{p.tickers.length - 5}</span>
                    )}
                  </div>
                  <div className="mt-2 text-[10px] text-[#8b949e]">AUM: {p.typical_aum}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* STEP 2 — Capital */}
        {step === 2 && selectedProfile && (
          <div className="flex flex-col gap-6 flex-1 justify-center">
            <div>
              <h2 className="text-lg font-semibold text-[#e6edf3] mb-1">
                {selectedProfile.has_existing_data ? 'Review Fund' : 'Initial Capital'}
              </h2>
              <p className="text-[#8b949e] text-xs">
                {selectedProfile.has_existing_data 
                  ? 'This profile already has data. You can resume it or overwrite it with a fresh start.' 
                  : `Set the starting AUM for ${selectedProfile.label}.`}
              </p>
            </div>

            {!selectedProfile.has_existing_data ? (
              <div className="bg-[#0d1117] border border-[#30363d] rounded-lg p-4 flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <span className="text-[#8b949e] text-lg font-bold">$</span>
                  <input
                    type="number"
                    min="1"
                    value={capital}
                    onChange={(e) => setCapital(e.target.value)}
                    className="flex-1 bg-transparent text-2xl font-bold text-[#e6edf3] focus:outline-none"
                    placeholder="100000"
                  />
                </div>
                <div className="flex gap-2 flex-wrap">
                  {[50000, 100000, 250000, 500000, 1000000].map((v) => (
                    <button
                      key={v}
                      onClick={() => setCapital(String(v))}
                      className="text-xs px-3 py-1 rounded border border-[#30363d] text-[#8b949e] hover:border-primary hover:text-primary transition-colors"
                    >
                      ${(v / 1000).toFixed(0)}K
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-primary/5 border border-primary/20 rounded-xl p-6 flex flex-col items-center gap-4 text-center">
                <History size={40} className="text-primary" />
                <div>
                  <h3 className="text-[#e6edf3] font-semibold">Existing Portfolio Detected</h3>
                  <p className="text-[#8b949e] text-xs mt-1">Previous positions and trade history are available for this profile.</p>
                </div>
                <div className="flex gap-3 w-full">
                  <button 
                    onClick={handleResume}
                    disabled={launching}
                    className="flex-1 bg-primary hover:bg-primary/80 text-white text-xs font-bold py-2.5 rounded-lg flex items-center justify-center gap-2 transition-all"
                  >
                    {launching ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <ChevronRight size={14} />}
                    Resume Existing Fund
                  </button>
                  <button 
                    onClick={() => { /* Stay here but maybe toggle a flag to show fresh start anyway? */ setSelectedProfile({...selectedProfile, has_existing_data: false}) }}
                    className="flex-1 bg-[#21262d] hover:bg-[#30363d] text-[#c9d1d9] text-xs font-bold py-2.5 rounded-lg transition-all"
                  >
                    Overwrite (Fresh Start)
                  </button>
                </div>
              </div>
            )}

            <div className="bg-[#1c2128] border border-[#30363d] rounded-lg p-3 text-xs text-[#8b949e] leading-relaxed">
              <span className="text-[#e6edf3] font-medium">{selectedProfile.label}</span> ·{' '}
              {selectedProfile.strategy_type} · {selectedProfile.tickers.length} positions
            </div>
          </div>
        )}

        {/* STEP 3 — Launch */}
        {step === 3 && selectedProfile && (
          <div className="flex flex-col gap-4 flex-1">
            <h2 className="text-lg font-semibold text-[#e6edf3]">Review &amp; Launch</h2>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {[
                ['Fund', fundName || 'Unnamed Fund'],
                ['Strategy', selectedProfile.label],
                ['Profile', selectedProfile.name],
                ['Initial AUM', `$${parseFloat(capital).toLocaleString()}`],
                ['Risk Level', selectedProfile.risk_level],
                ['Positions', `${selectedProfile.tickers.length} assets`],
              ].map(([k, v]) => (
                <div key={k} className="bg-[#0d1117] border border-[#30363d] rounded p-2">
                  <div className="text-[#8b949e]">{k}</div>
                  <div className="text-[#e6edf3] font-medium">{v}</div>
                </div>
              ))}
            </div>

            {!launching && !launched && (
              <button
                onClick={handleLaunch}
                className="mt-2 w-full bg-primary hover:bg-primary/80 text-white font-semibold py-3 rounded-lg flex items-center justify-center gap-2 transition-colors"
              >
                <Rocket size={16} /> Launch Fresh Fund
              </button>
            )}

            {(launching || logs.length > 0) && (
              <div className="bg-[#0d1117] border border-[#30363d] rounded-lg p-3 font-mono text-xs h-36 overflow-y-auto">
                {logs.map((l, i) => (
                  <div key={i} className={LOG_COLORS[l.type]}>
                    {l.text}
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            )}

            {launched && (
              <div className="flex flex-col items-center gap-3 py-2">
                <CheckCircle2 size={32} className="text-[#3fb950]" />
                <p className="text-[#3fb950] font-medium text-sm">Fund initialized successfully!</p>
                <button
                  onClick={onComplete}
                  className="bg-primary hover:bg-primary/80 text-white font-semibold px-6 py-2 rounded-lg transition-colors"
                >
                  Open Dashboard
                </button>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        {!launched && (
          <div className="flex justify-between mt-6">
            <button
              onClick={() => setStep((s) => Math.max(0, s - 1))}
              disabled={step === 0}
              className="flex items-center gap-1 text-sm text-[#8b949e] hover:text-[#e6edf3] disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={16} /> Back
            </button>
            {step < 3 && (
              <button
                onClick={() => setStep((s) => s + 1)}
                disabled={!canNext}
                className="flex items-center gap-1 text-sm bg-primary hover:bg-primary/80 text-white px-4 py-1.5 rounded-lg disabled:opacity-40 transition-colors"
              >
                Next <ChevronRight size={16} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Onboarding;
