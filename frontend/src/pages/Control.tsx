import React, { useState, useRef, useEffect } from 'react';
import { ApiService } from '../api/service';
import { Play, RotateCcw, FileText } from 'lucide-react';

interface LogEntry {
  text: string;
  type: 'info' | 'error' | 'warning' | 'cmd';
}

const Control: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [running, setRunning] = useState(false);
  const [strategy, setStrategy] = useState('threshold');
  const [mode, setMode] = useState('simulate');
  const [profile, setProfile] = useState('');
  const logEndRef = useRef<HTMLDivElement>(null);

  const addLog = (text: string, type: LogEntry['type'] = 'info') => {
    setLogs(prev => [...prev, { text, type }]);
  };

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const runStep = (step: string) => {
    setRunning(true);
    addLog(`python main.py ${step}`, 'cmd');

    ApiService.stream(
      `/api/run/${step}`,
      { strategy, mode, profile: profile || null },
      (msg) => {
        if (msg.line) {
          let type: LogEntry['type'] = 'info';
          if (msg.line.includes('ERROR') || msg.line.includes('error')) type = 'error';
          else if (msg.line.includes('WARNING')) type = 'warning';
          addLog(msg.line, type);
        }
      },
      (exitCode) => {
        addLog(`-- exit ${exitCode} --`, exitCode === 0 ? 'info' : 'error');
        setRunning(false);
      }
    );
  };

  const clearLogs = () => setLogs([]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* COMMAND PANEL */}
      <div className="bg-card-bg border border-border rounded-lg p-4 flex flex-col gap-4">
        <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Run Agent</h2>

        <div className="grid grid-cols-2 gap-4 text-xs">
          <div className="flex flex-col gap-1 col-span-2">
            <label className="text-[#8b949e]">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="bg-gray-bg border border-border rounded p-2 text-[#e6edf3]"
            >
              <option value="threshold">Threshold</option>
              <option value="calendar">Calendar</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[#8b949e]">Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="bg-gray-bg border border-border rounded p-2 text-[#e6edf3]"
            >
              <option value="simulate">Simulate</option>
              <option value="paper">Paper</option>
            </select>
          </div>
          <div className="flex flex-col gap-1 col-span-2">
            <label className="text-[#8b949e]">Profile</label>
            <select
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              className="bg-gray-bg border border-border rounded p-2 text-[#e6edf3]"
            >
              <option value="">default</option>
              <option value="balanced">balanced</option>
              <option value="conservative">conservative</option>
              <option value="growth">growth</option>
              <option value="crypto_heavy">crypto_heavy</option>
              <option value="long_short_equity">long_short_equity</option>
            </select>
          </div>
        </div>

        <div className="flex flex-col gap-2 mt-2">
          <button
            disabled={running}
            onClick={() => runStep('run-cycle')}
            className="flex items-center justify-center gap-2 bg-primary hover:opacity-90 disabled:opacity-50 text-white font-semibold py-2 rounded transition-all"
          >
            <Play size={16} fill="currentColor" /> Run Full Cycle
          </button>
          
          <div className="grid grid-cols-2 gap-2">
            <button disabled={running} onClick={() => runStep('observe')} className="bg-[#21262d] border border-border hover:bg-[#30363d] disabled:opacity-50 py-1.5 rounded text-sm">Observe</button>
            <button disabled={running} onClick={() => runStep('decide')} className="bg-[#21262d] border border-border hover:bg-[#30363d] disabled:opacity-50 py-1.5 rounded text-sm">Decide</button>
            <button disabled={running} onClick={() => runStep('execute')} className="bg-[#21262d] border border-border hover:bg-[#30363d] disabled:opacity-50 py-1.5 rounded text-sm">Execute</button>
            <button disabled={running} onClick={() => runStep('audit')} className="bg-[#21262d] border border-border hover:bg-[#30363d] disabled:opacity-50 py-1.5 rounded text-sm">Audit</button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button disabled={running} onClick={() => runStep('report')} className="bg-[#1a4731] border border-green text-green hover:opacity-80 disabled:opacity-50 py-1.5 rounded text-sm flex items-center justify-center gap-1.5">
              <FileText size={14} /> PDF Report
            </button>
            <button disabled={running} onClick={() => runStep('init')} className="bg-[#3d1a1a] border border-red text-red hover:opacity-80 disabled:opacity-50 py-1.5 rounded text-sm flex items-center justify-center gap-1.5">
              <RotateCcw size={14} /> Init Portfolio
            </button>
          </div>
        </div>
      </div>

      {/* TERMINAL */}
      <div className="lg:col-span-2 bg-card-bg border border-border rounded-lg p-4 flex flex-col gap-2 h-[400px]">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Terminal Output</h2>
          <button onClick={clearLogs} className="text-xs text-[#8b949e] hover:text-[#c9d1d9]">Clear</button>
        </div>
        <div className="bg-terminal-bg font-mono text-xs p-3 rounded flex-1 overflow-y-auto">
          {logs.map((log, i) => (
            <div
              key={i}
              className={`mb-1 break-all ${
                log.type === 'cmd' ? 'text-primary' :
                log.type === 'error' ? 'text-red' :
                log.type === 'warning' ? 'text-yellow' : 'text-[#3fb950]'
              }`}
            >
              {log.type === 'cmd' && <span className="mr-2">❯</span>}
              {log.text}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
};

export default Control;
