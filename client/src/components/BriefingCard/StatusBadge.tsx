type Variant = 'success' | 'warning' | 'danger' | 'neutral';

const STYLES: Record<Variant, string> = {
  success: 'bg-[hsl(var(--success-tint))] text-[hsl(var(--success))] border-[hsl(var(--success-border))]',
  warning: 'bg-[hsl(var(--warning-tint))] text-[hsl(var(--warning))] border-[hsl(var(--warning-border))]',
  danger: 'bg-[hsl(var(--danger-tint))] text-[hsl(var(--danger))] border-[hsl(var(--danger-border))]',
  neutral: 'bg-[hsl(var(--surface))] text-secondary-ink border-border',
};

export function StatusBadge({ variant = 'neutral', children }: { variant?: Variant; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 border rounded-md px-2.5 py-1 text-[12px] font-semibold ${STYLES[variant]}`}>
      {children}
    </span>
  );
}
