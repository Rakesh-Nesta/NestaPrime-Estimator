import { useState } from "react";
import { changePassword, getCurrentUser, login } from "./api";
import AuditLogView from "./AuditLogView";
import ClientsAdmin from "./ClientsAdmin";
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
  const [screen, setScreen] = useState("sports"); // "sports" | "scope" | "rates" | "pricing"
  const [preNavScreen, setPreNavScreen] = useState("sports");
  const [navMenuOpen, setNavMenuOpen] = useState(false);

  const TOP_LEVEL_SCREENS = ["rates", "pricing", "settings", "reports", "sports_scope_admin", "clients_admin", "audit_log", "price_requests"];

  function goToTopLevel(target) {
    if (TOP_LEVEL_SCREENS.includes(screen)) {
      setScreen(screen === target ? preNavScreen : target);
    } else {
      setPreNavScreen(screen);
      setScreen(target);
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
    const navItems = [
      { key: "pricing", label: "Pricing Calculator" },
      { key: "rates", label: "Rate Sheet" },
      { key: "settings", label: "Master Settings" },
      { key: "sports_scope_admin", label: "Sports & Scope Admin" },
      { key: "clients_admin", label: "Clients" },
      { key: "reports", label: "Reports" },
      ...(user.role === "director" ? [{ key: "audit_log", label: "Audit Log" }] : []),
      ...(user.role !== "sales" ? [{ key: "price_requests", label: "Price Requests" }] : []),
    ];

    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-4 sm:px-8 py-4 relative">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold text-gray-900">NestaPrime Estimator</h1>
            <div className="hidden sm:flex items-center gap-4">
              {navItems.map((item) => (
                <button
                  key={item.key}
                  onClick={() => goToTopLevel(item.key)}
                  className="text-sm text-blue-600 hover:underline"
                >
                  {screen === item.key ? "Back to project" : item.label}
                </button>
              ))}
              <p className="text-sm text-gray-500">
                {user.name} · <span className="font-medium">{user.role}</span>
              </p>
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
              {navItems.map((item) => (
                <button
                  key={item.key}
                  onClick={() => { goToTopLevel(item.key); setNavMenuOpen(false); }}
                  className="text-left text-sm text-blue-600 px-4 py-3 border-b hover:bg-gray-50"
                >
                  {screen === item.key ? "Back to project" : item.label}
                </button>
              ))}
              <p className="text-sm text-gray-500 px-4 py-3">
                {user.name} · <span className="font-medium">{user.role}</span>
              </p>
            </div>
          )}
        </header>
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
