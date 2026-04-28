import { useState } from 'react';
import { ArrowLeft, Check, Download } from 'lucide-react';
import type { BriefingCard as BC } from '@/types/briefing';
import { copyText, formatBriefingForExport } from '@/utils/clipboard';

interface Props { briefing: BC; onReset: () => void }

export function StickyActionBar({ briefing, onReset }: Props) {
  const [copied, setCopied] = useState(false);
  const onExport = async () => {
    if (await copyText(formatBriefingForExport(briefing))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <div className="fixed bottom-0 inset-x-0 bg-white border-t border-border z-40">
      <div className="max-w-[1200px] mx-auto px-6 py-3 flex items-center justify-between gap-3">
        <button
          onClick={onReset}
          className="inline-flex items-center gap-2 h-9 px-3 rounded-md border border-[hsl(var(--input))] text-[14px] text-body-ink hover:bg-[hsl(var(--surface))] transition"
        >
          <ArrowLeft size={14} /> Search Another Company
        </button>
        <button
          onClick={onExport}
          className={`inline-flex items-center gap-2 h-9 px-4 rounded-md text-[14px] font-medium text-white transition ${
            copied ? 'bg-[hsl(var(--success))]' : 'bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-hover))]'
          }`}
        >
          {copied ? <><Check size={14} /> Copied ✓</> : <><Download size={14} /> Export Briefing</>}
        </button>
      </div>
    </div>
  );
}
