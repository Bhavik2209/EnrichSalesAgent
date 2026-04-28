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
    <div className="fixed bottom-0 inset-x-0 bg-white/95 backdrop-blur border-t border-border z-40">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-3">
        <div className="grid grid-cols-2 gap-3">
        <button
          onClick={onReset}
          className="inline-flex min-w-0 items-center justify-center gap-2 min-h-12 px-3 sm:px-4 rounded-xl border border-[hsl(var(--input))] bg-white text-[13px] sm:text-[14px] font-semibold text-body-ink hover:bg-[hsl(var(--surface))] transition text-center leading-tight shadow-sm"
        >
          <ArrowLeft size={15} className="shrink-0" />
          <span>Search Another Company</span>
        </button>
        <button
          onClick={onExport}
          className={`inline-flex min-w-0 items-center justify-center gap-2 min-h-12 px-3 sm:px-4 rounded-xl text-[13px] sm:text-[14px] font-semibold text-white transition text-center leading-tight shadow-sm ${
            copied ? 'bg-[hsl(var(--success))]' : 'bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-hover))]'
          }`}
        >
          {copied ? (
            <>
              <Check size={15} className="shrink-0" />
              <span>Copied</span>
            </>
          ) : (
            <>
              <Download size={15} className="shrink-0" />
              <span>Export Briefing</span>
            </>
          )}
        </button>
        </div>
      </div>
    </div>
  );
}
