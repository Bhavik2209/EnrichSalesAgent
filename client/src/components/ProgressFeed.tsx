import { useMemo } from 'react';
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
  if (value.startsWith('company_summary')) return 'Audio Summary';
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
  if (value.startsWith('company_summary') || value.startsWith('opening_line') || value.startsWith('research.complete')) return Sparkles;
  return Globe;
}

interface Props {
  steps: ProgressStep[];
}

export function ProgressFeed({ steps }: Props) {
  const visibleSteps = useMemo(() => steps.slice(-4), [steps]);

  return (
    <section className="rounded-2xl border border-[hsl(var(--divider))] bg-[hsl(var(--surface))] p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="eyebrow">Live Logs</div>
          <div className="mt-1 text-[13px] text-secondary-ink">Latest backend activity.</div>
        </div>
        <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">{steps.length} events</div>
      </div>

      <div className="mt-4">
        {steps.length === 0 && (
          <div className="rounded-2xl border border-dashed border-[hsl(var(--input))] bg-white px-4 py-4">
            <div className="text-[13px] text-secondary-ink">Waiting for the backend stream to start...</div>
            <div className="mt-3 space-y-2">
              {[
                'Resolving company profile',
                'Checking enrichment sources',
                'Inspecting aftermarket signals',
                'Finding the best booth contact',
              ].map((line, index) => (
                <div key={line} className="flex items-center gap-3 text-[12px] text-secondary-ink">
                  <span className="text-muted-ink">{String(index + 1).padStart(2, '0')}</span>
                  <div className="h-2 w-2 rounded-full bg-[hsl(var(--primary))] pulse-dot" />
                  <span>{line}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <ul className="space-y-2">
          {visibleSteps.map((step, index) => {
            const Icon = stageIcon(step.stage);
            const isActive = step.status === 'active';
            const isFailed = step.status === 'failed';
            const isDone = step.status === 'done';
            return (
              <li
                key={step.id}
                className={`animate-fade-up rounded-2xl border px-3 py-3 ${
                  isFailed
                    ? 'border-[hsl(var(--danger-border))] bg-[hsl(var(--danger-tint))]'
                    : isActive
                    ? 'border-[hsl(var(--primary))]/20 bg-[hsl(var(--primary-tint-strong))]'
                    : 'border-[hsl(var(--divider))] bg-white'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                      isFailed
                        ? 'bg-[hsl(var(--danger))]/10 text-[hsl(var(--danger))]'
                        : isActive
                        ? 'bg-[hsl(var(--primary))]/12 text-[hsl(var(--primary))]'
                        : 'bg-[hsl(var(--surface))] text-secondary-ink'
                    }`}
                  >
                    <Icon size={14} />
                  </div>
                  <div className="w-8 shrink-0 pt-0.5 text-[11px] text-muted-ink">
                    {String(steps.length - visibleSteps.length + index + 1).padStart(2, '0')}
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
                    <div className="mt-1.5 text-[13px] leading-relaxed text-body-ink">
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
