import { useEffect, useState } from 'react';
import { Check, Copy, Pause, Volume2 } from 'lucide-react';
import { copyText } from '@/utils/clipboard';

interface Props {
  companyName: string;
  text: string;
}

export function CompanySummary({ companyName, text }: Props) {
  const [copied, setCopied] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window;

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const handleCopy = async () => {
    if (await copyText(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSpeak = () => {
    if (!canSpeak) return;
    if (isPlaying) {
      window.speechSynthesis.cancel();
      setIsPlaying(false);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.onend = () => setIsPlaying(false);
    utterance.onerror = () => setIsPlaying(false);
    setIsPlaying(true);
    window.speechSynthesis.speak(utterance);
  };

  return (
    <div
      className="rounded-xl border border-border px-5 sm:px-8 py-6 sm:py-7 mb-4 sm:mb-5 animate-section-in"
      style={{ background: 'linear-gradient(135deg, hsl(var(--surface)) 0%, hsl(var(--primary-tint)) 100%)', boxShadow: 'var(--shadow-card)' }}
    >
      <div className="eyebrow mb-3" style={{ color: 'hsl(var(--primary))' }}>QUICK COMPANY SUMMARY</div>
      <p className="text-[15px] sm:text-[18px] text-primary-ink leading-[1.65]">
        {text}
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <button
          onClick={handleSpeak}
          disabled={!canSpeak}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border text-[13px] font-medium transition bg-white text-[hsl(var(--primary))] border-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-tint))] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isPlaying ? <><Pause size={13} /> Stop Audio</> : <><Volume2 size={13} /> Play Audio</>}
        </button>
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
        Short narration for {companyName}. Audio uses your browser voice on this device.
      </div>
    </div>
  );
}
