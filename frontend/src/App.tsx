import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import { Dashboard } from "@/pages/Dashboard";
import { Portfolio } from "@/pages/Portfolio";
import { BacktestStudio } from "@/pages/BacktestStudio";
import { StrategyLab } from "@/pages/StrategyLab";
import { RiskCenter } from "@/pages/RiskCenter";
import { DataExplorer } from "@/pages/DataExplorer";
import { Experiments } from "@/pages/Experiments";
import { AgentsPanel } from "@/pages/AgentsPanel";
import { Reports } from "@/pages/Reports";
import { Settings } from "@/pages/Settings";
import { Events } from "@/pages/Events";
import { TradingCore } from "@/pages/TradingCore";
import { MiddleOffice } from "@/pages/MiddleOffice";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="backtest" element={<BacktestStudio />} />
          <Route path="strategy" element={<StrategyLab />} />
          <Route path="risk" element={<RiskCenter />} />
          <Route path="data" element={<DataExplorer />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="agents" element={<AgentsPanel />} />
          <Route path="events" element={<Events />} />
          <Route path="trading-core" element={<TradingCore />} />
          <Route path="middle-office" element={<MiddleOffice />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
