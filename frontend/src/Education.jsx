import { useMemo, useState } from "react";
import { askEducationAssistant } from "./api";
import { DIRECTOR_ADMIN_GUIDE, ESTIMATOR_GUIDE, FAQ, FULL_HANDBOOK } from "./handbookData";
import SportBuildGuide from "./SportBuildGuide";

// Section 15 (Amendment 15): a chat assistant answering "how do I use
// this app" questions, grounded only in the handbook content below --
// never live project/pricing/client data, never database tool access
// (Director-approved spec, Decision 2). context is built once per role
// and sent with every question; the backend has no independent copy of
// the handbook to check it against, so the same per-role slice Help.jsx
// already uses for its own tab visibility (Director/Admin Guide only
// for a Director) is what keeps that content from ever reaching another
// role here too.
//
// Section 16 (Amendment 16): a "Build Guide" tab sits alongside the
// chat, assembling the real per-sport accessory/flooring/package-tier
// data that already drives real Cost Sheets. Whichever sport is
// currently selected there also gets appended to the chat's own
// context (sportContext below) -- single source of truth, not a
// separate AI paraphrase of the same facts.
function buildHandbookContext(role) {
  const lines = [];
  lines.push("=== Full Handbook (every screen) ===");
  for (const s of FULL_HANDBOOK) {
    lines.push(`\n## ${s.screen}\n${s.what}`);
    if (s.fields?.length) lines.push("Fields: " + s.fields.join(" | "));
    if (s.whenMissing) lines.push(`When something's missing: ${s.whenMissing}`);
    if (s.watch) lines.push(`Watch out for: ${s.watch}`);
  }

  if (role === "sales" || role === "pm") {
    lines.push("\n\n=== Estimator Guide ===\n" + ESTIMATOR_GUIDE.intro);
    for (const s of ESTIMATOR_GUIDE.sections) lines.push(`\n## ${s.title}\n${s.body}`);
  }
  if (role === "director") {
    lines.push("\n\n=== Director/Admin Guide ===\n" + DIRECTOR_ADMIN_GUIDE.intro);
    for (const s of DIRECTOR_ADMIN_GUIDE.sections) lines.push(`\n## ${s.title}\n${s.body}`);
  }

  lines.push("\n\n=== FAQ ===");
  for (const item of FAQ) lines.push(`\nQ: ${item.q}\nA: ${item.a}`);

  return lines.join("\n");
}

function MessageBubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
          isUser ? "bg-gold text-base" : "bg-surface-raised text-text-primary border border-border-dark"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

export default function Education({ token, role, onBack }) {
  const canSeeBuildGuide = role !== "ca_tax";
  const [tab, setTab] = useState("chat");
  const handbookContext = useMemo(() => buildHandbookContext(role), [role]);
  const [sportContext, setSportContext] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  async function handleSend(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || sending) return;
    setError("");
    setInput("");
    const nextMessages = [...messages, { role: "user", content: question }];
    setMessages(nextMessages);
    setSending(true);
    try {
      const { answer } = await askEducationAssistant(token, {
        question,
        context: sportContext ? handbookContext + sportContext : handbookContext,
        history: messages.map((m) => ({ role: m.role, content: m.content })),
      });
      setMessages((cur) => [...cur, { role: "assistant", content: answer }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 px-4">
      <div className="bg-surface border border-border-dark rounded-lg p-6 space-y-4">
        <div className="flex items-center justify-between text-left">
          <div>
            <h2 className="font-heading font-bold text-text-primary text-lg">Education</h2>
            <p className="text-xs text-text-secondary mt-1">
              Ask how to use the app, or look up what a sport needs to build -- answers come from NestaPrime's own
              handbook and real records, not general knowledge.
            </p>
          </div>
          {onBack && (
            <button onClick={onBack} className="text-sm text-gold hover:underline">
              &larr; Back
            </button>
          )}
        </div>

        <div className="flex gap-1 border-b border-border-dark">
          <button
            onClick={() => setTab("chat")}
            className={`text-sm px-3 py-2 border-b-2 -mb-px ${
              tab === "chat" ? "border-gold text-gold font-medium" : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            Chat
          </button>
          {/* Section 16, Decision 1: Build Guide matches the underlying
              construction-catalog data's own read gate (sales/pm/director/
              procurement/site_engineer), not Education's own fully-open
              gate -- ca_tax has no real use for it and would just get a
              403 from the underlying endpoints anyway. */}
          {canSeeBuildGuide && (
            <button
              onClick={() => setTab("build_guide")}
              className={`text-sm px-3 py-2 border-b-2 -mb-px ${
                tab === "build_guide" ? "border-gold text-gold font-medium" : "border-transparent text-text-secondary hover:text-text-primary"
              }`}
            >
              Build Guide
            </button>
          )}
        </div>

        {tab === "chat" && (
          <>
            <p className="text-[11px] text-text-secondary bg-surface-raised border border-border-dark rounded px-2 py-1.5">
              AI-generated, based on the app's own handbook{sportContext ? " and the sport currently open in Build Guide" : ""} --
              verify with a Director for anything affecting pricing, approvals, or compliance.
            </p>

            <div className="space-y-2 min-h-[8rem] max-h-[28rem] overflow-y-auto">
              {messages.length === 0 && (
                <p className="text-sm text-text-secondary text-center py-6">
                  Ask something like "how do I create a new project?" or "what does a basketball court need?"
                </p>
              )}
              {messages.map((m, i) => (
                <MessageBubble key={i} role={m.role} content={m.content} />
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-surface-raised text-text-secondary border border-border-dark rounded-lg px-3 py-2 text-sm">
                    Thinking…
                  </div>
                </div>
              )}
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}

            <form onSubmit={handleSend} className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about using the app…"
                className="flex-1 rounded border border-border-dark bg-surface-raised text-text-primary px-3 py-2 text-sm"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="bg-gold text-base text-sm rounded px-4 py-2 hover:bg-gold-hover disabled:opacity-50"
              >
                {sending ? "Sending…" : "Send"}
              </button>
            </form>
          </>
        )}

        {tab === "build_guide" && canSeeBuildGuide && (
          <SportBuildGuide token={token} onSportDataChange={setSportContext} />
        )}
      </div>
    </div>
  );
}
