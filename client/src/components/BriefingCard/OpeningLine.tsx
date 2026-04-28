import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { copyText } from '@/utils/clipboard';

export function OpeningLine({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    if (await copyText(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  return (
    <div
      className="rounded-xl border border-border px-5 sm:px-8 py-6 sm:py-7 mb-4 sm:mb-5 animate-section-in"
      style={{ background: 'hsl(var(--primary-tint-strong))', boxShadow: 'var(--shadow-card)' }}
    >
      <div className="eyebrow mb-3" style={{ color: 'hsl(var(--primary))' }}>YOUR OPENING LINE</div>
      <div className="relative">
        <span
          aria-hidden
          className="absolute -left-1 -top-3 sm:-left-2 sm:-top-4 text-[36px] sm:text-[48px] leading-none font-serif"
          style={{ color: 'hsl(var(--primary))' }}
        >
          “
        </span>
        <p className="text-[16px] sm:text-[20px] italic text-primary-ink leading-[1.5] pl-5 sm:pl-6">
          {text}
        </p>
      </div>
      <div className="mt-5">
        <button
          onClick={handleCopy}
          className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-md border text-[13px] font-medium transition ${
            copied
              ? 'bg-[hsl(var(--success-tint))] text-[hsl(var(--success))] border-[hsl(var(--success-border))]'
              : 'bg-white text-[hsl(var(--primary))] border-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-tint))]'
          }`}
        >
          {copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}
        </button>
      </div>
      <div className="mt-3 text-[12px] text-secondary-ink">
        Personalized based on verified signals. Edit before use.
      </div>
    </div>
  );
}
