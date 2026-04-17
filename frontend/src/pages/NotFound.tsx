import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { AlertCircle } from 'lucide-react';

const NotFound: React.FC = () => {
  const location = useLocation();

  return (
    <div className="bg-card-bg border border-border rounded-lg p-12 flex flex-col items-center justify-center text-center">
      <AlertCircle size={48} className="text-yellow mb-4" />
      <h2 className="text-xl font-bold mb-2">View Under Construction</h2>
      <p className="text-[#8b949e] mb-6">
        The view for <code className="bg-gray-bg px-1.5 py-0.5 rounded text-primary">{location.pathname}</code> is currently being ported to React.
      </p>
      <Link to="/" className="text-primary hover:underline">Return to Dashboard</Link>
    </div>
  );
};

export default NotFound;
