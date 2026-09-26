import { useEffect, useState } from "react";
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
import FollowUps from "./FollowUps";
import Help from "./Help";
import MasterSettings from "./MasterSettings";
import Opportunities from "./Opportunities";
import Payments from "./Payments";
import PriceRequests from "./PriceRequests";
import PricingCalculator from "./PricingCalculator";
import ProjectSetup from "./ProjectSetup";
import QuickSearch from "./QuickSearch";
import RateSheet from "./RateSheet";
import Reports from "./Reports";
import ScopeChecklist from "./ScopeChecklist";
import Sidebar from "./Sidebar";
import TeamAccess from "./TeamAccess";
import { BellIcon } from "./Icons";
import { canOpen } from "./navAccess";
import LiveClock from "./LiveClock";
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
  // Amendment 12 (Section 11): a Dashboard tile drill-down carries a preset
  // filter (e.g. { status: "open" }, { statusGroup: "pending" }) into
  // whichever list screen it targets.
  const [drillPreset, setDrillPreset] = useState({});
  // Amendment 44 Phase C: set by "Start Project" on a Won Opportunity, read
  // by ProjectSetup, cleared as soon as any other path starts a project.
  const [startFrom, setStartFrom] = useState(null);
  // Amendment 53: the global quick search palette, and the text a client/lead result
  // pre-fills into Leads & Clients (`nonce` remounts it even when already open).
  const [searchOpen, setSearchOpen] = useState(false);
  const [clientsSearch, setClientsSearch] = useState({ text: "", nonce: 0 });

  useEffect(() => {
    if (!user) return undefined;
    function onKeyDown(e) {
      const t = e.target;
      const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      } else if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setSearchOpen(true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [user]);

  const TOP_LEVEL_SCREENS = [
    "dashboard", "rates", "pricing", "settings", "reports", "sports_scope_admin", "clients_admin",
    "audit_log", "quotations_admin", "price_requests", "vendors_admin", "cross_sell_admin", "help",
    "projects_admin", "estimates_admin", "calculator", "education",
    // Follow-ups got its real screen in Amendment 43; Opportunities got its
    // own in Amendment 44; Payments in Amendment 50 (was a placeholder).
    "opportunities", "followups", "payments",
    // Amendment 51: the real Team & Access screen (was Master Settings).
    "team_access",
  ];
  const PROJECT_STAGE_SCREENS = ["sports", "scope", "site_survey", "tender", "documents"];

  function goToTopLevel(target) {
    if (!TOP_LEVEL_SCREENS.includes(screen)) {
      setPreNavScreen(screen);
    }
    // A search-prefilled Leads & Clients filter belongs to that one visit.
    if (target !== "clients_admin") setClientsSearch((c) => (c.text ? { text: "", nonce: c.nonce + 1 } : c));
    setScreen(target);
    setNavMenuOpen(false);
  }

  // Amendment 53: open a quick-search result. A project or quotation opens that
  // project; a client or lead opens Leads & Clients with its exact name in the
  // search box (there is no per-record view or deep link).
  function handleOpenSearchResult(item) {
    setSearchOpen(false);
    if (item.project_id) {
      handleOpenProject(item.project_id);
    } else {
      setClientsSearch((c) => ({ text: item.primary, nonce: c.nonce + 1 }));
      goToTopLevel("clients_admin");
    }
  }

  function handleDrillDown(target, preset = {}) {
    setDrillPreset(preset);
    goToTopLevel(target);
  }

  function handleNewProject() {
    setStartFrom(null);
    setActiveProject(null);
    setScreen("sports");
  }

  function handleStartProject(hand_off) {
    setStartFrom(hand_off);
    setActiveProject(null);
    setScreen("sports");
  }

  async function handleOpenProject(projectId) {
    setClientsSearch((c) => (c.text ? { text: "", nonce: c.nonce + 1 } : c));
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
    setStartFrom(null);
    setScreen("dashboard");
    setPreNavScreen("dashboard");
    setDrillPreset({});
  }

  if (user && user.must_change_password) {
    return (
      <ForceChangePasswordScreen
        token={accessToken}
        onChanged={async (newToken) => {
          const activeToken = newToken || accessToken;
          setAccessToken(activeToken);
          const me = await getCurrentUser(activeToken);
          setUser(me);
        }}
        onLogout={handleLogout}
      />
    );
  }

  if (user) {
    // Amendment 36 (Section 42): the old Director-supplied nav diagram
    // (Dashboard / Quotation / Projects / Client / Vendor / Tools / Reports
    // / Admin / Education, a top-nav dropdown group) is replaced by
    // Sidebar.jsx's own item list -- see that file for the equivalent
    // structure, now organized around the new CRM-shaped headers.
    const canResumeProject = activeProject && TOP_LEVEL_SCREENS.includes(screen) && screen !== "dashboard";

    return (
      <div className="flex flex-col sm:flex-row min-h-screen bg-base">
        <Sidebar
          user={user}
          screen={screen}
          activeProject={activeProject}
          preNavScreen={preNavScreen}
          canResumeProject={canResumeProject}
          goToTopLevel={goToTopLevel}
          handleDrillDown={handleDrillDown}
          handleLogout={handleLogout}
          navMenuOpen={navMenuOpen}
          setNavMenuOpen={setNavMenuOpen}
          onOpenSearch={() => setSearchOpen(true)}
        />
        {searchOpen && (
          <QuickSearch token={accessToken} onClose={() => setSearchOpen(false)} onOpenResult={handleOpenSearchResult} />
        )}
        <main className="flex-1 min-w-0">
        <div className="hidden sm:flex items-center justify-between gap-4 px-6 pt-4 print:hidden">
          <p className="text-xs text-text-secondary">
            {screen === "dashboard" ? "Workspace / Overview" : " "}
          </p>
          <div className="flex items-center gap-4">
          <LiveClock name={user.name} />
          <span title="No live notifications yet" className="text-text-secondary/60">
            <BellIcon className="w-4 h-4" />
          </span>
          <span className="w-7 h-7 rounded-full bg-surface-raised border border-border-dark flex items-center justify-center text-text-primary font-heading font-bold text-[11px]">
            {user.name
              .split(" ")
              .map((n) => n[0])
              .join("")
              .slice(0, 2)
              .toUpperCase()}
          </span>
          </div>
        </div>
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
        {screen === "rates" && canOpen("rates", user.role) && (
          <RateSheet token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "pricing" && canOpen("pricing", user.role) && (
          <PricingCalculator token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "settings" && canOpen("settings", user.role) && (
          <MasterSettings token={accessToken} currentUser={user} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "team_access" && canOpen("team_access", user.role) && (
          <TeamAccess token={accessToken} currentUser={user} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "sports_scope_admin" && canOpen("sports_scope_admin", user.role) && (
          <SportsScopeAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "audit_log" && user.role === "director" && (
          <AuditLogView token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "quotations_admin" && ["sales", "pm", "director"].includes(user.role) && (
          <AllQuotations
            token={accessToken}
            role={user.role}
            initialStatusGroup={drillPreset.statusGroup || ""}
            onOpenProject={handleOpenProject}
            onOpenOpportunities={() => goToTopLevel("opportunities")}
            onNewProject={handleNewProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "clients_admin" && (
          <ClientsAdmin
            key={clientsSearch.nonce}
            initialSearch={clientsSearch.text}
            token={accessToken}
            role={user.role}
            onOpenProject={handleOpenProject}
            onOpenOpportunities={() => goToTopLevel("opportunities")}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {screen === "price_requests" && canOpen("price_requests", user.role) && (
          <PriceRequests token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "vendors_admin" && canOpen("vendors_admin", user.role) && (
          <VendorsAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "cross_sell_admin" && user.role === "director" && (
          <CrossSellAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "reports" && canOpen("reports", user.role) && (
          <Reports token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "help" && (
          <Help role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "opportunities" && (
          <Opportunities token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} onStartProject={handleStartProject} />
        )}
        {screen === "followups" && (
          <FollowUps token={accessToken} userId={user.id} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "payments" && ["pm", "director", "ca_tax"].includes(user.role) && (
          <Payments
            token={accessToken}
            role={user.role}
            initialFilter={drillPreset.filter || ""}
            onOpenProject={handleOpenProject}
            onBack={() => setScreen(preNavScreen)}
          />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && !activeProject && (
          // Section 21: Quick mode now routes through Sport Selection too, same as
          // Detailed mode -- that's the one screen where dimension customization
          // genuinely happens (CourtSize), and skipping it was Amendment 2's real
          // gap, not a missing form field.
          <ProjectSetup
            token={accessToken}
            startFrom={startFrom}
            onProjectCreated={(project) => { setStartFrom(null); setActiveProject(project); setScreen("sports"); }}
            onQuickSetupComplete={(project) => { setStartFrom(null); setActiveProject(project); setScreen("sports"); }}
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
            onNext={() => setScreen("documents")}
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
            onOpenPayments={() => goToTopLevel("payments")}
            onBack={() => setScreen("scope")}
          />
        )}
        </main>
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
            NestaPrime <span className="text-text-secondary font-normal">CRM</span>
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
      const changed = await changePassword(token, { currentPassword, newPassword });
      // Amendment 58: changing the password ends the old session, so the reply carries a fresh token.
      await onChanged(changed.access_token);
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
          <label className="block text-xs uppercase tracking-wider text-text-secondary">New password (at least 10 characters)</label>
          <input
            type="password"
            required
            minLength={10}
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
            minLength={10}
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
