import { NavLink } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/items", label: "Menu Engineering" },
  { to: "/approvals", label: "Approval Queue" },
  { to: "/validation", label: "Validation" },
];

export function TopNav() {
  return (
    <header className="fixed top-0 left-0 w-full z-50 flex items-center justify-between px-6 h-16 bg-obsidian border-b border-outline">
      <div className="flex items-center gap-8">
        <span className="font-display text-2xl text-fire uppercase tracking-wider">Margin IQ</span>
        <nav className="hidden md:flex items-center gap-6">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `label-caps pb-1 border-b-2 transition-colors ${
                  isActive ? "text-fire border-fire" : "border-transparent hover:text-on-surface"
                }`
              }
              end={l.to === "/"}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3 border border-outline px-3 py-1 label-caps">
        <span>Q1 2026</span>
        <span className="text-fire">•</span>
        <span>ROOK &amp; ROAST</span>
      </div>
    </header>
  );
}
