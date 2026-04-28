import { useEffect, useMemo, useState } from 'react';
import { Clock3 } from 'lucide-react';
import type { ProgressStep } from '@/types/briefing';
import { ProgressFeed } from './ProgressFeed';

interface Props {
  companyName: string;
  steps: ProgressStep[];
}

function fmt(elapsed: number) {
  const h = Math.floor(elapsed / 3600).toString().padStart(2, '0');
  const m = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
  const s = (elapsed % 60).toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function normalizeStage(stage?: string): string {
  const value = (stage ?? '').toLowerCase();
  if (value.startsWith('cache')) return 'cache';
  if (value.startsWith('discovery')) return 'discovery';
  if (value.startsWith('hunter') || value.startsWith('technology_checker') || value.startsWith('cufinder') || value.startsWith('revenue')) return 'enrichment';
  if (value.startsWith('scraper') || value.startsWith('what_they_make')) return 'scrape';
  if (value.startsWith('aftermarket')) return 'aftermarket';
  if (value.startsWith('people')) return 'people';
  if (value.startsWith('opening_line')) return 'opening_line';
  if (value.startsWith('research.complete')) return 'complete';
  return 'research';
}

const STAGE_CARDS = [
  { key: 'cache', label: 'Cache Check' },
  { key: 'discovery', label: 'Discovery' },
  { key: 'enrichment', label: 'Enrichment' },
  { key: 'scrape', label: 'Profile Scrape' },
  { key: 'aftermarket', label: 'Aftermarket' },
  { key: 'people', label: 'People' },
  { key: 'opening_line', label: 'Opening Line' },
];

export function ProgressView({ companyName, steps }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  const summary = useMemo(() => {
    const stageStates = new Map<string, 'idle' | 'running' | 'done' | 'failed'>();
    for (const step of steps) {
      const key = normalizeStage(step.stage);
      const current = stageStates.get(key);
      if (step.status === 'failed') {
        stageStates.set(key, 'failed');
        continue;
      }
      if (step.status === 'active') {
        if (current !== 'failed') stageStates.set(key, 'running');
        continue;
      }
      if (step.status === 'done' && current !== 'failed' && current !== 'running') {
        stageStates.set(key, 'done');
      }
    }

    const lastMessage = steps.length > 0 ? steps[steps.length - 1]?.message ?? 'Research started...' : 'Waiting for backend research events...';
    const doneCount = Array.from(stageStates.values()).filter((state) => state === 'done').length;
    const runningCount = Array.from(stageStates.values()).filter((state) => state === 'running').length;
    return { stageStates, lastMessage, doneCount, runningCount };
  }, [steps]);

  const activeStage = [...steps].reverse().find((step) => step.status === 'active')?.stage;
  const activeStageLabel = activeStage ? STAGE_CARDS.find((item) => normalizeStage(activeStage) === item.key)?.label ?? 'Research' : 'Research';
  const compactStages = STAGE_CARDS.slice(0, 6);

  return (
    <div className="min-h-[calc(100vh-56px)] bg-[linear-gradient(180deg,_#ffffff,_#f8fafc_100%)]">
      <div className="mx-auto max-w-[1100px] px-4 py-8 sm:px-6">
        <section className="card-surface overflow-hidden">
          <div className="grid gap-0 lg:grid-cols-[0.95fr_1.05fr]">
            <div className="border-b border-[hsl(var(--divider))] p-5 lg:border-b-0 lg:border-r sm:p-6">
              <div className="eyebrow">LIVE RESEARCH</div>
              <h1 className="mt-2 text-[24px] sm:text-[28px] font-bold text-primary-ink leading-tight tracking-[-0.03em] break-words">
                Building a briefing for {companyName}
              </h1>
              <div className="mt-5 rounded-2xl border border-[hsl(var(--divider))] bg-[hsl(var(--surface))] px-4 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Current Stage</div>
                    <div className="mt-1 text-[18px] font-semibold text-primary-ink">{activeStageLabel}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Elapsed</div>
                    <div className="mt-1 flex items-center gap-2 text-[16px] font-semibold text-primary-ink">
                      <Clock3 size={15} className="text-[hsl(var(--primary))]" />
                      <span className="font-mono">{fmt(elapsed)}</span>
                    </div>
                  </div>
                </div>
                <div className="mt-3 text-[13px] leading-relaxed text-secondary-ink">
                  {summary.lastMessage}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3">
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Events</div>
                  <div className="mt-1 text-[18px] font-semibold text-primary-ink">{steps.length}</div>
                </div>
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Done</div>
                  <div className="mt-1 text-[18px] font-semibold text-primary-ink">{summary.doneCount}</div>
                </div>
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Running</div>
                  <div className="mt-1 text-[18px] font-semibold text-primary-ink">{summary.runningCount}</div>
                </div>
              </div>

              <div className="mt-4 grid gap-2">
                {compactStages.map((item) => {
                  const state = summary.stageStates.get(item.key) ?? 'idle';
                  return (
                    <div key={item.key} className="flex items-center justify-between rounded-xl border border-[hsl(var(--divider))] bg-white px-3 py-2.5">
                      <span className="text-[13px] text-primary-ink">{item.label}</span>
                      <span className="text-[11px] uppercase tracking-[0.06em] text-secondary-ink">{state}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="p-5 sm:p-6">
              <ProgressFeed steps={steps} />
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
