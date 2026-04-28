import { SourceChip } from './SourceChip';

export function SourcesFooter({ sources }: { sources: string[] }) {
  return (
    <section className="card-surface px-5 sm:px-8 py-5 animate-section-in">
      <div className="eyebrow mb-3">SOURCES</div>
      <div className="flex flex-wrap gap-2">
        {sources.map((s, i) => <SourceChip key={s} url={s} index={i + 1} />)}
      </div>
    </section>
  );
}
