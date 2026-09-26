import { useState } from "react";
import {
  CalendarIcon,
  ClockIcon,
  DocumentIcon,
  FolderIcon,
  FunnelIcon,
  GridIcon,
  SearchIcon,
  UsersIcon,
} from "./Icons";
import { canOpen } from "./navAccess";

// Amendment 36 (Section 42): Phase 1 of the header-by-header CRM restructure
// -- replaces the old top-nav dropdowns with a left sidebar. Confirmed
// headers (Overview/Leads & Clients/Quotations/Projects/Team & Access) route
// to their existing, already-working screens, unchanged. Follow-ups got its
// real screen in Amendment 43; Opportunities got its own in Amendment 44;
// Payments in Amendment 50.
//
// Amendment 52 (Section 56): the screens that never got a header of their own
// live under "More", now as two always-open sections instead of five accordion
// groups (Vendor joins the tools; Reports is a plain item), and Help and
// Education -- which every role can use -- moved out of it to the sidebar
// footer. "All Quotations" is gone from Admin: it opened the same screen as the
// Quotations header. Each item is shown only to the roles navAccess.js lists for
// it (Amendment 51's rule); a section with nothing left to show is not listed.
const MORE_SECTIONS = [
  {
    key: "tools",
    label: "Tools & reports",
    items: [
      { key: "reports", label: "Reports" },
      { key: "rates", label: "Rate Sheet" },
      { key: "pricing", label: "Price Calculator" },
      { key: "price_requests", label: "Price Requests" },
      { key: "vendors_admin", label: "Vendor Master" },
      { key: "calculator", label: "One Simple Calculator" },
    ],
  },
  {
    key: "admin",
    label: "Admin",
    items: [
      { key: "sports_scope_admin", label: "Sports & Scope" },
      { key: "settings", label: "Master Settings" },
      { key: "cross_sell_admin", label: "Cross-Sell Add-ons", show: (role) => role === "director" },
      { key: "audit_log", label: "Audit Log" },
    ],
  },
];

// Open to every role, so not under More or Admin (Amendment 52).
const FOOTER_LINKS = [
  { key: "help", label: "Help" },
  { key: "education", label: "Education" },
];

// Amendment 59: an Admin has no business records -- no search, no Projects, no Education chat.
function footerLinksFor(role) {
  return FOOTER_LINKS.filter((link) => !(role === "admin" && link.key === "education"));
}

function visibleItems(section, role) {
  return section.items.filter((it) => canOpen(it.key, role) && (!it.show || it.show(role)));
}

