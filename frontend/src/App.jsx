import { useState } from "react";
import { changePassword, getCurrentUser, getProject, login } from "./api";
import AllEstimates from "./AllEstimates";
import AllProjects from "./AllProjects";
import AllQuotations from "./AllQuotations";
import AuditLogView from "./AuditLogView";
import ClientsAdmin from "./ClientsAdmin";
import ComingSoon from "./ComingSoon";
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
import Sidebar from "./Sidebar";
import { BellIcon } from "./Icons";
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

  const TOP_LEVEL_SCREENS = [
    "dashboard", "rates", "pricing", "settings", "reports", "sports_scope_admin", "clients_admin",
    "audit_log", "quotations_admin", "price_requests", "vendors_admin", "cross_sell_admin", "help",
    "projects_admin", "estimates_admin", "calculator", "education",
    // Amendment 36 (Section 42): Opportunities/Follow-ups/Payments are
    // placeholder headers -- visible in the new sidebar per the CRM
    // reference, no real backend yet (Phases 4/5/7).
    "opportunities", "followups", "payments",
  ];
  const PROJECT_STAGE_SCREENS = ["sports", "scope", "site_survey", "tender", "documents"];

  function goToTopLevel(target) {
    if (!TOP_LEVEL_SCREENS.includes(screen)) {
      setPreNavScreen(screen);
    }
    setScreen(target);
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
    // Amendment 36 (Section 42): the old Director-supplied nav diagram
    // (Dashboard / Quotation / Projects / Client / Vendor / Tools / Reports
    // / Admin / Education, a top-nav dropdown group) is replaced by
    // Sidebar.jsx's own item list -- see that file for the equivalent
    // structure, now organized around the new CRM-shaped headers.
    const canResumeProject = activeProject && TOP_LEVEL_SCREENS.includes(screen) && screen !== "dashboard";

    return (
      <div className="flex min-h-screen bg-base">
        <Sidebar
          user={user}
          screen={screen}
          activeProject={activeProject}
          preNavScreen={preNavScreen}
          canResumeProject={canResumeProject}
          goToTopLevel={goToTopLevel}
          handleDrillDown={handleDrillDown}
          handleNewProject={handleNewProject}
          handleLogout={handleLogout}
          navMenuOpen={navMenuOpen}
          setNavMenuOpen={setNavMenuOpen}
        />
        <main className="flex-1 min-w-0">
        <div className="hidden sm:flex items-center justify-between gap-4 px-6 pt-4 print:hidden">
          <p className="text-xs text-text-secondary">
            {screen === "dashboard" ? "Workspace / Overview" : " "}
          </p>
          <div className="flex items-center gap-4">
          <p className="text-xs text-text-secondary text-right leading-tight">
            {new Date().toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase()}
          </p>
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
        {screen === "opportunities" && (
          <ComingSoon
            title="Opportunities"
            description="Pipeline-stage tracking for pre-project enquiries -- lands in a later phase of the CRM restructure."
            onBack={() => setScreen("dashboard")}
          />
        )}
        {screen === "followups" && (
          <ComingSoon
            title="Follow-ups"
            description="Due/overdue client follow-up reminders -- lands in a later phase of the CRM restructure."
            onBack={() => setScreen("dashboard")}
          />
        )}
        {screen === "payments" && (
          <ComingSoon
            title="Payments"
            description="Forward-looking payment due-dates and overdue tracking -- lands in a later phase of the CRM restructure."
            onBack={() => setScreen("dashboard")}
          />
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
