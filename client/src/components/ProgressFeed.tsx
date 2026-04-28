import { Search, Globe, User, Newspaper, Sparkles, CheckCircle2 } from 'lucide-react';
import type { ProgressStep, ProgressStepType } from '@/types/briefing';

const ICONS: Record<ProgressStepType, any> = {
  search: Search,
  fetch: Globe,
  person: User,
  news: Newspaper,
  synthesis: Sparkles,
  done: CheckCircle2,
};

interface Props {
  steps: ProgressStep[];
}

export function ProgressFeed({ steps }: Props) {
  return (
    <div>
      <div className="eyebrow mb-2">AGENT ACTIVITY</div>
      <div className="bg-white border border-border rounded-lg p-4 max-h-[480px] overflow-y-auto">
        {steps.length === 0 && (
          <div className="text-[13px] text-muted-ink py-2">Waiting for the agent...</div>
        )}
        <ul className="space-y-1">
          {steps.map(step => {
            const Icon = ICONS[step.type] ?? Search;
            const isActive = step.status === 'active';
            const isFailed = step.status === 'failed';
            return (
              <li
                key={step.id}
                className={`animate-fade-up flex items-center gap-3 rounded-md px-3 py-2.5 ${
                  isActive ? 'bg-[hsl(var(--primary-tint))] border-l-[3px] border-[hsl(var(--primary))]' : ''
                }`}
              >
                <Icon size={16} className={isActive ? 'text-[hsl(var(--primary))]' : 'text-secondary-ink'} />
                <span className="font-mono text-[10px] text-muted-ink shrink-0">{step.timestamp}</span>
                <span className="text-[13px] text-body-ink flex-1 leading-snug">{step.message}</span>
                <span
                  className={`h-2 w-2 rounded-full shrink-0 ${
                    isActive
                      ? 'bg-[hsl(var(--primary))] pulse-dot'
                      : isFailed
                      ? 'bg-[hsl(var(--danger))]'
                      : step.status === 'done'
                      ? 'bg-[hsl(var(--success))]'
                      : 'bg-[hsl(var(--text-muted))]'
                  }`}
                />
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
