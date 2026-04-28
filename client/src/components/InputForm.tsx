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
    <div className="flex w-full flex-1 items-center">
      <div className="w-full">
        <div className="px-2 pb-6 text-center sm:pb-7">
          <div className="eyebrow mb-3" style={{ letterSpacing: '0.1em' }}>TRADESHOW INTELLIGENCE</div>
          <h1 className="text-[30px] sm:text-[38px] md:text-[44px] leading-[1.06] font-bold text-primary-ink tracking-[-0.03em]">
          Know before you walk up.
          </h1>
          <p className="mx-auto mt-3 text-[14px] sm:text-[16px] text-secondary-ink max-w-[460px] leading-relaxed">
            Enter a company name and get a decision-ready briefing before you reach the booth.
          </p>
        </div>

        <form
          onSubmit={submit}
          className="mx-auto w-full max-w-[540px] rounded-xl border border-border bg-white p-5 sm:p-6"
          style={{ boxShadow: 'var(--shadow-input)' }}
        >
          <label className="eyebrow block mb-2">COMPANY NAME *</label>
          <input
            autoFocus
            value={company}
            onChange={e => setCompany(e.target.value)}
            placeholder="e.g. Krones AG, SMC Corporation, Bobst"
            className="w-full h-11 px-4 text-[15px] rounded-lg border border-[hsl(var(--input))] bg-white outline-none transition focus:border-[hsl(var(--primary))]"
            style={{ boxShadow: 'none' }}
            onFocus={e => (e.currentTarget.style.boxShadow = 'var(--shadow-focus)')}
            onBlur={e => (e.currentTarget.style.boxShadow = 'none')}
          />

          <div className="h-3" />

          <label className="eyebrow block mb-2">EXTRA CONTEXT (optional)</label>
          <textarea
            value={context}
            onChange={e => setContext(e.target.value)}
            placeholder="e.g. saw a labeling machine, booth #3402, they're demoing a palletizer"
            className="w-full h-[84px] overflow-hidden px-4 py-3 text-[14px] rounded-lg border border-[hsl(var(--input))] bg-white outline-none resize-none transition focus:border-[hsl(var(--primary))]"
            onFocus={e => (e.currentTarget.style.boxShadow = 'var(--shadow-focus)')}
            onBlur={e => (e.currentTarget.style.boxShadow = 'none')}
          />

          <div className="mt-4 flex items-center gap-3">
            <button
              type="submit"
              disabled={!company.trim()}
              className="flex-1 h-11 rounded-lg font-semibold text-[15px] text-white bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-hover))] active:scale-[0.99] transition disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ letterSpacing: '0.01em' }}
            >
              Enrich
            </button>
            <div className="text-[11px] text-secondary-ink">Usually under 60s</div>
          </div>
        </form>

        <div className="mt-5 text-center text-[12px] text-secondary-ink px-2">
          <span className="inline-flex flex-wrap justify-center gap-x-3 gap-y-1">
            <span>✓ Source-backed claims</span>
            <span className="text-muted-ink hidden sm:inline">·</span>
            <span>✓ No hallucinated names</span>
            <span className="text-muted-ink hidden sm:inline">·</span>
            <span>✓ Uncertainty surfaced honestly</span>
          </span>
        </div>
      </div>
    </div>
  );
}
