import React from 'react';

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  variant?: 'default' | 'green' | 'red' | 'yellow';
}

const variantClass: Record<NonNullable<StatCardProps['variant']>, string> = {
  default: 'text-[#e6edf3]',
  green: 'text-green',
  red: 'text-red',
  yellow: 'text-yellow',
};

const StatCard: React.FC<StatCardProps> = ({ label, value, hint, variant = 'default' }) => (
  <div className="bg-card-bg border border-border rounded-lg p-4 min-w-[120px]">
    <div className="text-[11px] text-[#8b949e] uppercase tracking-wide mb-1">{label}</div>
    <div className={`text-lg font-semibold font-mono ${variantClass[variant]}`}>{value}</div>
    {hint ? <div className="text-[10px] text-[#6e7681] mt-1">{hint}</div> : null}
  </div>
);

export default StatCard;
