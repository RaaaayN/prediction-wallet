import React from 'react';

interface JsonPanelProps {
  title: string;
  data: unknown;
  className?: string;
}

/** Pretty-print JSON for API inspection (development-style panels). */
const JsonPanel: React.FC<JsonPanelProps> = ({ title, data, className = '' }) => (
  <div className={`bg-card-bg border border-border rounded-lg p-4 ${className}`}>
    <h2 className="text-sm font-semibold text-[#8b949e] uppercase tracking-wide mb-2">{title}</h2>
    <pre className="text-xs font-mono text-[#c9d1d9] overflow-x-auto max-h-[480px] overflow-y-auto whitespace-pre-wrap break-words">
      {JSON.stringify(data, null, 2)}
    </pre>
  </div>
);

export default JsonPanel;
