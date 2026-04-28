import type { AftermarketFootprint as AF } from '@/types/briefing';
import { ExternalLink } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import { SourceChip } from './SourceChip';

export function AftermarketFootprint({ data }: { data: AF }) {
  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">AFTERMARKET FOOTPRINT</div>
      <div className="mb-3">
        {data.hasPortal === true && <StatusBadge variant="success">Yes ✓</StatusBadge>}
        {data.hasPortal === false && <StatusBadge variant="danger">No</StatusBadge>}
        {data.hasPortal === null && <StatusBadge variant="warning">Uncertain</StatusBadge>}
      </div>
      <p className="text-[14px] text-body-ink leading-relaxed">{data.description}</p>
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
