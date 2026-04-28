import type { CompanySnapshot as CS } from '@/types/briefing';
import { ConfidenceDot } from './ConfidenceDot';

interface Row { label: string; value: string | null; level: 'confirmed' | 'uncertain' | 'unconfirmed' }

export function CompanySnapshot({ data }: { data: CS }) {
  const rows: Row[] = [
    { label: 'PARENT COMPANY', value: data.parentCompany, level: data.parentCompany ? 'confirmed' : 'unconfirmed' },
    { label: 'HQ', value: data.hqLocation, level: data.hqLocation ? 'confirmed' : 'unconfirmed' },
    { label: 'FOUNDED', value: data.founded, level: data.founded ? 'confirmed' : 'unconfirmed' },
    { label: 'EMPLOYEES', value: data.employeeRange, level: data.employeeRange ? 'confirmed' : 'unconfirmed' },
    { label: 'REVENUE', value: data.revenue, level: data.revenueConfidence },
  ];
  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">COMPANY SNAPSHOT</div>
      <ul className="flex-1">
        {rows.map((r, i) => (
          <li
            key={r.label}
            className={`flex items-center gap-2 sm:gap-3 py-2.5 sm:py-3 ${i < rows.length - 1 ? 'border-b border-[hsl(var(--divider))]' : ''}`}
          >
            <span className="text-[10px] sm:text-[11px] font-semibold tracking-[0.06em] text-muted-ink w-[110px] sm:w-[140px] shrink-0">{r.label}</span>
            <span className={`flex-1 text-[13px] sm:text-[14px] font-medium break-words ${r.value ? 'text-primary-ink' : 'text-muted-ink'}`}>
              {r.value ?? '—'}
            </span>
            <ConfidenceDot level={r.level} />
          </li>
        ))}
      </ul>
    </section>
  );
}
