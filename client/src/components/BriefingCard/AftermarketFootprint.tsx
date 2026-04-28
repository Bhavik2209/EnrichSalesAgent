import type { AftermarketFootprint as AF } from '@/types/briefing';
import { ExternalLink } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import { SourceChip } from './SourceChip';

export function AftermarketFootprint({ data }: { data: AF }) {
  const hasContent = data.hasPortal !== null || Boolean(data.description) || Boolean(data.portalUrl) || data.emails.length > 0 || data.sources.length > 0;
  if (!hasContent) return null;

  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">AFTERMARKET FOOTPRINT</div>
      <div className="mb-3">
        {data.hasPortal === true && <StatusBadge variant="success">Yes ✓</StatusBadge>}
        {data.hasPortal === false && <StatusBadge variant="danger">No</StatusBadge>}
        {data.hasPortal === null && <StatusBadge variant="warning">Uncertain</StatusBadge>}
      </div>
      {data.description && <p className="text-[14px] text-body-ink leading-relaxed">{data.description}</p>}
      {data.emails.length > 0 && (
        <div className="mt-3">
          <div className="text-[10px] sm:text-[11px] font-semibold tracking-[0.06em] text-muted-ink mb-2">EMAIL SIGNALS</div>
          <div className="flex flex-wrap gap-2">
            {data.emails.map((email) => (
              <span key={email} className="inline-flex items-center rounded-full border border-border px-2.5 py-1 text-[11px] text-secondary-ink">
                {email}
              </span>
            ))}
          </div>
        </div>
      )}
      {data.portalUrl && (
        <a
          href={data.portalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-md border border-[hsl(var(--info))]/20 bg-[hsl(var(--info-tint))] px-3 py-1.5 text-[13px] text-[hsl(var(--info))] hover:underline"
        >
          View supporting link
          <ExternalLink size={12} />
        </a>
      )}
      {data.sources.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {data.sources.map(s => <SourceChip key={s} url={s} />)}
        </div>
      )}
    </section>
  );
}
