import { useState } from "react";
import { getCurrentUser, login } from "./api";
import Documents from "./Documents";
import MasterSettings from "./MasterSettings";
import PricingCalculator from "./PricingCalculator";
import ProjectSetup from "./ProjectSetup";
import RateSheet from "./RateSheet";
import Reports from "./Reports";
import ScopeChecklist from "./ScopeChecklist";
import SportSelection from "./SportSelection";
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

  const TOP_LEVEL_SCREENS = ["rates", "pricing", "settings", "reports"];

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

  if (user) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white border-b px-8 py-4 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">NestaPrime Estimator</h1>
          <div className="flex items-center gap-4">
            <button onClick={() => goToTopLevel("pricing")} className="text-sm text-blue-600 hover:underline">
              {screen === "pricing" ? "Back to project" : "Pricing Calculator"}
            </button>
            <button onClick={() => goToTopLevel("rates")} className="text-sm text-blue-600 hover:underline">
              {screen === "rates" ? "Back to project" : "Rate Sheet"}
            </button>
            <button onClick={() => goToTopLevel("settings")} className="text-sm text-blue-600 hover:underline">
              {screen === "settings" ? "Back to project" : "Master Settings"}
            </button>
            <button onClick={() => goToTopLevel("reports")} className="text-sm text-blue-600 hover:underline">
              {screen === "reports" ? "Back to project" : "Reports"}
            </button>
            <p className="text-sm text-gray-500">
              {user.name} · <span className="font-medium">{user.role}</span>
            </p>
          </div>
        </header>
        {screen === "rates" && (
          <RateSheet token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "pricing" && (
          <PricingCalculator token={accessToken} onBack={() => setScreen(preNavScreen)} />
        )}
        {screen === "settings" && (
          <MasterSettings token={accessToken} onBack={() => setScreen(preNavScreen)} />
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
