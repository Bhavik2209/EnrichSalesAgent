import { useEffect, useState } from 'react';
import type { BriefingCard as BC, ProgressStep } from '@/types/briefing';
import { ProgressFeed } from './ProgressFeed';
import { BriefingPreview } from './BriefingPreview';

interface Props {
  companyName: string;
  steps: ProgressStep[];
  briefing: BC | null;
  completedStepCount: number;
}

function fmt(elapsed: number) {
  const h = Math.floor(elapsed / 3600).toString().padStart(2, '0');
  const m = Math.floor((elapsed % 3600) / 60).toString().padStart(2, '0');
  const s = (elapsed % 60).toString().padStart(2, '0');
  return `${h}:${m}:${s}`;
}

export function ProgressView({ companyName, steps, briefing, completedStepCount }: Props) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <div>
      <div className="bg-white border-b border-border">
        <div className="max-w-[1200px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-baseline gap-3">
            <span className="text-[16px] font-semibold text-primary-ink">{companyName}</span>
            <span className="text-[13px] text-secondary-ink">Researching...</span>
          </div>
          <span className="font-mono text-[13px] text-secondary-ink">{fmt(elapsed)}</span>
        </div>
        <div className="h-1 w-full bg-[hsl(var(--divider))] overflow-hidden">
          <div className="h-full bg-[hsl(var(--primary))] progress-grow" />
        </div>
      </div>

      <div className="max-w-[1100px] mx-auto px-6 mt-8 grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2">
          <ProgressFeed steps={steps} />
        </div>
        <div className="lg:col-span-3">
          <BriefingPreview companyName={companyName} steps={steps} briefing={briefing} completedStepCount={completedStepCount} />
        </div>
      </div>
    </div>
  );
}
