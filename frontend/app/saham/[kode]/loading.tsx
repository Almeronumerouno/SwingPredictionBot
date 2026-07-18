export default function Loading() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-zinc-800 rounded" />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-20 bg-zinc-800 rounded-lg" />
        ))}
      </div>
      <div className="h-[400px] bg-zinc-800 rounded-lg" />
    </div>
  );
}
