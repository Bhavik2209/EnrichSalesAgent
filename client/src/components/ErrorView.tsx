import { AlertTriangle } from 'lucide-react';

export function ErrorView({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="max-w-[480px] mx-auto mt-24 card-surface p-8 text-center">
      <div className="mx-auto h-12 w-12 rounded-full bg-[hsl(var(--danger-tint))] text-[hsl(var(--danger))] flex items-center justify-center">
        <AlertTriangle size={22} />
      </div>
      <h3 className="mt-4 text-[20px] font-bold text-primary-ink">Something went wrong</h3>
      <p className="mt-2 text-[14px] text-secondary-ink">{message}</p>
      <button
        onClick={onRetry}
        className="mt-5 h-10 px-4 rounded-md bg-[hsl(var(--primary))] hover:bg-[hsl(var(--primary-hover))] text-white text-[14px] font-medium"
      >
        Try Again
      </button>
    </div>
  );
}
