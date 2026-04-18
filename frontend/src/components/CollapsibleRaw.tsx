import React, { useState } from 'react';

interface CollapsibleRawProps {
  label?: string;
  data: unknown;
}

/** Raw JSON for debugging — collapsed by default. */
const CollapsibleRaw: React.FC<CollapsibleRawProps> = ({ label = 'Données brutes (JSON)', data }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-4 border border-[#21262d] rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left px-3 py-2 text-xs text-[#8b949e] hover:bg-[#1c2128] hover:text-[#c9d1d9] flex justify-between items-center"
      >
        <span>{label}</span>
        <span className="text-primary">{open ? '▼' : '▶'}</span>
      </button>
      {open ? (
        <pre className="text-[11px] font-mono text-[#8b949e] p-3 max-h-64 overflow-auto border-t border-[#21262d] bg-terminal-bg whitespace-pre-wrap break-words">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </div>
  );
};

export default CollapsibleRaw;
