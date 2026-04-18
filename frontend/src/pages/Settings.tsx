import { useState } from "react";
import { useStore } from "@/store/useStore";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings as SettingsIcon, Save, RefreshCw, Trash2, AlertCircle } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

const PROFILES = [
  { id: "balanced", label: "Balanced Fund", risk: "Medium" },
  { id: "conservative", label: "Conservative Income", risk: "Low" },
  { id: "growth", label: "Growth Equity", risk: "High" },
  { id: "crypto_heavy", label: "Digital Asset Blend", risk: "Very High" },
  { id: "long_short_equity", label: "Long/Short Equity", risk: "Institutional" },
];

export function Settings() {
  const { profile, setProfile } = useStore();
  const [capital, setCapital] = useState(100000);
  const queryClient = useQueryClient();

  const initializeFund = useMutation({
    mutationFn: async () => {
       await apiClient.post("/run/init", { profile, initial_capital: capital });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
      alert("Fund initialized successfully.");
    }
  });

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">System Settings</h2>
        <p className="text-muted-foreground mt-1">Manage fund configuration, profiles, and environment variables.</p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><SettingsIcon className="h-4 w-4" /> Active Profile</CardTitle>
            <CardDescription>Switch between fund mandates and risk profiles</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {PROFILES.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setProfile(p.id)}
                  className={`flex flex-col items-start p-4 border rounded-lg text-left transition-all ${
                    profile === p.id 
                      ? "border-primary bg-primary/5 ring-1 ring-primary" 
                      : "border-border hover:bg-secondary/50"
                  }`}
                >
                  <span className="font-bold">{p.label}</span>
                  <span className="text-xs text-muted-foreground mt-1 uppercase tracking-wider">{p.risk} Risk</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Fund Lifecycle</CardTitle>
            <CardDescription>Bootstrap or reset the current portfolio</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col space-y-2">
              <label className="text-sm font-medium">Initial Capital ($)</label>
              <div className="flex gap-4">
                <input 
                  type="number" 
                  value={capital}
                  onChange={(e) => setCapital(Number(e.target.value))}
                  className="flex h-9 w-64 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                />
                <Button variant="outline" onClick={() => initializeFund.mutate()} disabled={initializeFund.isPending}>
                  {initializeFund.isPending ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Initialize {profile.toUpperCase()}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground italic">Warning: Initializing will seed the portfolio with target weights at current market prices.</p>
            </div>

            <div className="pt-6 border-t border-border">
              <div className="flex items-start gap-4 p-4 border border-destructive/20 bg-destructive/5 rounded-lg text-destructive">
                <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <h4 className="font-bold">Danger Zone</h4>
                  <p className="text-sm opacity-90">Resetting the system will wipe all history, traces, and positions for the current profile.</p>
                  <Button variant="destructive" size="sm" className="mt-2">
                    <Trash2 className="h-4 w-4 mr-2" /> Full Data Wipe
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
