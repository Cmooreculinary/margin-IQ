const STYLES: Record<string, string> = {
  star: "bg-star text-obsidian",
  plowhorse: "bg-plowhorse text-obsidian",
  puzzle: "bg-puzzle text-obsidian",
  dog: "bg-dog text-obsidian",
};

export function QuadrantBadge({ quadrant }: { quadrant: string }) {
  return (
    <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${STYLES[quadrant] || "bg-outline"}`}>
      {quadrant}
    </span>
  );
}
