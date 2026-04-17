import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Control from './pages/Control';
import Portfolio from './pages/Portfolio';
import Traces from './pages/Traces';
import NotFound from './pages/NotFound';

const App: React.FC = () => {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/control" element={<Control />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/traces" element={<Traces />} />
          
          {/* Placeholder for other routes */}
          <Route path="/workspace" element={<NotFound />} />
          <Route path="/riskhub" element={<NotFound />} />
          <Route path="/analytics" element={<NotFound />} />
          <Route path="/audit" element={<NotFound />} />
          <Route path="/book" element={<NotFound />} />
          <Route path="/ideas" element={<NotFound />} />
          <Route path="/blotter" element={<NotFound />} />
          <Route path="/risk" element={<NotFound />} />
          <Route path="/regime" element={<NotFound />} />
          <Route path="/stress" element={<NotFound />} />
          <Route path="/perf" element={<NotFound />} />
          <Route path="/history" element={<NotFound />} />
          <Route path="/montecarlo" element={<NotFound />} />
          <Route path="/backtest" element={<NotFound />} />
          <Route path="/correlation" element={<NotFound />} />
          <Route path="/runs" element={<NotFound />} />

          <Route path="*" element={<NotFound />} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App;
