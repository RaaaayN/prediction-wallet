import React from 'react';

interface SectionCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}

const SectionCard: React.FC<SectionCardProps> = ({ title, subtitle, children, className = '' }) => (
  <section className={`bg-card-bg border border-border rounded-xl overflow-hidden ${className}`}>
    <div className="px-4 py-3 border-b border-[#21262d] bg-[#11161d]/80">
      <h2 className="text-sm font-semibold text-[#e6edf3] tracking-tight">{title}</h2>
      {subtitle ? <p className="text-xs text-[#8b949e] mt-0.5">{subtitle}</p> : null}
    </div>
    <div className="p-4">{children}</div>
  </section>
);

export default SectionCard;
