"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";

export default function DateSelector({
  selected,
  basePath,
}: {
  selected?: string;
  basePath?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    const target = basePath || pathname;

    if (v) {
      const params = new URLSearchParams(searchParams.toString());
      params.set("date", v);
      router.push(`${target}?${params.toString()}`);
    } else {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("date");
      const qs = params.toString();
      router.push(qs ? `${target}?${qs}` : target);
    }
  }

  return (
    <div className="relative inline-flex items-center gap-2">
      <div className="absolute left-3 pointer-events-none text-[var(--color-text-muted)]">
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <input
        type="date"
        defaultValue={selected || ""}
        onChange={handleChange}
        max={new Date().toISOString().slice(0, 10)}
        className="h-9 pl-9 pr-3 text-sm font-medium border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/20 focus:border-[var(--color-primary)]/40 transition-all duration-200 shadow-sm hover:border-[var(--color-text-muted)] cursor-pointer"
      />
    </div>
  );
}
