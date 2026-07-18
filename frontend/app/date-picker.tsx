"use client";

export default function DatePicker({ selected }: { selected: string }) {
  return (
    <input
      type="date"
      defaultValue={selected}
      onChange={(e) => {
        const val = e.target.value;
        const params = new URLSearchParams(window.location.search);
        if (val) params.set("date", val);
        else params.delete("date");
        const qs = params.toString();
        window.location.href = qs ? `/?${qs}` : "/";
      }}
      className="bg-zinc-800 border border-zinc-600 rounded px-3 py-1.5 text-sm text-white"
    />
  );
}
