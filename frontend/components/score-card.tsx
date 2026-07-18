interface Props {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
  negative?: boolean;
}

export default function ScoreCard({ label, value, sub, positive, negative }: Props) {
  const color = positive ? "text-green-400" : negative ? "text-red-400" : "text-white";
  return (
    <div className="bg-zinc-800 rounded-lg p-3">
      <p className="text-xs text-zinc-400 mb-0.5">{label}</p>
      <p className={`text-lg font-bold tabular-nums ${color}`}>{value}</p>
      {sub && <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>}
    </div>
  );
}
