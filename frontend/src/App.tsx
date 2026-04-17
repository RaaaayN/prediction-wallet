import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Control from './pages/Control';
import Portfolio from './pages/Portfolio';
import Traces from './pages/Traces';
import NotFound from './pages/NotFound';
import Workspace from './pages/Workspace';
import RiskHub from './pages/RiskHub';
import Analytics from './pages/Analytics';
import Audit from './pages/Audit';
import Book from './pages/Book';
import Ideas from './pages/Ideas';
import Blotter from './pages/Blotter';
import RiskDetail from './pages/RiskDetail';
import Regime from './pages/Regime';
import Stress from './pages/Stress';
import Perf from './pages/Perf';
import History from './pages/History';
import MonteCarlo from './pages/MonteCarlo';
import Backtest from './pages/Backtest';
import Correlation from './pages/Correlation';
import Runs from './pages/Runs';

const App: React.FC = () => {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/control" element={<Control />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/traces" element={<Traces />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/riskhub" element={<RiskHub />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="/book" element={<Book />} />
          <Route path="/ideas" element={<Ideas />} />
          <Route path="/blotter" element={<Blotter />} />
          <Route path="/risk" element={<RiskDetail />} />
          <Route path="/regime" element={<Regime />} />
          <Route path="/stress" element={<Stress />} />
          <Route path="/perf" element={<Perf />} />
          <Route path="/history" element={<History />} />
          <Route path="/montecarlo" element={<MonteCarlo />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/correlation" element={<Correlation />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App;
