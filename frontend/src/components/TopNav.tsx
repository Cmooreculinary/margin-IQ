import { NavLink } from "react-router-dom";
import { ProductCapabilities } from "../lib/api";

type LinkItem = { to: string; label: string; end?: boolean };

export function TopNav({ capabilities }: { capabilities: ProductCapabilities }) {
  const marginEnabled = capabilities.enabled_products.includes("margin_iq");
  const supplyEnabled = capabilities.enabled_products.includes("supply_agent");
  const links: LinkItem[] = [];

  if (capabilities.suite_enabled) links.push({ to: "/", label: "Suite Home", end: true });
  if (marginEnabled) {
    links.push({
      to: capabilities.suite_enabled ? "/margin" : "/",
      label: capabilities.suite_enabled ? "Margin IQ" : "Dashboard",
      end: true,
    });
    links.push(
      { to: "/items", label: "Menu Engineering" },
      { to: "/approvals", label: "Approval Queue" },
      { to: "/validation", label: "Validation" },
      { to: "/engagement", label: "Engagement Plan" },
      { to: "/documents", label: "Upload" }
    );
  }
  if (supplyEnabled) links.push({ to: "/supply-agent", label: "Supply Agent" });

  const brand = capabilities.suite_enabled
    ? "BCA IQ Suite"
    : marginEnabled
      ? "Margin IQ"
      : "Supply Agent";

  return (
    <header className="fixed top-0 left-0 w-full z-50 flex items-center justify-between px-3 md:px-6 h-16 bg-obsidian border-b border-outline">
      <div className="flex items-center gap-5 lg:gap-8 min-w-0">
        <span className="font-display text-2xl text-fire uppercase tracking-wider whitespace-nowrap">{brand}</span>
        <nav className="hidden md:flex items-center gap-3 lg:gap-5 overflow-x-auto">
          {links.map((link) => (
            <NavLink
              key={`${link.to}-${link.label}`}
              to={link.to}
              className={({ isActive }) =>
                `label-caps pb-1 border-b-2 transition-colors whitespace-nowrap ${
                  isActive ? "text-fire border-fire" : "border-transparent hover:text-on-surface"
                }`
              }
              end={link.end}
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="hidden sm:flex items-center gap-3 border border-outline px-3 py-1 label-caps whitespace-nowrap">
        <span>{capabilities.deployment_mode.toUpperCase()}</span>
        <span className="text-fire">|</span>
        <span>{capabilities.tenant_name || "TENANT"}</span>
      </div>
    </header>
  );
}
