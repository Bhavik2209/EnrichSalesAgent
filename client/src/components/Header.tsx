export function Header() {
  return (
    <header className="sticky top-0 z-30 bg-white border-b border-border">
      <div className="max-w-[1200px] mx-auto flex items-center justify-between px-4 sm:px-6 h-14">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-[2px] bg-[hsl(var(--primary))]" aria-hidden />
            <span className="text-[16px] sm:text-[18px] font-extrabold tracking-tight text-primary-ink">EnrichSalesAgent</span>
          </div>
        </div>
        <span className="inline-flex items-center rounded-full border border-[hsl(var(--primary))] text-[hsl(var(--primary))] text-[10px] sm:text-[11px] font-semibold px-2 sm:px-2.5 py-0.5 tracking-wide shrink-0">
          BETA
        </span>
      </div>
    </header>
  );
}
