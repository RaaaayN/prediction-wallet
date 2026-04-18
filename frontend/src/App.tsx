import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Control from './pages/Control';
import Portfolio from './pages/Portfolio';
import Traces from './pages/Traces';
import NotFound from './pages/NotFound';
import RiskHub from './pages/RiskHub';
import Analytics from './pages/Analytics';
import Audit from './pages/Audit';
import Book from './pages/Book';
import Ideas from './pages/Ideas';
import MiddleOffice from './pages/MiddleOffice';
import Instruments from './pages/Instruments';
import RiskDetail from './pages/RiskDetail';
import Regime from './pages/Regime';
import Stress from './pages/Stress';
import Perf from './pages/Perf';
import History from './pages/History';
import MonteCarlo from './pages/MonteCarlo';
import Backtest from './pages/Backtest';
import Correlation from './pages/Correlation';
import Runs from './pages/Runs';
import Operations from './pages/Operations';
import Onboarding from './pages/Onboarding';
import { ApiService } from './api/service';
import type { OnboardingStatus } from './types';

const MainApp: React.FC = () => (
  <Router>
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/control" element={<Control />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/traces" element={<Traces />} />
        <Route path="/workspace" element={<Instruments />} />
        <Route path="/riskhub" element={<RiskHub />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/book" element={<Book />} />
        <Route path="/ideas" element={<Ideas />} />
        <Route path="/blotter" element={<MiddleOffice />} />
        <Route path="/risk" element={<RiskDetail />} />
        <Route path="/regime" element={<Regime />} />
        <Route path="/stress" element={<Stress />} />
        <Route path="/perf" element={<Perf />} />
        <Route path="/history" element={<History />} />
        <Route path="/montecarlo" element={<MonteCarlo />} />
        <Route path="/backtest" element={<Backtest />} />
        <Route path="/correlation" element={<Correlation />} />
        <Route path="/runs" element={<Runs />} />
        <Route path="/operations" element={<Operations />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  </Router>
);

const App: React.FC = () => {
  const [status, setStatus] = useState<OnboardingStatus | null>(null);

  useEffect(() => {
    ApiService.get<OnboardingStatus>('/api/onboarding/status')
      .then(setStatus)
      .catch(() => setStatus({ needs_onboarding: false, profile: 'balanced', positions_count: 0 }));
  }, []);

  if (!status) return null;

  if (status.needs_onboarding) {
    return (
      <Onboarding
        onComplete={() => setStatus({ ...status, needs_onboarding: false })}
      />
    );
  }

  return <MainApp />;
};

export default App;
