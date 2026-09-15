import { useState } from "react";
import { changePassword, getCurrentUser, getProject, login } from "./api";
import AllQuotations from "./AllQuotations";
import AuditLogView from "./AuditLogView";
import ClientsAdmin from "./ClientsAdmin";
import CrossSellAdmin from "./CrossSellAdmin";
import CustomNotesPanel from "./CustomNotesPanel";
import Dashboard from "./Dashboard";
import Documents from "./Documents";
import Help from "./Help";
import MasterSettings from "./MasterSettings";
import PriceRequests from "./PriceRequests";
import PricingCalculator from "./PricingCalculator";
import ProjectSetup from "./ProjectSetup";
import RateSheet from "./RateSheet";
import Reports from "./Reports";
import ScopeChecklist from "./ScopeChecklist";
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

  const TOP_LEVEL_SCREENS = ["dashboard", "rates", "pricing", "settings", "reports", "sports_scope_admin", "clients_admin", "audit_log", "quotations_admin", "price_requests", "vendors_admin", "cross_sell_admin", "help"];
  const PROJECT_STAGE_SCREENS = ["sports", "scope", "site_survey", "tender", "documents"];

  function goToTopLevel(target) {
    if (!TOP_LEVEL_SCREENS.includes(screen)) {
      setPreNavScreen(screen);
    }
    setScreen(target);
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
    // Amendment 4: nav regrouped Daily Work / Management / Admin, "the app
    // itself is the training." A group's own label is never a clickable
    // item, only the entries within it.
    const navGroups = [
      {
        label: "Daily Work",
        items: [
          { key: "dashboard", label: "Dashboard" },
          // K.3: /pricing/quote is PM/Director only server-side -- Sales
          // saw this nav item and hit a dead-end 403 before this hid it.
          ...(user.role !== "sales" ? [{ key: "pricing", label: "Pricing Calculator" }] : []),
          { key: "rates", label: "Rate Sheet" },
          { key: "help", label: "Help" },
        ],
      },
      {
        label: "Management",
        items: [
          { key: "clients_admin", label: "Clients" },
          { key: "reports", label: "Reports" },
          ...(user.role !== "sales" ? [{ key: "price_requests", label: "Price Requests" }] : []),
          // Amendment 7: M.4 -- Sales/Site Engineer/CA have no reason to
          // see vendor relationships or pricing, matching PROCUREMENT_ROLES
          // server-side (backend/app/api/vendors.py).
          ...(["pm", "director", "procurement"].includes(user.role)
            ? [{ key: "vendors_admin", label: "Vendors" }]
            : []),
        ],
      },
      {
        label: "Admin",
        items: [
          // Master Settings' core /settings read is PM/Director only
          // server-side (backend/app/api/settings.py READ_ROLES); Sales
          // saw this nav item, and the K.1 percentage list silently 403'd
          // and just never appeared -- same dead-end pattern Pricing
          // Calculator already had fixed above.
          ...(user.role !== "sales" ? [{ key: "settings", label: "Master Settings" }] : []),
          // Sports & Scope Admin aggregates several master-data lists;
          // Netting grades / Vehicle classes specifically exclude Sales
          // server-side (backend/app/api/structures.py,
          // overheads.py NETTING_CATALOG_READ_ROLES /
          // VEHICLE_CLASS_READ_ROLES -- PM/Director/Procurement/Site
          // Engineer only), so Sales got every list on the page failing
          // with "Role 'sales' is not permitted" instead of the working
          // sport/scope-item dropdowns those same roles use elsewhere.
          ...(user.role !== "sales" ? [{ key: "sports_scope_admin", label: "Sports & Scope Admin" }] : []),
          ...(user.role === "director" ? [{ key: "cross_sell_admin", label: "Cross-Sell Add-ons" }] : []),
          ...(user.role === "director" ? [{ key: "audit_log", label: "Audit Log" }] : []),
          // Amendment 6b (Section 9): "admin reviews all quotations" --
          // same Director-only gate as Audit Log (K.3 restricts the
          // cost/margin figures this screen shows to PM/Director; this
          // is the stricter Director-only tier, matching Margin
          // Performance's own gate for the same figures).
          ...(user.role === "director" ? [{ key: "quotations_admin", label: "All Quotations" }] : []),
        ],
      },
    ];
    const canResumeProject = activeProject && TOP_LEVEL_SCREENS.includes(screen) && screen !== "dashboard";

    return (
      <div className="min-h-screen bg-base">
        <header className="bg-surface border-b border-border-dark px-4 sm:px-8 py-4 relative print:hidden">
          <div className="flex items-center justify-between">
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
            <div className="hidden sm:flex items-center gap-5">
              {navGroups.map((group, i) => (
                <div key={group.label} className={`flex items-center gap-4 ${i > 0 ? "border-l border-border-dark pl-5" : ""}`}>
                  {group.items.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => goToTopLevel(item.key)}
                      className={`text-xs uppercase tracking-wider font-medium pb-0.5 border-b-2 transition-colors duration-200 ${
                        screen === item.key
                          ? "text-text-primary border-gold"
                          : "text-text-secondary border-transparent hover:text-text-primary"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ))}
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
            <div className="sm:hidden absolute inset-x-0 top-full bg-surface border-b border-border-dark shadow-lg flex flex-col z-10">
              {navGroups.map((group) => (
                <div key={group.label}>
                  <p className="text-xs uppercase tracking-wide text-text-secondary/70 px-4 pt-3">{group.label}</p>
                  {group.items.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => { goToTopLevel(item.key); setNavMenuOpen(false); }}
                      className="text-left text-sm text-text-primary px-4 py-3 border-b border-border-dark hover:bg-surface-raised w-full"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ))}
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
          />
        )}
        {screen === "rates" && (
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
            onOpenProject={handleOpenProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "clients_admin" && (
          <ClientsAdmin token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} />
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
          <ProjectSetup
            token={accessToken}
            onProjectCreated={(project) => { setActiveProject(project); setScreen("sports"); }}
            onQuickSetupComplete={(project) => { setActiveProject(project); setScreen("scope"); }}
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
