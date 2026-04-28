import { ExternalLink } from 'lucide-react';
import type { RecentSignal } from '@/types/briefing';

export function RecentSignals({ signals }: { signals: RecentSignal[] }) {
  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">RECENT SIGNALS  ·  Last 12 months</div>
      {signals.length === 0 ? (
        <div className="text-[13px] italic text-muted-ink">No signals found in the last 12 months</div>
      ) : (
        <ul>
          {signals.map((s, i) => (
            <li
              key={i}
              className={`py-3 ${i < signals.length - 1 ? 'border-b border-[hsl(var(--divider))]' : ''}`}
            >
              <div className="font-mono text-[11px] text-muted-ink">{s.date}</div>
              <div className="text-[14px] font-medium text-primary-ink mt-1 leading-snug">{s.headline}</div>
              <a
                href={s.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[12px] text-[hsl(var(--info))] mt-1 hover:underline"
              >
                {s.sourceName} <ExternalLink size={11} />
              </a>
              {s.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {s.tags.map(t => (
                    <span key={t} className="inline-block bg-[hsl(var(--divider))] text-secondary-ink text-[11px] rounded-full px-2 py-0.5">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
