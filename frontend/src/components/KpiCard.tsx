export function KpiCard({
  label,
  value,
  delta,
  highlight = false,
}: {
  label: string;
  value: string;
  delta?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`border p-5 flex flex-col justify-between ${
        highlight ? "border-fire shadow-glow bg-surface" : "border-outline bg-surface"
      }`}
    >
      <p className={`label-caps mb-4 ${highlight ? "text-fire" : ""}`}>{label}</p>
      <div className="flex items-baseline gap-2">
        <span className={`data-num text-2xl ${highlight ? "text-fire" : "text-on-surface"}`}>{value}</span>
        {delta && <span className="data-num text-xs text-star">{delta}</span>}
      </div>
    </div>
  );
}
