import { SourceChip } from './SourceChip';

interface Props { text: string; sources: string[] }

export function ProductLine({ text, sources }: Props) {
  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">WHAT THEY MAKE</div>
      <p className="text-[15px] text-body-ink leading-[1.65]">{text}</p>
      {sources.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {sources.map(s => <SourceChip key={s} url={s} />)}
        </div>
      )}
    </section>
  );
}
