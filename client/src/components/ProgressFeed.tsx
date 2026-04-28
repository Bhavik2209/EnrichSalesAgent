import { CheckCircle2, Clock3, Globe, Search, Sparkles, User, Wrench, XCircle } from 'lucide-react';
import type { ProgressStep } from '@/types/briefing';

function stageLabel(stage?: string): string {
  const value = (stage ?? '').toLowerCase();
  if (value.startsWith('cache')) return 'Cache';
  if (value.startsWith('discovery')) return 'Discovery';
  if (value.startsWith('hunter')) return 'Hunter';
  if (value.startsWith('technology_checker')) return 'Technology Checker';
  if (value.startsWith('cufinder')) return 'CUFinder';
  if (value.startsWith('scraper')) return 'Website Scrape';
  if (value.startsWith('aftermarket')) return 'Aftermarket';
  if (value.startsWith('people')) return 'People';
  if (value.startsWith('what_they_make')) return 'What They Make';
  if (value.startsWith('opening_line')) return 'Opening Line';
  if (value.startsWith('research.complete')) return 'Complete';
  return 'Research';
}

function stageIcon(stage?: string) {
  const value = (stage ?? '').toLowerCase();
  if (value.startsWith('cache')) return Clock3;
  if (value.startsWith('discovery')) return Search;
  if (value.startsWith('hunter')) return Globe;
  if (value.startsWith('technology_checker') || value.startsWith('cufinder')) return Wrench;
  if (value.startsWith('people')) return User;
  if (value.startsWith('opening_line') || value.startsWith('research.complete')) return Sparkles;
  return Globe;
}

interface Props {
  steps: ProgressStep[];
}

export function ProgressFeed({ steps }: Props) {
  return (
    <section className="card-surface p-4 sm:p-5 h-full">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div>
          <div className="eyebrow">LIVE RESEARCH FEED</div>
          <div className="text-[13px] text-secondary-ink mt-1">Streaming actual backend activity as it happens.</div>
        </div>
        <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">{steps.length} events</div>
      </div>

      <div className="rounded-xl border border-[hsl(var(--divider))] bg-[hsl(var(--surface))] p-2 sm:p-3 max-h-[560px] overflow-y-auto">
        {steps.length === 0 && (
          <div className="rounded-lg border border-dashed border-[hsl(var(--input))] bg-white px-4 py-6 text-[13px] text-secondary-ink">
            Waiting for the backend stream to start...
          </div>
        )}
        <ul className="space-y-2">
          {steps.map((step) => {
            const Icon = stageIcon(step.stage);
            const isActive = step.status === 'active';
            const isFailed = step.status === 'failed';
            const isDone = step.status === 'done';
            return (
              <li
                key={step.id}
                className={`animate-fade-up rounded-xl border px-3 py-3 sm:px-4 ${
                  isFailed
                    ? 'border-[hsl(var(--danger-border))] bg-[hsl(var(--danger-tint))]'
                    : isActive
                    ? 'border-[hsl(var(--primary))]/20 bg-[hsl(var(--primary-tint-strong))]'
                    : 'border-[hsl(var(--divider))] bg-white'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                      isFailed
                        ? 'bg-[hsl(var(--danger))]/10 text-[hsl(var(--danger))]'
                        : isActive
                        ? 'bg-[hsl(var(--primary))]/12 text-[hsl(var(--primary))]'
                        : 'bg-[hsl(var(--surface))] text-secondary-ink'
                    }`}
                  >
                    <Icon size={16} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-secondary-ink">
                        {stageLabel(step.stage)}
                      </span>
                      <span className="font-mono text-[10px] text-muted-ink">{step.timestamp}</span>
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] ${
                          isFailed
                            ? 'bg-[hsl(var(--danger))]/10 text-[hsl(var(--danger))]'
                            : isActive
                            ? 'bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]'
                            : 'bg-[hsl(var(--success))]/10 text-[hsl(var(--success))]'
                        }`}
                      >
                        {isFailed ? 'Failed' : isActive ? 'Running' : 'Done'}
                      </span>
                    </div>
                    <div className="mt-1 text-[13px] sm:text-[14px] leading-relaxed text-body-ink">
                      {step.message}
                    </div>
                  </div>
                  <div className="shrink-0">
                    {isFailed ? (
                      <XCircle size={16} className="text-[hsl(var(--danger))]" />
                    ) : isDone ? (
                      <CheckCircle2 size={16} className="text-[hsl(var(--success))]" />
                    ) : (
                      <div className="h-2.5 w-2.5 rounded-full bg-[hsl(var(--primary))] pulse-dot" />
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
