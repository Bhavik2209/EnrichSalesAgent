import type { BoothContact as BC } from '@/types/briefing';
import { StatusBadge } from './StatusBadge';
import { SourceChip } from './SourceChip';

export function BoothContact({ data }: { data: BC }) {
  const hasDirectContact = Boolean(data.name || data.email || data.sourceUrl);
  const badge = data.isVerified
    ? { variant: 'success' as const, label: 'Verified ✓' }
    : hasDirectContact
      ? { variant: 'warning' as const, label: 'Contact Found' }
      : { variant: 'warning' as const, label: 'Role Estimate' };

  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">RIGHT PERSON AT THE BOOTH</div>
      <div className="flex items-center gap-2 flex-wrap">
        <div className="text-[16px] font-semibold text-primary-ink">{data.name ?? data.title}</div>
        <StatusBadge variant={badge.variant}>{badge.label}</StatusBadge>
      </div>

      {data.name && (
        <div className="text-[14px] text-secondary-ink mt-0.5">{data.title}</div>
      )}

      {data.email && (
        <a
          href={`mailto:${data.email}`}
          className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-md border border-[hsl(var(--info))]/20 bg-[hsl(var(--info-tint))] px-3 py-1.5 text-[13px] text-[hsl(var(--info))] hover:underline"
        >
          {data.email}
        </a>
      )}

      {data.reasoning && <p className="text-[13px] text-secondary-ink italic mt-3 leading-relaxed">{data.reasoning}</p>}

      <div className="mt-3 flex flex-wrap gap-2">
        {data.sourceLabel && (
          <span className="inline-flex items-center rounded-full border border-border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.04em] text-secondary-ink">
            Source: {data.sourceLabel}
          </span>
        )}
        {data.sourceUrl && <SourceChip url={data.sourceUrl} />}
      </div>
    </section>
  );
}
