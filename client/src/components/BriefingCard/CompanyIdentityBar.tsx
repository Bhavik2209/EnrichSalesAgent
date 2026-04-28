import { MapPin } from 'lucide-react';
import type { BriefingCard } from '@/types/briefing';
import { GeographyBadge } from './GeographyBadge';

export function CompanyIdentityBar({ b }: { b: BriefingCard }) {
  const s = b.snapshot;
  const showOfficial = s.officialName && s.officialName !== b.companyName;
  const statItems = [
    s.founded ? <div key="founded"><span className="text-secondary-ink">Founded:</span> <span className="text-primary-ink font-medium">{s.founded}</span></div> : null,
    s.employeeRange ? <div key="employees"><span className="text-secondary-ink">Employees:</span> <span className="text-primary-ink font-medium">{s.employeeRange}</span></div> : null,
    s.revenue ? (
      <div key="revenue" className="col-span-2">
        <span className="text-secondary-ink">Revenue:</span>{' '}
        {s.revenueConfidence === 'confirmed' ? (
          <span className="text-primary-ink font-medium">{s.revenue}</span>
        ) : (
          <span className="text-[hsl(var(--warning))] font-medium">{s.revenue}</span>
        )}
      </div>
    ) : null,
  ].filter(Boolean);

  return (
    <div className="bg-white border border-border rounded-xl px-5 sm:px-8 py-5 sm:py-6 mb-4 sm:mb-5 animate-section-in" style={{ boxShadow: 'var(--shadow-card)' }}>
      <div className="flex flex-col md:flex-row md:items-center gap-4 md:gap-5">
        <div className="flex-1 min-w-0">
          <h2 className="text-[22px] sm:text-[28px] font-bold text-primary-ink leading-tight tracking-[-0.02em] break-words">{b.companyName}</h2>
          {showOfficial && <div className="text-[14px] text-secondary-ink mt-0.5">{s.officialName}</div>}
          {s.hqLocation && (
            <div className="text-[13px] text-secondary-ink mt-2 flex items-center gap-1.5">
              <MapPin size={13} /> {s.hqLocation}
            </div>
          )}
        </div>
        <div className="flex-shrink-0 self-start md:self-auto">
          <GeographyBadge status={s.geographyStatus} />
        </div>
        {statItems.length > 0 && (
          <div className="flex-shrink-0 md:text-right text-[13px] space-y-0.5 grid grid-cols-2 md:block gap-x-4 md:gap-x-0 pt-3 md:pt-0 border-t md:border-t-0 border-[hsl(var(--divider))]">
            {statItems}
          </div>
        )}
      </div>
    </div>
  );
}
