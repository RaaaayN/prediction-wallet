import React from 'react';

interface KeyValueTableProps {
  title?: string;
  rows: Record<string, string | number>;
  emptyMessage?: string;
}

const KeyValueTable: React.FC<KeyValueTableProps> = ({ title, rows, emptyMessage = 'Aucune donnée' }) => {
  const keys = Object.keys(rows);
  if (keys.length === 0) {
    return <p className="text-sm text-[#8b949e]">{emptyMessage}</p>;
  }
  return (
    <div>
      {title ? <h3 className="text-xs font-semibold text-[#8b949e] uppercase tracking-wide mb-2">{title}</h3> : null}
      <table>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td className="text-[#8b949e] font-mono text-xs">{k}</td>
              <td className="text-right font-mono text-sm text-[#e6edf3]">{String(rows[k])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default KeyValueTable;
