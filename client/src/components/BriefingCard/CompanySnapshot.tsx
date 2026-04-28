import type { CompanySnapshot as CS } from '@/types/briefing';
import { ConfidenceDot } from './ConfidenceDot';
import { SourceChip } from './SourceChip';

interface Row { label: string; value: string | null; level: 'confirmed' | 'uncertain' | 'unconfirmed' }

export function CompanySnapshot({ data }: { data: CS }) {
  const rows: Row[] = [
    { label: 'PARENT COMPANY', value: data.parentCompany, level: data.parentCompany ? 'confirmed' : 'unconfirmed' },
    { label: 'HQ', value: data.hqLocation, level: data.hqLocation ? 'confirmed' : 'unconfirmed' },
    { label: 'FOUNDED', value: data.founded, level: data.founded ? 'confirmed' : 'unconfirmed' },
    { label: 'EMPLOYEES', value: data.employeeRange, level: data.employeeRange ? 'confirmed' : 'unconfirmed' },
    { label: 'REVENUE', value: data.revenue, level: data.revenueConfidence },
    { label: 'PHONE', value: data.phone, level: data.phone ? 'confirmed' : 'unconfirmed' },
  ].filter((row) => Boolean(row.value));

  const hasMeta = rows.length > 0 || data.siteEmails.length > 0 || Boolean(data.website) || Boolean(data.linkedinUrl);
  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">COMPANY SNAPSHOT</div>
      {rows.length > 0 && <ul className="flex-1">
        {rows.map((r, i) => (
          <li
            key={r.label}
            className={`flex items-center gap-2 sm:gap-3 py-2.5 sm:py-3 ${i < rows.length - 1 ? 'border-b border-[hsl(var(--divider))]' : ''}`}
          >
            <span className="text-[10px] sm:text-[11px] font-semibold tracking-[0.06em] text-muted-ink w-[110px] sm:w-[140px] shrink-0">{r.label}</span>
            <span className={`flex-1 text-[13px] sm:text-[14px] font-medium break-words ${r.value ? 'text-primary-ink' : 'text-muted-ink'}`}>
              {r.value}
            </span>
            <ConfidenceDot level={r.level} />
          </li>
        ))}
      </ul>}
      {data.siteEmails.length > 0 && (
        <div className={`${rows.length > 0 ? 'mt-4' : ''}`}>
          <div className="text-[10px] sm:text-[11px] font-semibold tracking-[0.06em] text-muted-ink mb-2">SITE EMAILS</div>
          <div className="flex flex-wrap gap-2">
            {data.siteEmails.map((email) => (
              <span key={email} className="inline-flex items-center rounded-full border border-border px-2.5 py-1 text-[11px] text-secondary-ink">
                {email}
              </span>
            ))}
          </div>
        </div>
      )}
      {(data.website || data.linkedinUrl) && (
        <div className={`${rows.length > 0 || data.siteEmails.length > 0 ? 'mt-4' : ''} flex flex-wrap gap-2`}>
          {data.website && <SourceChip url={data.website} />}
          {data.linkedinUrl && <SourceChip url={data.linkedinUrl} />}
        </div>
      )}
      {!hasMeta && <div className="text-[14px] text-secondary-ink">No company snapshot details were available.</div>}
    </section>
  );
}
