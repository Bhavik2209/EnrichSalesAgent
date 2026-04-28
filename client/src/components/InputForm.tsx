import { useState } from 'react';

interface Props {
  onSubmit: (companyName: string, context: string) => void;
}

export function InputForm({ onSubmit }: Props) {
  const [company, setCompany] = useState('');
  const [context, setContext] = useState('');

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!company.trim()) return;
    onSubmit(company.trim(), context.trim());
  };

  return (
    <div className="w-full">
      <div className="text-center mb-8 sm:mb-10 pt-10 sm:pt-20 px-2">
        <div className="eyebrow mb-4" style={{ letterSpacing: '0.1em' }}>TRADESHOW INTELLIGENCE</div>
        <h1 className="text-[32px] sm:text-[40px] md:text-[48px] leading-[1.08] font-bold text-primary-ink tracking-[-0.03em]">
          Know before you walk up.
        </h1>
        <p className="mx-auto mt-4 sm:mt-5 text-[15px] sm:text-[18px] text-secondary-ink max-w-[480px] leading-relaxed">
          Enter a company name. Get a decision-ready briefing in 60 seconds — before you reach the booth.
        </p>
      </div>

      <form
        onSubmit={submit}
        className="mx-auto w-full max-w-[560px] bg-white border border-border rounded-xl p-5 sm:p-8"
        style={{ boxShadow: 'var(--shadow-input)' }}
      >
        <label className="eyebrow block mb-2">COMPANY NAME *</label>
        <input
          autoFocus
          value={company}
          onChange={e => setCompany(e.target.value)}
          placeholder="e.g. Krones AG, SMC Corporation, Bobst"
          className="w-full h-12 px-4 text-[16px] rounded-lg border border-[hsl(var(--input))] bg-white outline-none transition focus:border-[hsl(var(--primary))]"
          style={{ boxShadow: 'none' }}
          onFocus={e => (e.currentTarget.style.boxShadow = 'var(--shadow-focus)')}
          onBlur={e => (e.currentTarget.style.boxShadow = 'none')}
        />

        <div className="h-4" />

        <label className="eyebrow block mb-2">EXTRA CONTEXT  (optional)</label>
        <textarea
          value={context}
          onChange={e => setContext(e.target.value)}
          placeholder="e.g. saw a labeling machine, booth #3402, they're demoing a palletizer"
          className="w-full h-[72px] px-4 py-3 text-[14px] rounded-lg border border-[hsl(var(--input))] bg-white outline-none resize-none transition focus:border-[hsl(var(--primary))]"
          onFocus={e => (e.currentTarget.style.boxShadow = 'var(--shadow-focus)')}
          onBlur={e => (e.currentTarget.style.boxShadow = 'none')}
        />

        <div className="h-6" />

        <button
          type="submit"
          disabled={!company.trim()}
          className="w-full h-12 rounded-lg font-semibold text-[15px] text-white bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-hover))] active:scale-[0.99] transition disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ letterSpacing: '0.01em' }}
        >
          Enrich →
        </button>
      </form>

      <div className="mt-6 text-center text-[12px] sm:text-[13px] text-secondary-ink px-2">
        <span className="inline-flex flex-wrap justify-center gap-x-3 gap-y-1">
          <span>✓ Source-backed claims</span>
          <span className="text-muted-ink hidden sm:inline">·</span>
          <span>✓ No hallucinated names</span>
          <span className="text-muted-ink hidden sm:inline">·</span>
          <span>✓ Uncertainty surfaced honestly</span>
        </span>
      </div>

      <div className="mt-8 sm:mt-10 mx-auto grid grid-cols-3 gap-2 sm:gap-3 max-w-[480px]">
        {[
          { n: '< 60s', l: 'Full briefing' },
          { n: '100%', l: 'Claims sourced' },
          { n: '0', l: 'Invented facts' },
        ].map((s, i) => (
          <div key={i} className="bg-white border border-border rounded-lg py-3 sm:py-4 px-2 sm:px-6 text-center">
            <div className="text-[20px] sm:text-[28px] font-bold text-[hsl(var(--primary))] leading-none">{s.n}</div>
            <div className="mt-1.5 sm:mt-2 text-[11px] sm:text-[12px] text-secondary-ink">{s.l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
