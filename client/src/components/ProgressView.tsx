import { useEffect, useMemo, useState } from 'react';
import { Clock3, DatabaseZap, Globe, ScanSearch, Sparkles, UserRoundSearch } from 'lucide-react';
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
  { key: 'cache', label: 'Cache Check', desc: 'Checking stored results before live research.', icon: DatabaseZap },
  { key: 'discovery', label: 'Discovery', desc: 'Resolving the official site and company identity.', icon: Globe },
  { key: 'enrichment', label: 'Enrichment', desc: 'Querying Hunter first, then provider fallbacks if needed.', icon: ScanSearch },
  { key: 'scrape', label: 'Profile Scrape', desc: 'Website/profile extraction only when Hunter leaves gaps.', icon: ScanSearch },
  { key: 'aftermarket', label: 'Aftermarket', desc: 'Confirming service, support, and parts signals.', icon: ScanSearch },
  { key: 'people', label: 'People', desc: 'Finding the strongest contact or fallback title.', icon: UserRoundSearch },
  { key: 'opening_line', label: 'Opening Line', desc: 'Writing the personalized outreach line.', icon: Sparkles },
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

  return (
    <div className="min-h-[calc(100vh-56px)] bg-[radial-gradient(circle_at_top_left,_rgba(249,115,22,0.08),_transparent_35%),linear-gradient(180deg,_#fff,_#fbfbfc_100%)]">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-5 sm:gap-6">
          <section className="card-surface p-5 sm:p-6 overflow-hidden relative">
            <div className="absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,_hsl(var(--primary)),_rgba(249,115,22,0.25))]" />
            <div className="flex flex-col gap-5">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div>
                  <div className="eyebrow">LIVE RESEARCH</div>
                  <h1 className="mt-2 text-[26px] sm:text-[34px] font-bold text-primary-ink leading-tight tracking-[-0.03em] break-words">
                    Building a briefing for {companyName}
                  </h1>
                  <p className="mt-2 text-[14px] sm:text-[15px] text-secondary-ink max-w-[62ch]">
                    The backend is streaming real research activity from discovery, Hunter enrichment, fallback providers, scraping, aftermarket analysis, people targeting, and opening-line generation.
                  </p>
                </div>
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-[hsl(var(--surface))] px-4 py-3 min-w-[140px]">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Elapsed</div>
                  <div className="mt-1 flex items-center gap-2 text-[20px] font-semibold text-primary-ink">
                    <Clock3 size={18} className="text-[hsl(var(--primary))]" />
                    <span className="font-mono">{fmt(elapsed)}</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Events</div>
                  <div className="mt-1 text-[22px] font-semibold text-primary-ink">{steps.length}</div>
                </div>
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Stages Done</div>
                  <div className="mt-1 text-[22px] font-semibold text-primary-ink">{summary.doneCount}</div>
                </div>
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Running</div>
                  <div className="mt-1 text-[22px] font-semibold text-primary-ink">{summary.runningCount}</div>
                </div>
                <div className="rounded-2xl border border-[hsl(var(--divider))] bg-white px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.08em] text-muted-ink">Current</div>
                  <div className="mt-1 text-[12px] leading-snug text-secondary-ink">
                    {summary.lastMessage}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {STAGE_CARDS.map((item) => {
                  const Icon = item.icon;
                  const state = summary.stageStates.get(item.key) ?? 'idle';
                  const tone =
                    state === 'failed'
                      ? 'border-[hsl(var(--danger-border))] bg-[hsl(var(--danger-tint))]'
                      : state === 'running'
                      ? 'border-[hsl(var(--primary))]/25 bg-[hsl(var(--primary-tint-strong))]'
                      : state === 'done'
                      ? 'border-[hsl(var(--success-border))] bg-[hsl(var(--success-tint))]'
                      : 'border-[hsl(var(--divider))] bg-white';

                  return (
                    <div key={item.key} className={`rounded-2xl border px-4 py-4 ${tone}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/80 text-[hsl(var(--primary))]">
                            <Icon size={18} />
                          </div>
                          <div className="min-w-0">
                            <div className="text-[14px] font-semibold text-primary-ink">{item.label}</div>
                            <div className="mt-1 text-[12px] leading-relaxed text-secondary-ink">{item.desc}</div>
                          </div>
                        </div>
                        <span className="inline-flex items-center rounded-full border border-[hsl(var(--divider))] bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.06em] text-secondary-ink">
                          {state}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </section>

          <div className="xl:row-span-2">
            <ProgressFeed steps={steps} />
          </div>
        </div>
      </div>
    </div>
  );
}
