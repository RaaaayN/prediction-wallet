import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import SectionCard from '../components/SectionCard';
import type { Instrument } from '../types';
import { Globe, Shield, Coins, BarChart } from 'lucide-react';

const Instruments: React.FC = () => {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    ApiService.get<Instrument[]>('/api/trading-core/instruments')
      .then(setInstruments)
      .catch((ex) => setErr(ex instanceof Error ? ex.message : 'Failed to load instruments'))
      .finally(() => setLoading(false));
  }, []);

  if (err) return <div className="text-red text-sm p-4">Error: {err}</div>;
  if (loading) return <div className="text-primary text-sm p-4 animate-pulse">Loading Security Master...</div>;

  const getIcon = (assetClass: string) => {
    switch (assetClass.toLowerCase()) {
      case 'equity': return <BarChart size={16} className="text-primary" />;
      case 'crypto': return <Coins size={16} className="text-orange" />;
      case 'bond': return <Shield size={16} className="text-green" />;
      default: return <Globe size={16} className="text-[#8b949e]" />;
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <SectionCard 
        title="Security Master" 
        subtitle="Canonical repository of tradable instruments"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {instruments.map((inst) => (
            <div key={inst.instrument_id} className="bg-gray-bg border border-border/60 rounded-lg p-3 hover:border-primary/50 transition-all group">
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-2">
                  {getIcon(inst.asset_class)}
                  <span className="font-mono font-bold text-[#e6edf3]">{inst.symbol}</span>
                </div>
                <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded ${inst.is_active ? 'bg-green/10 text-green border border-green/20' : 'bg-red/10 text-red border border-red/20'}`}>
                  {inst.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              
              <div className="text-sm font-semibold text-[#c9d1d9] mb-1 truncate">{inst.name}</div>
              
              <div className="flex justify-between items-center text-[11px] text-[#8b949e]">
                <div className="flex gap-3">
                  <span>{inst.asset_class.toUpperCase()}</span>
                  {inst.sector && <span className="border-l border-border/40 pl-3">{inst.sector}</span>}
                </div>
                <span className="font-mono opacity-0 group-hover:opacity-100 transition-opacity">{inst.instrument_id}</span>
              </div>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
};

export default Instruments;
