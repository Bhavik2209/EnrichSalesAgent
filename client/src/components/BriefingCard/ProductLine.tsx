import { SourceChip } from './SourceChip';

interface Props { text: string | null; tags: string[]; sources: string[] }

export function ProductLine({ text, tags, sources }: Props) {
  if (!text && tags.length === 0) return null;

  return (
    <section className="card-surface p-5 sm:p-6 animate-section-in h-full flex flex-col">
      <div className="eyebrow mb-3">WHAT THEY MAKE</div>
      {text && <p className="text-[15px] text-body-ink leading-[1.65]">{text}</p>}
      {tags.length > 0 && (
        <div className={text ? 'mt-4' : ''}>
          <div className="text-[10px] sm:text-[11px] font-semibold tracking-[0.06em] text-muted-ink mb-2">RELATED TAGS</div>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span key={tag} className="inline-flex items-center rounded-full border border-border px-2.5 py-1 text-[11px] text-secondary-ink">
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
      {sources.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {sources.map(s => <SourceChip key={s} url={s} />)}
        </div>
      )}
    </section>
  );
}