function NavLink({ label, active, onClick, badge, muted, icon: IconComp }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left text-sm px-4 py-2.5 rounded flex items-center justify-between transition-colors duration-200 ${
        active
          ? "bg-gold-muted text-gold font-medium"
          : muted
          ? "text-text-secondary/60 hover:text-text-secondary hover:bg-surface-raised"
          : "text-text-secondary hover:text-text-primary hover:bg-surface-raised"
      }`}
    >
      <span className="flex items-center gap-2.5">
        {IconComp && <IconComp className="w-4 h-4 shrink-0" />}
        {label}
      </span>
      {badge !== undefined && (
        <span className="text-[10px] uppercase tracking-wider bg-surface-raised border border-border-dark rounded px-1.5 py-0.5">
          {badge}
        </span>
      )}
    </button>
  );
}

export default function Sidebar({
  user,
  screen,
  activeProject,
  preNavScreen,
  canResumeProject,
  goToTopLevel,
  handleDrillDown,
  handleLogout,
  navMenuOpen,
  setNavMenuOpen,
  onOpenSearch,
}) {
  const [moreOpen, setMoreOpen] = useState(false);
  const isAdmin = user.role === "admin";

  // Amendment 51: Team & Access is user management and the role/permission
  // view, no longer Master Settings. Amendment 59: Admin and Director use both;
  // a PM sees the People tab only (the screen decides).
  const showTeamAccess = canOpen("team_access", user.role);

  function go(target) {
    goToTopLevel(target);
    setNavMenuOpen(false);
  }

  // Amendment 53: the global quick search. Closes the phone menu first so the
  // palette is not stacked on top of it.
  function openSearch() {
    setNavMenuOpen(false);
    onOpenSearch();
  }

  // Amendment 49 (Section 53): this opens the Quotations list for every role
  // that can use it. It used to start a new project for everyone but the
  // Director -- "+ New project" now lives on that screen and on the Overview.
  function onQuotationsClick() {
    handleDrillDown("quotations_admin", {});
    setNavMenuOpen(false);
  }
  const canSeeQuotations = ["sales", "pm", "director"].includes(user.role);
  const canSeePayments = ["pm", "director", "ca_tax"].includes(user.role);

  // Amendment 46: GET /clients and /opportunities are gated to these four
  // roles; site_engineer/ca_tax got a nav item that could only ever show a
  // permission error, so they no longer see it (same idea as Team & Access
  // being hidden from Sales).
  const canSeeRelationships = ["sales", "pm", "director", "procurement"].includes(user.role);

  const primaryItems = [
    { key: "dashboard", label: "Overview", onClick: () => go("dashboard"), icon: GridIcon },
    ...(canSeeRelationships
      ? [
          { key: "clients_admin", label: "Leads & Clients", onClick: () => go("clients_admin"), icon: UsersIcon },
          { key: "opportunities", label: "Opportunities", onClick: () => go("opportunities"), icon: FunnelIcon },
        ]
      : []),
    ...(canSeeQuotations
      ? [{ key: "__quotations", label: "Quotations", onClick: onQuotationsClick, matchKeys: ["quotations_admin"], icon: DocumentIcon }]
      : []),
    ...(isAdmin
      ? []
      : [{ key: "projects_admin", label: "Projects", onClick: () => go("projects_admin"), icon: FolderIcon }]),
    // Amendment 50 (Section 54): a real header now, shown only to the roles
    // that can open it (PM/Director write, CA/Tax reads) -- as Amendment 46
    // did for Leads & Clients, so nobody gets an item that can only refuse them.
    ...(canSeePayments
      ? [{ key: "payments", label: "Payments", onClick: () => go("payments"), icon: CalendarIcon }]
      : []),
    ...(canSeeRelationships
      ? [{ key: "followups", label: "Follow-ups", onClick: () => go("followups"), icon: ClockIcon }]
      : []),
    ...(showTeamAccess ? [{ key: "team_access", label: "Team & Access", onClick: () => go("team_access"), icon: UsersIcon }] : []),
  ];

  const sidebarBody = (
    <div className="flex flex-col h-full">
      <button onClick={() => go("dashboard")} className="flex items-center gap-2.5 px-4 pt-5 pb-1 group text-left">
        <span className="w-8 h-8 rounded bg-base border border-gold/40 flex items-center justify-center text-gold font-heading font-bold text-sm group-hover:border-gold transition-colors">
          N
        </span>
        <span className="leading-tight">
          <span className="font-heading font-bold text-text-primary tracking-tight block">NestaPrime</span>
          <span className="text-[9px] uppercase tracking-wider text-text-secondary/70">Relationships &middot; Projects &middot; Growth</span>
        </span>
      </button>

      <div className="px-4 pt-4 pb-2">
        <p className="text-[10px] uppercase tracking-wider text-text-secondary/60 mb-2">Your workspace</p>
        <div className="bg-surface-raised border border-border-dark rounded-lg px-3 py-2.5 flex items-center gap-2.5">
          <span className="w-7 h-7 rounded bg-base border border-border-dark flex items-center justify-center text-text-secondary font-heading font-bold text-[11px] shrink-0">
            NP
          </span>
          <span className="leading-tight min-w-0">
            <span className="block text-xs font-medium text-text-primary truncate">Nesta Prime Solutions</span>
            <span className="block text-[10px] text-text-secondary truncate">Sports infrastructure &middot; India</span>
          </span>
        </div>
      </div>

      {!isAdmin && (
      <div className="px-4 pb-1">
        <button
          onClick={openSearch}
          className="w-full flex items-center gap-2.5 rounded border border-border-dark bg-surface-raised px-3 py-2 text-sm text-text-secondary hover:text-text-primary hover:border-gold/40 transition-colors"
          aria-label="Search clients, leads, projects and quotations"
        >
          <SearchIcon className="w-4 h-4 shrink-0" />
          <span className="flex-1 text-left">Search</span>
          <kbd className="hidden sm:inline text-[10px] rounded border border-border-dark px-1.5 py-0.5 text-text-secondary/70">/</kbd>
        </button>
      </div>
      )}

      <nav className="flex-1 overflow-y-auto px-2 space-y-1 pt-1">
        {primaryItems.map((item) => (
          <NavLink
            key={item.key}
            label={item.label}
            badge={item.badge}
            muted={item.muted}
            icon={item.icon}
            active={screen === item.key || (item.matchKeys || []).includes(screen)}
            onClick={item.onClick}
          />
        ))}

        <div className="pt-2 mt-2 border-t border-border-dark">
          <NavLink
            label="More"
            active={moreOpen}
            onClick={() => setMoreOpen((v) => !v)}
          />
          {moreOpen && (
            <div className="pl-2 space-y-2 mt-1">
              {MORE_SECTIONS.filter((sec) => visibleItems(sec, user.role).length > 0).map((section) => (
                <div key={section.key}>
                  <p className="text-xs uppercase tracking-wide text-text-secondary/70 px-3 py-1.5">{section.label}</p>
                  <div className="pl-3 space-y-0.5">
                    {visibleItems(section, user.role).map((it) => (
                      <NavLink key={it.key} label={it.label} active={screen === it.key} onClick={() => go(it.key)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </nav>

      <div className="border-t border-border-dark px-2 pt-2 space-y-0.5">
        {footerLinksFor(user.role).map((link) => (
          <NavLink key={link.key} label={link.label} active={screen === link.key} onClick={() => go(link.key)} />
        ))}
      </div>

      <div className="border-t border-border-dark px-4 py-3 space-y-2">
        {canResumeProject && (
          <button
            onClick={() => go(preNavScreen)}
            className="w-full text-left text-xs uppercase tracking-wider font-medium text-gold hover:text-gold-hover"
          >
            ↩ Resume {activeProject.project_no}
          </button>
        )}
        <p className="text-xs text-text-secondary">
          {user.name} · <span className="text-text-primary">{user.role}</span>
        </p>
        <button
          onClick={handleLogout}
          className="text-xs uppercase tracking-wider text-text-secondary hover:text-text-primary"
        >
          Log out
        </button>
      </div>
    </div>
  );

  return (
    <>
      <aside className="hidden sm:flex sm:flex-col w-64 shrink-0 bg-surface border-r border-border-dark min-h-screen print:hidden">
        {sidebarBody}
      </aside>

      <div className="sm:hidden flex items-center justify-between bg-surface border-b border-border-dark px-4 py-3 print:hidden">
        <button onClick={() => go("dashboard")} className="flex items-center gap-2 group">
          <span className="w-7 h-7 rounded bg-base border border-gold/40 flex items-center justify-center text-gold font-heading font-bold text-xs">
            N
          </span>
          <span className="font-heading font-bold text-text-primary text-sm">NestaPrime</span>
        </button>
        {!isAdmin && (
          <button onClick={openSearch} className="p-2 ml-auto mr-1 text-text-secondary" aria-label="Search">
            <SearchIcon className="w-5 h-5" />
          </button>
        )}
        <button
          onClick={() => setNavMenuOpen(!navMenuOpen)}
          className="p-2 -mr-2 text-text-secondary"
          aria-label="Toggle navigation menu"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            {navMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>
      {navMenuOpen && (
        <div className="sm:hidden fixed inset-0 z-40 bg-base overflow-y-auto print:hidden">{sidebarBody}</div>
      )}
    </>
  );
}
