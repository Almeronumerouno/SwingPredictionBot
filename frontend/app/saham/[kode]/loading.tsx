export default function Loading() {
  return (
    <div className="space-y-6">
      <div className="h-4 w-24 bg-[var(--color-muted-bg)] rounded" />
      <div className="flex items-end justify-between">
        <div className="space-y-2">
          <div className="h-8 w-32 bg-[var(--color-muted-bg)] rounded" />
          <div className="h-4 w-48 bg-[var(--color-muted-bg)] rounded" />
        </div>
        <div className="text-right space-y-1">
          <div className="h-6 w-28 bg-[var(--color-muted-bg)] rounded ml-auto" />
        </div>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-20 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)]" />
        ))}
      </div>
      <div className="h-[400px] border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)]" />
    </div>
  );
}

