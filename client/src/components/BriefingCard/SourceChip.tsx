import { ExternalLink } from 'lucide-react';

interface Props {
  url: string;
  label?: string;
  index?: number;
}

export function SourceChip({ url, label, index }: Props) {
  let display = label;
  if (!display) {
    try { display = new URL(url).hostname.replace('www.', ''); } catch { display = url; }
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 font-mono text-[12px] text-[hsl(var(--info))] bg-[hsl(var(--surface))] border border-border rounded px-2 py-[3px] hover:bg-[hsl(var(--info-tint))] hover:underline transition"
    >
      {typeof index === 'number' && <span className="text-secondary-ink">{index}.</span>}
      <span className="truncate max-w-[260px]">{display}</span>
      <ExternalLink size={11} />
    </a>
  );
}
