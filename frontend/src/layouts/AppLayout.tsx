import { Outlet, NavLink } from "react-router-dom";
import { 
  LayoutDashboard, 
  PieChart, 
  FlaskConical, 
  Cpu, 
  ShieldAlert, 
  Database, 
  TestTube, 
  Bot, 
  FileText,
  Settings as SettingsIcon,
  Activity,
  Layers,
  Briefcase
} from "lucide-react";
import { cn } from "@/utils/cn";
import { useStore } from "@/store/useStore";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/api/client";

const navItems = [
  { path: "/", label: "Dashboard", icon: LayoutDashboard },
  { path: "/portfolio", label: "Portfolio", icon: PieChart },
  { path: "/backtest", label: "Backtesting Studio", icon: FlaskConical },
  { path: "/strategy", label: "Strategy Lab", icon: Cpu },
  { path: "/risk", label: "Risk Center", icon: ShieldAlert },
  { path: "/data", label: "Data Explorer", icon: Database },
  { path: "/experiments", label: "Experiments", icon: TestTube },
  { path: "/agents", label: "Agents Panel", icon: Bot },
  { path: "/trading-core", label: "Trading Core", icon: Layers },
  { path: "/middle-office", label: "Middle Office", icon: Briefcase },
  { path: "/events", label: "Event Browser", icon: Activity },
  { path: "/reports", label: "Reports", icon: FileText },
  { path: "/settings", label: "Settings", icon: SettingsIcon },
];

export function AppLayout() {
  const { profile, setProfile } = useStore();

  const { data: profiles } = useQuery({
    queryKey: ['onboarding-profiles'],
    queryFn: async () => {
      const { data } = await apiClient.get('/onboarding/profiles');
      return data;
    }
  });

  const handleProfileChange = async (newProfile: string) => {
    await apiClient.post("/onboarding/resume", { profile: newProfile });
    setProfile(newProfile);
    window.location.reload(); // Refresh to ensure all queries reset
  };

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-card flex flex-col">
        <div className="h-16 flex items-center px-6 border-b border-border">
          <h1 className="text-xl font-bold tracking-tight">Prediction Wallet</h1>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors",
                  isActive 
                    ? "bg-accent text-accent-foreground" 
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b border-border flex items-center justify-between px-8 bg-card/50 backdrop-blur-sm z-10 sticky top-0">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <span className="text-sm font-medium text-muted-foreground">System Online</span>
            </div>

            <div className="h-4 w-[1px] bg-border" />

            <div className="flex items-center gap-2">
               <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Profile:</span>
               <select 
                 className="bg-transparent text-sm font-bold focus:outline-none cursor-pointer hover:text-primary transition-colors"
                 value={profile}
                 onChange={(e) => handleProfileChange(e.target.value)}
               >
                 {profiles?.map((p: any) => (
                   <option key={p.name} value={p.name} className="bg-background text-foreground">{p.label}</option>
                 ))}
               </select>
            </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
