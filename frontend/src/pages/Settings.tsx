import { useState, useEffect } from "react";
import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { 
  Settings as SettingsIcon, 
  Save, 
  RefreshCw, 
  Trash2, 
  ShieldAlert,
  Terminal,
  Key,
  Cpu,
  Database,
  ShieldCheck,
  Zap
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

export function Settings() {
  const { profile, setProfile } = useStore();
  const [initialCapital, setInitialCapital] = useState(100000);
  const [logs, setLogs] = useState<string[]>([]);
  const queryClient = useQueryClient();

  // 1. Fetch System Settings
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      const { data } = await apiClient.get('/settings');
      return data;
    }
  });

  // 2. Fetch Profile Details for Onboarding/Switching
  const { data: profiles, isLoading: profilesLoading } = useQuery({
    queryKey: ['onboarding-profiles'],
    queryFn: async () => {
      const { data } = await apiClient.get('/onboarding/profiles');
      return data;
    }
  });

  const [formData, setFormData] = useState<any>({});

  useEffect(() => {
    if (settings) {
      setFormData({
        ai_provider: settings.ai_provider,
        gemini_model: settings.gemini_model,
        execution_mode: settings.execution_mode,
        agent_backend: settings.agent_backend,
        trading_core_enabled: settings.trading_core_enabled,
      });
    }
  }, [settings]);

  // Mutation: Update Global Settings
  const updateSettings = useMutation({
    mutationFn: async (newData: any) => {
      await apiClient.post("/settings", newData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      alert("System configuration updated successfully.");
    }
  });

  // Mutation: Initialize / Bootstrap Fund
  const initializeFund = useMutation({
    mutationFn: async () => {
      setLogs(["[INIT] Starting fund initialization..."]);
      const response = await fetch(`/api/run/init`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-KEY': localStorage.getItem('prediction_wallet_api_key') || ''
        },
        body: JSON.stringify({ profile, initial_capital: initialCapital })
      });

      if (!response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        // Clean up SSE/Log chunks
        setLogs(prev => [...prev, chunk.replace(/data: /g, '')]);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
    }
  });

  // Mutation: Switch Profile (Persisted)
  const switchProfile = useMutation({
    mutationFn: async (targetProfile: string) => {
      await apiClient.post("/onboarding/resume", { profile: targetProfile });
      setProfile(targetProfile);
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
      alert(`Switched active profile to ${profile.toUpperCase()}`);
    }
  });

  const handleFullReset = async () => {
    if (!confirm(`CRITICAL: This will wipe ALL positions, history, and audit traces for ${profile.toUpperCase()}. Continue?`)) return;
    try {
      setLogs([`[RESET] Wiping data for ${profile}...`]);
      await apiClient.post("/run/reset", { profile }); // This endpoint should handle reset logic
      setLogs(prev => [...prev, "✓ Data wipe complete."]);
      queryClient.invalidateQueries();
    } catch (e) {
      setLogs(prev => [...prev, "❌ Reset failed. Ensure endpoint /api/run/reset exists."]);
    }
  };

  if (settingsLoading || profilesLoading) return <div className="p-8 animate-pulse text-muted-foreground">Synchronizing with system configuration...</div>;

  return (
    <div className="space-y-6 max-w-6xl pb-20">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">System Settings</h2>
        <p className="text-muted-foreground mt-1">Institutional configuration, AI mandates, and fund lifecycle management.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Profile / Mandate Selection */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><SettingsIcon className="h-4 w-4" /> Fund Mandate</CardTitle>
            <CardDescription>Select the active investment profile. Each profile has its own target allocation and DB.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1">
            <div className="space-y-3">
              {profiles?.map((p: any) => (
                <div 
                  key={p.name}
                  onClick={() => switchProfile.mutate(p.name)}
                  className={`relative p-4 border rounded-lg cursor-pointer transition-all group ${
                    profile === p.name 
                      ? "border-primary bg-primary/5 ring-1 ring-primary shadow-sm" 
                      : "border-border hover:bg-secondary/50 hover:border-primary/50"
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <div className="font-bold flex items-center gap-2">
                        {p.label}
                        {p.has_existing_data && <Database className="h-3 w-3 text-emerald-500" />}
                      </div>
                      <div className="text-[10px] text-muted-foreground uppercase tracking-widest mt-1">
                        {p.risk_level} Risk • {p.strategy_type}
                      </div>
                    </div>
                    {profile === p.name && (
                       <div className="h-5 w-5 rounded-full bg-emerald-500/20 flex items-center justify-center">
                          <ShieldCheck className="h-3 w-3 text-emerald-500" />
                       </div>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-2 line-clamp-1 group-hover:line-clamp-none transition-all">
                    {p.description}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          {/* AI & Infrastructure Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Cpu className="h-4 w-4" /> Engine & AI Mandate</CardTitle>
              <CardDescription>Global backend configuration (stored in .env)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">AI Provider</label>
                  <select 
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus:ring-1 focus:ring-primary"
                    value={formData.ai_provider}
                    onChange={e => setFormData({...formData, ai_provider: e.target.value})}
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="anthropic">Anthropic Claude</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Execution Mode</label>
                  <select 
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm focus:ring-1 focus:ring-primary"
                    value={formData.execution_mode}
                    onChange={e => setFormData({...formData, execution_mode: e.target.value})}
                  >
                    <option value="simulate">Simulation</option>
                    <option value="paper">Paper Trading</option>
                    <option value="live">Live (Restricted)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase text-muted-foreground">Agent Framework</label>
                  <select 
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={formData.agent_backend}
                    onChange={e => setFormData({...formData, agent_backend: e.target.value})}
                  >
                    <option value="pydantic-ai">Pydantic AI (Standard)</option>
                  </select>
                </div>
                <div className="space-y-2">
                   <label className="text-xs font-bold uppercase text-muted-foreground">Trading Core</label>
                   <div className="flex items-center gap-2 h-9 border border-input rounded-md px-3 bg-secondary/20">
                      <input 
                        type="checkbox" 
                        id="tc_check"
                        className="rounded border-input text-primary focus:ring-primary"
                        checked={formData.trading_core_enabled}
                        onChange={e => setFormData({...formData, trading_core_enabled: e.target.checked})}
                      />
                      <label htmlFor="tc_check" className="text-xs">Postgres Ledger</label>
                   </div>
                </div>
              </div>

              <div className="flex items-center gap-2 p-3 bg-secondary/30 rounded-md text-[10px] text-muted-foreground">
                <Key className="h-3 w-3" />
                <span>
                  Admin Auth: {settings?.has_gemini_key ? "Gemini OK" : "Gemini Missing"} | 
                  {settings?.has_anthropic_key ? " Claude OK" : " Claude Missing"}
                </span>
              </div>

              <Button 
                className="w-full" 
                onClick={() => updateSettings.mutate(formData)} 
                disabled={updateSettings.isPending}
              >
                {updateSettings.isPending ? <RefreshCw className="h-3 w-3 animate-spin mr-2" /> : <Save className="h-3 w-3 mr-2" />}
                Apply Global Changes
              </Button>
            </CardContent>
          </Card>

          {/* Fund Lifecycle Operations */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><Zap className="h-4 w-4" /> Fund Lifecycle</CardTitle>
              <CardDescription>Manage the initialization and persistence of the active fund.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">Target Capital ($)</label>
                <div className="flex gap-2">
                  <input 
                    type="number" 
                    value={initialCapital}
                    onChange={(e) => setInitialCapital(Number(e.target.value))}
                    className="flex-1 h-10 rounded-md border border-input bg-background px-3 text-sm font-mono"
                  />
                  <Button 
                    variant="outline" 
                    className="h-10 px-6 font-bold"
                    onClick={() => initializeFund.mutate()} 
                    disabled={initializeFund.isPending}
                  >
                    {initializeFund.isPending ? <RefreshCw className="h-4 w-4 animate-spin" /> : "BOOTSTRAP"}
                  </Button>
                </div>
              </div>

              {logs.length > 0 && (
                <div className="p-3 bg-black rounded border border-border font-mono text-[9px] text-emerald-400 overflow-auto max-h-40 shadow-inner">
                  <div className="flex items-center gap-2 mb-2 text-muted-foreground opacity-50 uppercase tracking-tighter">
                    <Terminal className="h-3 w-3" /> Stream Output
                  </div>
                  {logs.map((log, i) => (
                    <div key={i} className="leading-relaxed">{log}</div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Danger Zone */}
        <Card className="md:col-span-2 border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2 text-sm font-bold uppercase">
              <ShieldAlert className="h-4 w-4" /> Administrative Danger Zone
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col md:flex-row justify-between items-center gap-4 border-t border-destructive/10 pt-4">
            <div className="text-xs text-muted-foreground">
              <p className="font-bold text-destructive">Wipe all state for "{profile.toUpperCase()}"</p>
              <p>Irreversibly deletes positions, cash ledger, backtest history, and all decision traces in the database.</p>
            </div>
            <Button variant="destructive" size="sm" onClick={handleFullReset} className="font-bold px-8">
              <Trash2 className="h-4 w-4 mr-2" /> DATA WIPE
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
