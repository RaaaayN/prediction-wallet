import React, { useEffect, useState } from 'react';
import { ApiService } from '../api/service';
import type { AppSettings } from '../types';
import { Save, RefreshCcw, ShieldCheck, Cpu, Activity, Zap, Key } from 'lucide-react';

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  // Form states
  const [formData, setFormData] = useState<Partial<AppSettings & { gemini_api_key?: string, anthropic_api_key?: string }>>({});

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await ApiService.get<AppSettings>('/api/settings');
      setSettings(data);
      setFormData(data);
    } catch (err) {
      console.error('Error fetching settings:', err);
      setMessage({ text: 'Failed to load settings.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const result = await ApiService.post<{ ok: boolean; message: string }>('/api/settings', formData);
      if (result.ok) {
        setMessage({ text: result.message, type: 'success' });
        // Refresh to get updated state (like has_gemini_key)
        await fetchSettings();
      }
    } catch (err: any) {
      setMessage({ text: err.message || 'Error updating settings.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    let val: any = value;
    
    if (type === 'number') val = parseFloat(value);
    if (type === 'checkbox') val = (e.target as HTMLInputElement).checked;

    setFormData(prev => ({ ...prev, [name]: val }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCcw className="animate-spin text-primary" size={32} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Settings</h1>
          <p className="text-[#8b949e]">Configure global governance, AI engines, and risk parameters.</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg transition-colors disabled:opacity-50"
        >
          {saving ? <RefreshCcw size={18} className="animate-spin" /> : <Save size={18} />}
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {message && (
        <div className={`p-4 rounded-lg border ${message.type === 'success' ? 'bg-green-500/10 border-green-500/50 text-green-500' : 'bg-red-500/10 border-red-500/50 text-red-500'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* AI SECTION */}
        <div className="bg-card-bg border border-border rounded-xl p-6 space-y-6">
          <div className="flex items-center gap-3 text-primary">
            <Cpu size={20} />
            <h2 className="font-semibold text-white uppercase tracking-wider text-sm">AI Engine</h2>
          </div>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Active Provider</label>
              <select
                name="ai_provider"
                value={formData.ai_provider}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              >
                <option value="gemini">Google Gemini</option>
                <option value="anthropic">Anthropic Claude</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Gemini Model</label>
              <input
                name="gemini_model"
                type="text"
                value={formData.gemini_model}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Claude Model</label>
              <input
                name="claude_model"
                type="text"
                value={formData.claude_model}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
          </div>
        </div>

        {/* API KEYS SECTION */}
        <div className="bg-card-bg border border-border rounded-xl p-6 space-y-6">
          <div className="flex items-center gap-3 text-primary">
            <Key size={20} />
            <h2 className="font-semibold text-white uppercase tracking-wider text-sm">Credentials</h2>
          </div>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <label className="text-xs font-medium text-[#8b949e] uppercase">Gemini API Key</label>
                {settings?.has_gemini_key && <span className="text-[10px] text-green-500 flex items-center gap-1"><ShieldCheck size={10} /> Configured</span>}
              </div>
              <input
                name="gemini_api_key"
                type="password"
                placeholder={settings?.has_gemini_key ? "••••••••••••••••" : "Enter API key"}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <label className="text-xs font-medium text-[#8b949e] uppercase">Anthropic API Key</label>
                {settings?.has_anthropic_key && <span className="text-[10px] text-green-500 flex items-center gap-1"><ShieldCheck size={10} /> Configured</span>}
              </div>
              <input
                name="anthropic_api_key"
                type="password"
                placeholder={settings?.has_anthropic_key ? "••••••••••••••••" : "Enter API key"}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
          </div>
        </div>

        {/* EXECUTION SECTION */}
        <div className="bg-card-bg border border-border rounded-xl p-6 space-y-6">
          <div className="flex items-center gap-3 text-primary">
            <Activity size={20} />
            <h2 className="font-semibold text-white uppercase tracking-wider text-sm">Execution Policy</h2>
          </div>
          
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Mode</label>
              <select
                name="execution_mode"
                value={formData.execution_mode}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              >
                <option value="simulate">Simulate (Paper)</option>
                <option value="paper">Paper (Dry Run)</option>
                <option value="live">Live (Restricted)</option>
              </select>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-bg border border-border rounded-lg">
              <div>
                <p className="text-sm font-medium">Trading Core</p>
                <p className="text-[10px] text-[#8b949e]">OMS & Ledger V1</p>
              </div>
              <input
                name="trading_core_enabled"
                type="checkbox"
                checked={formData.trading_core_enabled}
                onChange={handleChange}
                className="w-5 h-5 accent-primary"
              />
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Active Profile</label>
              <select
                name="portfolio_profile"
                value={formData.portfolio_profile}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              >
                <option value="balanced">balanced</option>
                <option value="conservative">conservative</option>
                <option value="growth">growth</option>
                <option value="crypto_heavy">crypto_heavy</option>
                <option value="long_short_equity">long_short_equity</option>
              </select>
            </div>
          </div>
        </div>

        {/* RISK GOVERNANCE SECTION */}
        <div className="bg-card-bg border border-border rounded-xl p-6 space-y-6">
          <div className="flex items-center gap-3 text-primary">
            <ShieldCheck size={20} />
            <h2 className="font-semibold text-white uppercase tracking-wider text-sm">Risk Governance</h2>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Max Trades / Cycle</label>
              <input
                name="max_trades_per_cycle"
                type="number"
                value={formData.max_trades_per_cycle}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Max Notional %</label>
              <input
                name="max_order_fraction_of_portfolio"
                type="number"
                step="0.01"
                value={formData.max_order_fraction_of_portfolio}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Drift Threshold</label>
              <input
                name="drift_threshold"
                type="number"
                step="0.01"
                value={formData.drift_threshold}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Kill Switch DD %</label>
              <input
                name="kill_switch_drawdown"
                type="number"
                step="0.01"
                value={formData.kill_switch_drawdown}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
          </div>
        </div>

        {/* MARKET SECTION */}
        <div className="bg-card-bg border border-border rounded-xl p-6 space-y-6 col-span-1 md:col-span-2">
          <div className="flex items-center gap-3 text-primary">
            <Zap size={20} />
            <h2 className="font-semibold text-white uppercase tracking-wider text-sm">Market & Data</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Benchmark Ticker</label>
              <input
                name="benchmark_ticker"
                type="text"
                value={formData.benchmark_ticker}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Market Data TTL (s)</label>
              <input
                name="market_data_ttl_seconds"
                type="number"
                value={formData.market_data_ttl_seconds}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-medium text-[#8b949e] uppercase">Risk-Free Rate</label>
              <input
                name="risk_free_rate"
                type="number"
                step="0.001"
                value={formData.risk_free_rate}
                onChange={handleChange}
                className="w-full bg-gray-bg border border-border rounded-lg p-2.5 text-sm focus:border-primary outline-none"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
