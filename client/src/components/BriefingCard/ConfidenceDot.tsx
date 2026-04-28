import type { ConfidenceLevel } from '@/types/briefing';

const COLORS: Record<ConfidenceLevel, string> = {
  confirmed: 'hsl(var(--success))',
  uncertain: 'hsl(var(--warning))',
  unconfirmed: 'hsl(var(--input))',
};

export function ConfidenceDot({ level, title }: { level: ConfidenceLevel; title?: string }) {
  return (
    <span
      title={title ?? level}
      className="inline-block h-2 w-2 rounded-full shrink-0"
      style={{ background: COLORS[level] }}
    />
  );
}
