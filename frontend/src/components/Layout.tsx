import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Terminal, Briefcase, ShieldAlert, BarChart3, History, BookOpen, Activity, Zap, TrendingUp, Layers, Fingerprint, ClipboardList, Repeat2 } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const mainTabs = [
    { name: 'Overview', path: '/', icon: <LayoutDashboard size={18} /> },
    { name: 'Command', path: '/control', icon: <Terminal size={18} /> },
    { name: 'Book', path: '/workspace', icon: <BookOpen size={18} /> },
    { name: 'Risk', path: '/riskhub', icon: <ShieldAlert size={18} /> },
    { name: 'Analytics', path: '/analytics', icon: <BarChart3 size={18} /> },
    { name: 'Audit', path: '/audit', icon: <ClipboardList size={18} /> },
    { name: 'Operations', path: '/operations', icon: <Repeat2 size={18} /> },
  ];

  const subTabs = [
    { name: 'Portfolio', path: '/portfolio', icon: <Briefcase size={14} /> },
    { name: 'Book Summary', path: '/book', icon: <Layers size={14} /> },
    { name: 'Idea Book', path: '/ideas', icon: <Zap size={14} /> },
    { name: 'Blotter', path: '/blotter', icon: <Activity size={14} /> },
    { name: 'Risk Detail', path: '/risk', icon: <ShieldAlert size={14} /> },
    { name: 'Regime', path: '/regime', icon: <TrendingUp size={14} /> },
    { name: 'Stress Test', path: '/stress', icon: <Zap size={14} /> },
    { name: 'Performance', path: '/perf', icon: <Activity size={14} /> },
    { name: 'History', path: '/history', icon: <History size={14} /> },
    { name: 'Monte Carlo', path: '/montecarlo', icon: <TrendingUp size={14} /> },
    { name: 'Backtest', path: '/backtest', icon: <TrendingUp size={14} /> },
    { name: 'Correlation', path: '/correlation', icon: <TrendingUp size={14} /> },
    { name: 'Agent Trace', path: '/traces', icon: <Fingerprint size={14} /> },
    { name: 'Cycles', path: '/runs', icon: <ClipboardList size={14} /> },
  ];

  return (
    <div className="min-h-screen bg-gray-bg text-[#e6edf3]">
      {/* HEADER */}
      <header className="border-b border-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-sm font-bold text-white">PW</div>
          <span className="font-semibold text-base">Prediction Wallet</span>
          <span className="text-[#8b949e] text-sm">Governed Portfolio Agent</span>
        </div>
      </header>

      {/* MAIN TABS */}
      <nav className="border-b border-border px-6 flex gap-6 overflow-x-auto bg-gray-bg">
        {mainTabs.map((tab) => (
          <NavLink
            key={tab.path}
            to={tab.path}
            className={({ isActive }) =>
              `py-3 text-sm flex items-center gap-2 border-b-2 transition-colors ${
                isActive ? 'border-primary text-primary' : 'border-transparent text-[#8b949e] hover:text-[#c9d1d9]'
              }`
            }
          >
            {tab.icon}
            {tab.name}
          </NavLink>
        ))}
      </nav>

      <main className="p-6 max-w-7xl mx-auto">
        {/* SUB NAV / CHIPS */}
        <div className="bg-[#11161d] border border-[#21262d] rounded-xl p-4 mb-6">
          <div className="text-[#8b949e] text-[11px] font-semibold tracking-wider uppercase mb-3">Detailed Views</div>
          <div className="flex flex-wrap gap-2">
            {subTabs.map((tab) => (
              <NavLink
                key={tab.path}
                to={tab.path}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-full text-xs flex items-center gap-1.5 border transition-all ${
                    isActive
                      ? 'bg-primary/10 border-primary text-primary'
                      : 'bg-card-bg border-border text-[#c9d1d9] hover:border-primary hover:text-primary'
                  }`
                }
              >
                {tab.icon}
                {tab.name}
              </NavLink>
            ))}
          </div>
        </div>

        {children}
      </main>
    </div>
  );
};

export default Layout;
