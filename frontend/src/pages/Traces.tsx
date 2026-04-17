import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { DecisionTrace } from '../types';
import { ChevronDown, ChevronUp, Fingerprint, Clock, Activity, Brain, ShieldCheck, Zap, ClipboardList } from 'lucide-react';

const Traces: React.FC = () => {
  const [traces, setTraces] = useState<DecisionTrace[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const data = await ApiService.get<DecisionTrace[]>('/api/traces?limit=100');
        setTraces(data);
      } catch (err) {
        console.error('Error fetching traces:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  const filteredTraces = traces.filter(t => 
    t.cycle_id.toLowerCase().includes(filter.toLowerCase()) ||
    t.stage.toLowerCase().includes(filter.toLowerCase())
  );

  const getStageIcon = (stage: string) => {
    switch (stage) {
      case 'observe': return <Activity size={14} className="text-primary" />;
      case 'decide': return <Brain size={14} className="text-purple" />;
      case 'validate': return <ShieldCheck size={14} className="text-yellow" />;
      case 'execute': return <Zap size={14} className="text-green" />;
      case 'audit': return <ClipboardList size={14} className="text-red" />;
      default: return <Fingerprint size={14} />;
    }
  };

  const getStageBadgeClass = (stage: string) => {
    switch (stage) {
      case 'observe': return 'bg-[#1b2a3d] text-primary';
      case 'decide': return 'bg-[#2d1f6e] text-purple';
      case 'validate': return 'bg-[#3d2d0a] text-yellow';
      case 'execute': return 'bg-[#1a4731] text-green';
      case 'audit': return 'bg-[#3d1a1a] text-red';
      default: return 'bg-[#21262d] text-[#8b949e]';
    }
  };

  if (loading) return <div className="text-gray-500">Loading Traces...</div>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4 mb-2">
        <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide">Decision Traces</h2>
        <input
          type="text"
          placeholder="Filter by cycle ID or stage..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-card-bg border border-border rounded px-3 py-1.5 text-sm flex-1 max-w-sm focus:border-primary outline-none"
        />
      </div>

      <div className="flex flex-col gap-2">
        {filteredTraces.map((trace) => {
          const isExpanded = expandedId === trace.id;
          let payload: Record<string, unknown> = {};
          try {
            payload = JSON.parse(trace.payload_json) as Record<string, unknown>;
          } catch {
            payload = {};
          }

          return (
            <div key={trace.id} className="bg-card-bg border border-border rounded-lg overflow-hidden">
              <div
                onClick={() => toggleExpand(trace.id)}
                className="p-3 flex items-center gap-4 cursor-pointer hover:bg-[#1c2128] transition-colors"
              >
                <div className={`px-2 py-0.5 rounded flex items-center gap-1.5 text-[10px] font-bold uppercase ${getStageBadgeClass(trace.stage)}`}>
                  {getStageIcon(trace.stage)}
                  {trace.stage}
                </div>
                <span className="font-mono text-xs text-primary">{trace.cycle_id}</span>
                <span className="text-xs text-[#8b949e] flex items-center gap-1">
                  <Clock size={12} />
                  {trace.created_at.slice(0, 19).replace('T', ' ')}
                </span>
                <div className="ml-auto text-[#8b949e]">
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </div>

              {isExpanded && (
                <div className="p-4 border-t border-border bg-terminal-bg">
                   <div className="text-[11px] text-[#8b949e] uppercase font-semibold mb-2">Payload JSON</div>
                   <pre className="text-xs font-mono text-[#c9d1d9] overflow-x-auto whitespace-pre-wrap max-h-[400px]">
                     {JSON.stringify(payload, null, 2)}
                   </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Traces;
