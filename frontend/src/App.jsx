import { useState } from "react";
import { changePassword, getCurrentUser, getProject, login } from "./api";
import AuditLogView from "./AuditLogView";
import ClientsAdmin from "./ClientsAdmin";
import Dashboard from "./Dashboard";
import Documents from "./Documents";
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

  const TOP_LEVEL_SCREENS = ["dashboard", "rates", "pricing", "settings", "reports", "sports_scope_admin", "clients_admin", "audit_log", "price_requests"];
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
          { key: "pricing", label: "Pricing Calculator" },
          { key: "rates", label: "Rate Sheet" },
        ],
      },
      {
        label: "Management",
        items: [
          { key: "clients_admin", label: "Clients" },
          { key: "reports", label: "Reports" },
          ...(user.role !== "sales" ? [{ key: "price_requests", label: "Price Requests" }] : []),
        ],
      },
      {
        label: "Admin",
        items: [
          { key: "settings", label: "Master Settings" },
          { key: "sports_scope_admin", label: "Sports & Scope Admin" },
          ...(user.role === "director" ? [{ key: "audit_log", label: "Audit Log" }] : []),
        ],
      },
    ];
    const canResumeProject = activeProject && TOP_LEVEL_SCREENS.includes(screen) && screen !== "dashboard";

    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-4 sm:px-8 py-4 relative">
          <div className="flex items-center justify-between">
            <button
              onClick={() => goToTopLevel("dashboard")}
              className="text-lg font-semibold text-gray-900 hover:text-blue-600"
            >
              NestaPrime Estimator
            </button>
            <div className="hidden sm:flex items-center gap-5">
              {navGroups.map((group, i) => (
                <div key={group.label} className={`flex items-center gap-4 ${i > 0 ? "border-l pl-5" : ""}`}>
                  {group.items.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => goToTopLevel(item.key)}
                      className={`text-sm hover:underline ${
                        screen === item.key ? "text-gray-900 font-medium" : "text-blue-600"
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
                  className="text-sm text-blue-600 hover:underline border-l pl-5"
                >
                  ↩ Resume {activeProject.project_no}
                </button>
              )}
              <p className="text-sm text-gray-500 border-l pl-5">
                {user.name} · <span className="font-medium">{user.role}</span>
              </p>
              <button onClick={handleLogout} className="text-sm text-gray-500 hover:underline">
                Log out
              </button>
            </div>
            <button
              onClick={() => setNavMenuOpen(!navMenuOpen)}
              className="sm:hidden p-2 -mr-2 text-gray-600"
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
            <div className="sm:hidden absolute inset-x-0 top-full bg-white border-b shadow-lg flex flex-col z-10">
              {navGroups.map((group) => (
                <div key={group.label}>
                  <p className="text-xs uppercase tracking-wide text-gray-400 px-4 pt-3">{group.label}</p>
                  {group.items.map((item) => (
                    <button
                      key={item.key}
                      onClick={() => { goToTopLevel(item.key); setNavMenuOpen(false); }}
                      className="text-left text-sm text-blue-600 px-4 py-3 border-b hover:bg-gray-50 w-full"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              ))}
              {canResumeProject && (
                <button
                  onClick={() => { setScreen(preNavScreen); setNavMenuOpen(false); }}
                  className="text-left text-sm text-blue-600 px-4 py-3 border-b hover:bg-gray-50"
                >
                  ↩ Resume {activeProject.project_no}
                </button>
              )}
              <p className="text-sm text-gray-500 px-4 py-3">
                {user.name} · <span className="font-medium">{user.role}</span>
              </p>
              <button
                onClick={() => { handleLogout(); setNavMenuOpen(false); }}
                className="text-left text-sm text-gray-500 px-4 py-3 hover:bg-gray-50"
              >
                Log out
              </button>
            </div>
          )}
        </header>
        {error && (
          <p className="max-w-4xl mx-auto mt-4 px-4 text-sm text-red-600">{error}</p>
        )}
        {activeProject && PROJECT_STAGE_SCREENS.includes(screen) && (
          <ProjectBreadcrumb
            project={activeProject}
            screen={screen}
            onDashboard={() => setScreen("dashboard")}
            onSetup={() => setActiveProject(null)}
            onStage={(stage) => setScreen(stage)}
          />
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
        {screen === "pricing" && (
          <PricingCalculator token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "settings" && (
          <MasterSettings token={accessToken} currentUser={user} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "sports_scope_admin" && (
          <SportsScopeAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "audit_log" && user.role === "director" && (
          <AuditLogView token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "clients_admin" && (
          <ClientsAdmin token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "price_requests" && user.role !== "sales" && (
          <PriceRequests token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "reports" && (
          <Reports token={accessToken} role={user.role} onBack={() => setScreen(preNavScreen)} />
        )}
        {!TOP_LEVEL_SCREENS.includes(screen) && !activeProject && (
          <ProjectSetup
            token={accessToken}
            onProjectCreated={(project) => { setActiveProject(project); setScreen("sports"); }}
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form
        onSubmit={handleSubmit}
        className="bg-white shadow rounded-lg p-8 max-w-sm w-full space-y-4"
      >
        <h1 className="text-xl font-semibold text-gray-900">NestaPrime Estimator</h1>

        <div>
          <label className="block text-sm font-medium text-gray-700">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white rounded py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
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
    <div className="bg-blue-50 border-b border-blue-100 px-4 sm:px-8 py-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <button onClick={onDashboard} className="text-blue-600 hover:underline font-medium">
        🏠 Dashboard
      </button>
      <span className="text-gray-400">·</span>
      <span className="text-gray-500">{project.project_no}</span>
      <span className="text-gray-400">·</span>
      {steps.map((step, i) => (
        <span key={step.key} className="flex items-center gap-2">
          {i > 0 && <span className="text-gray-400">→</span>}
          <button
            onClick={step.onClick}
            className={
              currentKey === step.key
                ? "font-semibold text-gray-900"
                : "text-blue-600 hover:underline"
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white shadow rounded-lg p-6 sm:p-8 max-w-sm w-full space-y-4"
      >
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Change your password</h1>
          <p className="text-sm text-gray-500 mt-1">
            Your account has a Director-assigned password. Set your own before continuing.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Current password</label>
          <input
            type="password"
            required
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">New password</label>
          <input
            type="password"
            required
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Confirm new password</label>
          <input
            type="password"
            required
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-600 text-white rounded py-2 font-medium hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? "Changing…" : "Change password and continue"}
        </button>

        <button
          type="button"
          onClick={onLogout}
          className="w-full text-sm text-gray-500 hover:underline"
        >
          Log out instead
        </button>
      </form>
    </div>
  );
}
