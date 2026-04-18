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
          <Route path="reports" element={<Reports />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
