import type { GeographyStatus } from '@/types/briefing';

interface Props { status: GeographyStatus }

export function GeographyBadge({ status }: Props) {
  if (status === 'target') {
    return (
      <span className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-md text-[13px] font-semibold border bg-[hsl(var(--success-tint))] text-[hsl(var(--success))] border-[hsl(var(--success-border))]">
        ✓ TARGET MARKET
      </span>
    );
  }
  if (status === 'flagged') {
    return (
      <span className="pulse-flag inline-flex items-center gap-1 px-3.5 py-1.5 rounded-md text-[13px] font-semibold border bg-[hsl(var(--danger-tint))] text-[hsl(var(--danger))] border-[hsl(var(--danger-border))]">
        ⚠ FLAGGED MARKET
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-3.5 py-1.5 rounded-md text-[13px] font-semibold border bg-[hsl(var(--warning-tint))] text-[hsl(var(--warning))] border-[hsl(var(--warning-border))]">
      ? UNVERIFIED REGION
    </span>
  );
}
