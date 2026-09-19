import { useState } from "react";
import { changePassword, getCurrentUser, getProject, login } from "./api";
import AllEstimates from "./AllEstimates";
import AllProjects from "./AllProjects";
import AllQuotations from "./AllQuotations";
import AuditLogView from "./AuditLogView";
import ClientsAdmin from "./ClientsAdmin";
import CrossSellAdmin from "./CrossSellAdmin";
import CustomNotesPanel from "./CustomNotesPanel";
import Dashboard from "./Dashboard";
import Documents from "./Documents";
import Education from "./Education";
import Help from "./Help";
import MasterSettings from "./MasterSettings";
import PriceRequests from "./PriceRequests";
import PricingCalculator from "./PricingCalculator";
import ProjectSetup from "./ProjectSetup";
import RateSheet from "./RateSheet";
import Reports from "./Reports";
import ScopeChecklist from "./ScopeChecklist";
import SimpleCalculator from "./SimpleCalculator";
import SiteSurvey from "./SiteSurvey";
import SportSelection from "./SportSelection";
import SportsScopeAdmin from "./SportsScopeAdmin";
import TenderMode from "./TenderMode";
import VendorsAdmin from "./VendorsAdmin";

export default function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeProject, setActiveProject] = useState(null);
  const [screen, setScreen] = useState("dashboard"); // "dashboard" | "sports" | "scope" | "rates" | "pricing" | ...
  const [preNavScreen, setPreNavScreen] = useState("dashboard");
  const [navMenuOpen, setNavMenuOpen] = useState(false);
  const [openNavGroup, setOpenNavGroup] = useState(null);
  // Amendment 12 (Section 11): a Dashboard tile drill-down carries a preset
  // filter (e.g. { status: "open" }, { statusGroup: "pending" }) into
  // whichever list screen it targets.
  const [drillPreset, setDrillPreset] = useState({});

  const TOP_LEVEL_SCREENS = [
    "dashboard", "rates", "pricing", "settings", "reports", "sports_scope_admin", "clients_admin",
    "audit_log", "quotations_admin", "price_requests", "vendors_admin", "cross_sell_admin", "help",
    "projects_admin", "estimates_admin", "calculator", "education",
  ];
  const PROJECT_STAGE_SCREENS = ["sports", "scope", "site_survey", "tender", "documents"];

  function goToTopLevel(target) {
    if (!TOP_LEVEL_SCREENS.includes(screen)) {
      setPreNavScreen(screen);
    }
    setScreen(target);
    setOpenNavGroup(null);
    setNavMenuOpen(false);
  }

  function handleDrillDown(target, preset = {}) {
    setDrillPreset(preset);
    goToTopLevel(target);
  }

  function handleNewProject() {
    setActiveProject(null);
    setScreen("sports");
  }

  async function handleOpenProject(projectId) {
    try {
      const project = await getProject(accessToken, projectId);
      setActiveProject(project);
      setScreen("documents");
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await login(email, password);
      const me = await getCurrentUser(access_token);
      setAccessToken(access_token);
      setUser(me);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    setUser(null);
    setAccessToken("");
    setEmail("");
    setPassword("");
    setActiveProject(null);
    setScreen("dashboard");
    setPreNavScreen("dashboard");
    setDrillPreset({});
  }

  if (user && user.must_change_password) {
    return (
      <ForceChangePasswordScreen
        token={accessToken}
        onChanged={async () => {
          const me = await getCurrentUser(accessToken);
          setUser(me);
        }}
        onLogout={handleLogout}
      />
    );
  }

  if (user) {
    // Amendment 12 (Section 11): Director-supplied nav diagram -- Dashboard
    // / Quotation / Projects / Client / Vendor / Tools / Reports / Admin /
    // Education, replacing the old flat Daily Work / Management / Admin
    // grouping. Every item that only carries a preset filter (Pending/Old
    // Quotation, Quotation-winning projects) reuses an existing screen via
    // onDrillDown rather than inventing a new one. A group's own label is
    // never a clickable item, only the entries within it.
    const navGroups = [
      {
        key: "quotation",
        label: "Quotation",
        items: [
          { key: "new_quotation", label: "New Quotation", action: () => handleNewProject() },
          // K.3: cost/margin figures, so Pending/Old Quotation stay
          // Director-only, same gate quotations_admin already has.
          ...(user.role === "director"
            ? [
                { key: "quotation_pending", label: "Pending", action: () => handleDrillDown("quotations_admin", { statusGroup: "pending" }) },
                { key: "quotation_old", label: "Old", action: () => handleDrillDown("quotations_admin", { statusGroup: "old" }) },
              ]
            : []),
        ],
      },
      {
        key: "projects",
        label: "Projects",
        items: [
          { key: "create_cost_sheet", label: "Create Cost Sheet of Quotations", action: () => handleNewProject() },
          { key: "won_projects", label: "Quotation-winning Projects", action: () => handleDrillDown("projects_admin", { status: "won" }) },
          // Procurement statement = the existing per-project Consumption
          // Sheet (already on Documents/Cost Sheet) -- a project picker
          // first, matching the Director's own clarification that this is
          // a nav fix, not a new capability.
          { key: "procurement_statement", label: "Procurement Statement", action: () => handleDrillDown("projects_admin", {}) },
          { key: "all_projects", label: "All Projects", action: () => handleDrillDown("projects_admin", {}) },
        ],
      },
      {
        key: "client",
        label: "Client",
        items: [
          { key: "client_create", label: "Create New", action: () => goToTopLevel("clients_admin") },
          { key: "client_list", label: "List", action: () => goToTopLevel("clients_admin") },
        ],
      },
      ...(["pm", "director", "procurement"].includes(user.role)
        ? [
            {
              key: "vendor",
              label: "Vendor",
              items: [
                { key: "vendor_create", label: "Create New", action: () => goToTopLevel("vendors_admin") },
                { key: "vendor_list", label: "List", action: () => goToTopLevel("vendors_admin") },
              ],
            },
          ]
        : []),
      {
        key: "tools",
        label: "Tools",
        items: [
          // K.3 / rate_items.py READ_ROLES: PM/Director/Procurement/Site
          // Engineer only, server-side -- Sales hit a dead-end 403 on
          // these before this hid them.
          ...(user.role !== "sales" ? [{ key: "pricing", label: "Price Calculator", action: () => goToTopLevel("pricing") }] : []),
          ...(user.role !== "sales" ? [{ key: "rates", label: "Rate Sheet", action: () => goToTopLevel("rates") }] : []),
          { key: "calculator", label: "One Simple Calculator", action: () => goToTopLevel("calculator") },
          ...(user.role !== "sales" ? [{ key: "price_requests", label: "Price Requests", action: () => goToTopLevel("price_requests") }] : []),
        ],
      },
      {
        key: "reports",
        label: "Reports",
        items: [{ key: "reports", label: "All Types of Reports", action: () => goToTopLevel("reports") }],
      },
      {
        key: "admin",
        label: "Admin",
        items: [
          // Master Settings' core /settings read and Sports & Scope
          // Admin's aggregated lists are PM/Director/Procurement/Site
          // Engineer only server-side -- same dead-end-403 reasoning as
          // Tools above.
          ...(user.role !== "sales" ? [{ key: "sports_scope_admin", label: "Sports & Scope", action: () => goToTopLevel("sports_scope_admin") }] : []),
          ...(user.role !== "sales" ? [{ key: "settings", label: "Master Settings", action: () => goToTopLevel("settings") }] : []),
          ...(user.role === "director" ? [{ key: "cross_sell_admin", label: "Cross-Sell Add-ons", action: () => goToTopLevel("cross_sell_admin") }] : []),
          ...(user.role === "director" ? [{ key: "audit_log", label: "Audit Log", action: () => goToTopLevel("audit_log") }] : []),
          ...(user.role === "director" ? [{ key: "quotations_admin_all", label: "All Quotations", action: () => handleDrillDown("quotations_admin", {}) }] : []),
          { key: "help", label: "Help", action: () => goToTopLevel("help") },
        ],
      },
    ];
    const canResumeProject = activeProject && TOP_LEVEL_SCREENS.includes(screen) && screen !== "dashboard";

    return (
      <div className="min-h-screen bg-base">
        <header className="bg-surface border-b border-border-dark px-4 sm:px-8 py-4 relative print:hidden">
          {openNavGroup && (
            <div className="fixed inset-0 z-40" onClick={() => setOpenNavGroup(null)} />
          )}
          <div className="flex items-center justify-between relative z-50">
            <button
              onClick={() => goToTopLevel("dashboard")}
              className="flex items-center gap-2.5 group"
            >
              <span className="w-8 h-8 rounded bg-base border border-gold/40 flex items-center justify-center text-gold font-heading font-bold text-sm group-hover:border-gold transition-colors">
                N
              </span>
              <span className="font-heading font-bold text-text-primary tracking-tight">
                NestaPrime <span className="text-text-secondary font-normal">Estimator</span>
              </span>
            </button>
            <div className="hidden sm:flex items-center gap-4">
              <button
                onClick={() => goToTopLevel("dashboard")}
                className={`text-xs uppercase tracking-wider font-medium pb-0.5 border-b-2 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                  screen === "dashboard"
                    ? "text-text-primary border-gold"
                    : "text-text-secondary border-transparent hover:text-text-primary"
                }`}
              >
                Dashboard
              </button>
              {navGroups.map((group) => (
                <div key={group.key} className="relative border-l border-border-dark pl-4">
                  <button
                    onClick={() => setOpenNavGroup(openNavGroup === group.key ? null : group.key)}
                    className={`text-xs uppercase tracking-wider font-medium pb-0.5 border-b-2 flex items-center gap-1 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                      openNavGroup === group.key
                        ? "text-text-primary border-gold"
                        : "text-text-secondary border-transparent hover:text-text-primary"
                    }`}
                  >
                    {group.label}
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {openNavGroup === group.key && (
                    <div className="absolute top-full left-0 mt-2 bg-surface border border-border-dark rounded-lg shadow-lg py-1.5 min-w-[220px] z-50">
                      {group.items.map((item) => (
                        <button
                          key={item.key}
                          onClick={item.action}
                          className="w-full text-left text-xs text-text-secondary hover:text-text-primary hover:bg-surface-raised px-4 py-2 transition-colors duration-200"
                        >
                          {item.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              <button
                onClick={() => goToTopLevel("education")}
                className={`text-xs uppercase tracking-wider font-medium pb-0.5 border-b-2 border-l-0 hover:-translate-y-0.5 transition-all duration-250 ease-out ${
                  screen === "education"
                    ? "text-text-primary border-gold"
                    : "text-text-secondary border-transparent hover:text-text-primary"
                }`}
              >
                Education
              </button>
              {canResumeProject && (
                <button
                  onClick={() => setScreen(preNavScreen)}
                  className="text-xs uppercase tracking-wider font-medium text-gold hover:text-gold-hover border-l border-border-dark pl-5"
                >
                  ↩ Resume {activeProject.project_no}
                </button>
              )}
              <p className="text-xs text-text-secondary border-l border-border-dark pl-5">
                {user.name} · <span className="text-text-primary">{user.role}</span>
              </p>
              <button onClick={handleLogout} className="text-xs uppercase tracking-wider text-text-secondary hover:text-text-primary">
                Log out
              </button>
            </div>
            <button
              onClick={() => setNavMenuOpen(!navMenuOpen)}
              className="sm:hidden p-2 -mr-2 text-text-secondary"
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
            <div className="sm:hidden absolute inset-x-0 top-full bg-surface border-b border-border-dark shadow-lg flex flex-col z-10 max-h-[70vh] overflow-y-auto">
              <button
                onClick={() => { goToTopLevel("dashboard"); setNavMenuOpen(false); }}
                className="text-left text-sm text-text-primary px-4 py-3 border-b border-border-dark hover:bg-surface-raised w-full font-medium"
              >
                Dashboard
              </button>
              {navGroups.map((group) => (
                <div key={group.key}>
                  <p className="text-xs uppercase tracking-wide text-text-secondary/70 px-4 pt-3">{group.label}</p>
                  {group.items.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => { item.action(); setNavMenuOpen(false); }}
                      className="text-left text-sm text-text-primary px-4 py-3 border-b border-border-dark hover:bg-surface-raised w-full"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ))}
              <button
                onClick={() => { goToTopLevel("education"); setNavMenuOpen(false); }}
                className="text-left text-sm text-text-primary px-4 py-3 border-b border-border-dark hover:bg-surface-raised w-full font-medium"
              >
                Education
              </button>
              {canResumeProject && (
                <button
                  onClick={() => { setScreen(preNavScreen); setNavMenuOpen(false); }}
                  className="text-left text-sm text-gold px-4 py-3 border-b border-border-dark hover:bg-surface-raised"
                >
                  ↩ Resume {activeProject.project_no}
                </button>
              )}
              <p className="text-sm text-text-secondary px-4 py-3">
                {user.name} · <span className="text-text-primary">{user.role}</span>
              </p>
              <button
                onClick={() => { handleLogout(); setNavMenuOpen(false); }}
                className="text-left text-sm text-text-secondary px-4 py-3 hover:bg-surface-raised"
              >
                Log out
              </button>
            </div>
          )}
        </header>
        {error && (
          <p className="max-w-4xl mx-auto mt-4 px-4 text-sm text-red-400 print:hidden">{error}</p>
        )}
        {activeProject && PROJECT_STAGE_SCREENS.includes(screen) && (
          <>
            <ProjectBreadcrumb
              project={activeProject}
              screen={screen}
              onDashboard={() => setScreen("dashboard")}
              onSetup={() => setActiveProject(null)}
              onStage={(stage) => setScreen(stage)}
            />
            <CustomNotesPanel
              token={accessToken}
              project={activeProject}
              onNotesSaved={(updated) => setActiveProject(updated)}
            />
          </>
        )}
        {screen === "dashboard" && (
          <Dashboard
            token={accessToken}
            role={user.role}
            onNewProject={handleNewProject}
            onOpenProject={handleOpenProject}
            onDrillDown={handleDrillDown}
          />
        )}
        {screen === "projects_admin" && (
          <AllProjects
            token={accessToken}
            initialStatus={drillPreset.status || ""}
            onOpenProject={handleOpenProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "estimates_admin" && (
          <AllEstimates
            token={accessToken}
            initialStatus={drillPreset.status || ""}
            onOpenProject={handleOpenProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "calculator" && (
          <SimpleCalculator onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "education" && (
          <Education token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "rates" && user.role !== "sales" && (
          <RateSheet token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "pricing" && user.role !== "sales" && (
          <PricingCalculator token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "settings" && user.role !== "sales" && (
          <MasterSettings token={accessToken} currentUser={user} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "sports_scope_admin" && user.role !== "sales" && (
          <SportsScopeAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "audit_log" && user.role === "director" && (
          <AuditLogView token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "quotations_admin" && user.role === "director" && (
          <AllQuotations
            token={accessToken}
            initialStatusGroup={drillPreset.statusGroup || ""}
            onOpenProject={handleOpenProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "clients_admin" && (
          <ClientsAdmin
            token={accessToken}
            role={user.role}
            onOpenProject={handleOpenProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "price_requests" && user.role !== "sales" && (
          <PriceRequests token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "vendors_admin" && ["pm", "director", "procurement"].includes(user.role) && (
          <VendorsAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "cross_sell_admin" && user.role === "director" && (
          <CrossSellAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "reports" && (
          <Reports token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "help" && (
          <Help role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && !activeProject && (
          // Section 21: Quick mode now routes through Sport Selection too, same as
          // Detailed mode -- that's the one screen where dimension customization
          // genuinely happens (CourtSize), and skipping it was Amendment 2's real
          // gap, not a missing form field.
          <ProjectSetup
            token={accessToken}
            onProjectCreated={(project) => { setActiveProject(project); setScreen("sports"); }}
            onQuickSetupComplete={(project) => { setActiveProject(project); setScreen("sports"); }}
          />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "sports" && (
          <SportSelection
            token={accessToken}
            project={activeProject}
            role={user.role}
            onBack={() => setActiveProject(null)}
            onNext={() => setScreen("scope")}
          />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "scope" && (
          <ScopeChecklist
            token={accessToken}
            project={activeProject}
            onBack={() => setScreen("sports")}
            onNext={() => setScreen("tender")}
            onDocuments={() => setScreen("documents")}
            onSiteSurvey={() => setScreen("site_survey")}
          />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "site_survey" && (
          <SiteSurvey
            token={accessToken}
            project={activeProject}
            role={user.role}
            onBack={() => setScreen("scope")}
          />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "tender" && (
          <TenderMode
            token={accessToken}
            project={activeProject}
            onBack={() => setScreen("scope")}
          />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && activeProject && screen === "documents" && (
          <Documents
            token={accessToken}
            project={activeProject}
            role={user.role}
            onBack={() => setScreen("scope")}
          />
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-surface border border-border-dark rounded-lg p-8 max-w-sm w-full space-y-5"
      >
        <div className="flex items-center gap-2.5">
          <span className="w-9 h-9 rounded bg-base border border-gold/40 flex items-center justify-center text-gold font-heading font-bold">
            N
          </span>
          <h1 className="font-heading font-bold text-text-primary tracking-tight">
            NestaPrime <span className="text-text-secondary font-normal">Estimator</span>
          </h1>
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-text-secondary">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gold"
          />
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-text-secondary">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gold"
          />
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gold hover:bg-gold-hover text-base rounded py-2.5 font-semibold uppercase tracking-wider text-xs transition-colors duration-200 disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

// Amendment 4: guided step-path shown on every project-stage screen, plus
// the "← Dashboard" link every section is supposed to get. Site Survey and
// Tender Mode are optional side-branches reached from Scope, not their own
// step in the main line -- shown here as "current" by highlighting Scope.
function ProjectBreadcrumb({ project, screen, onDashboard, onSetup, onStage }) {
  const steps = [
    { key: "setup", label: "Setup", onClick: onSetup },
    { key: "sports", label: "Sport", onClick: () => onStage("sports") },
    { key: "scope", label: "Scope", onClick: () => onStage("scope") },
    { key: "documents", label: "Documents", onClick: () => onStage("documents") },
  ];
  const currentKey = screen === "site_survey" || screen === "tender" ? "scope" : screen;

  return (
    <div className="bg-surface border-b border-border-dark px-4 sm:px-8 py-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs uppercase tracking-wider">
      <button onClick={onDashboard} className="text-gold hover:text-gold-hover font-medium">
        Dashboard
      </button>
      <span className="text-text-secondary/50 normal-case">·</span>
      <span className="text-text-secondary normal-case font-mono">{project.project_no}</span>
      <span className="text-text-secondary/50 normal-case">·</span>
      {steps.map((step, i) => (
        <span key={step.key} className="flex items-center gap-2">
          {i > 0 && <span className="text-text-secondary/50">→</span>}
          <button
            onClick={step.onClick}
            className={
              currentKey === step.key
                ? "font-semibold text-text-primary border-b-2 border-gold"
                : "text-text-secondary hover:text-text-primary"
            }
          >
            {step.label}
          </button>
        </span>
      ))}
    </div>
  );
}

function ForceChangePasswordScreen({ token, onChanged, onLogout }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("New password and confirmation don't match");
      return;
    }
    setSubmitting(true);
    try {
      await changePassword(token, { currentPassword, newPassword });
      await onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-surface border border-border-dark rounded-lg p-6 sm:p-8 max-w-sm w-full space-y-5"
      >
        <div>
          <h1 className="font-heading font-bold text-text-primary">Change your password</h1>
          <p className="text-sm text-text-secondary mt-1">
            Your account has a Director-assigned password. Set your own before continuing.
          </p>
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-text-secondary">Current password</label>
          <input
            type="password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="mt-1.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gold"
          />
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-text-secondary">New password</label>
          <input
            type="password"
            required
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-1.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gold"
          />
        </div>

        <div>
          <label className="block text-xs uppercase tracking-wider text-text-secondary">Confirm new password</label>
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1.5 w-full rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gold"
          />
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-gold hover:bg-gold-hover text-base rounded py-2.5 font-semibold uppercase tracking-wider text-xs transition-colors duration-200 disabled:opacity-50"
        >
          {submitting ? "Changing…" : "Change password and continue"}
        </button>

        <button
          type="button"
          onClick={onLogout}
          className="w-full text-xs uppercase tracking-wider text-text-secondary hover:text-text-primary"
        >
          Log out instead
        </button>
      </form>
    </div>
  );
}
