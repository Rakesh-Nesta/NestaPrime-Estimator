import { useEffect, useState } from "react";
import { createMessage, draftMessage, listMessages, listMessageTemplates, NetworkOutcomeUnknownError, PdfExportError, resendMessage } from "./api";
import PdfExportProblem from "./PdfExportProblem";

// Amendment 8 (Sections 8 and 17): WhatsApp (wa-gateway), Telegram (Bot API)
// and Email (SMTP) are all real sends now.
const REAL_SEND_CHANNELS = ["whatsapp", "telegram", "email"];
const DOC_TYPES_WITH_PDF = ["estimate", "quotation"];

// What the app can honestly say about a send. "accepted" is NOT delivery: the provider took it, the recipient may not have it.
const OUTCOME_STYLE = {
  pending: "text-yellow-300",
  accepted: "text-green-400",
  failed: "text-red-400",
  unknown: "text-yellow-300",
  recorded: "text-text-secondary",
};
const DUPLICATE_WARNING = "The previous message may already have been sent. Sending again could create a duplicate.";

function newRequestId() {
  return crypto.randomUUID();
}

export default function MessagesPanel({ token, docType, docId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [channel, setChannel] = useState("email");
  const [recipient, setRecipient] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  const [includeDocument, setIncludeDocument] = useState(false);
  const [sending, setSending] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState("");
  // One request id per send. It stays the same across retries of the SAME send, so a retry returns the existing outcome and
  // never sends twice; it changes when the content changes or after the send is finished.
  const [requestId, setRequestId] = useState(newRequestId);
  const [pdfProblem, setPdfProblem] = useState(null);
  const [lostConnection, setLostConnection] = useState(false);
  const [confirmingFor, setConfirmingFor] = useState(null); // message id whose "send again anyway" is awaiting confirmation
  const [understood, setUnderstood] = useState(false);
  const [resendRequestIds, setResendRequestIds] = useState({});
  const [resending, setResending] = useState(null);

  const isRealSend = REAL_SEND_CHANNELS.includes(channel);
  const canIncludeDocument = isRealSend && DOC_TYPES_WITH_PDF.includes(docType);

  function load() {
    return listMessages(token, docType, docId)
      .then(setMessages)
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, docType, docId]);

  // Any change to what would be sent makes it a different send: a new request id.
  useEffect(() => {
    setRequestId(newRequestId());
    setLostConnection(false);
    setPdfProblem(null);
  }, [channel, recipient, templateId, subject, note, includeDocument]);

  useEffect(() => {
    listMessageTemplates(token, { channel })
      .then((rows) => setTemplates(rows.filter((t) => t.document_type === null || t.document_type === docType)))
      .catch(() => setTemplates([]));
    setTemplateId("");
  }, [token, channel, docType]);

  function selectTemplate(id) {
    setTemplateId(id);
    const t = templates.find((row) => row.id === id);
    if (t) {
      if (t.subject) setSubject(t.subject);
      setNote(t.body);
    }
  }

  async function submitSend() {
    if (sending) return; // no duplicate requests while one is pending
    setError("");
    setPdfProblem(null);
    setSending(true);
    try {
      await createMessage(token, {
        docType, docId, channel, recipient, templateId: templateId || undefined,
        subject: subject || undefined, bodyNote: note || undefined,
        includeDocument: canIncludeDocument && includeDocument, requestId,
      });
      setLostConnection(false);
      setRecipient("");
      setTemplateId("");
      setSubject("");
      setNote("");
      setIncludeDocument(false);
      setRequestId(newRequestId());
      await load();
    } catch (err) {
      if (err instanceof PdfExportError) {
        setPdfProblem({ kind: err.kind, excluded: err.excluded });
      } else if (err instanceof NetworkOutcomeUnknownError) {
        // The request may have been processed. Keep the SAME request id: Retry will return the recorded outcome (or send, if
        // it never arrived) -- it can never send twice.
        setLostConnection(true);
        setError(err.message);
      } else {
        setError(err.message);
      }
    } finally {
      setSending(false);
    }
  }

  async function handleLog(e) {
    e.preventDefault();
    if (!recipient) return;
    await submitSend();
  }

  async function handleResend(m, { confirmed }) {
    if (resending) return;
    setError("");
    setResending(m.id);
    const rid = resendRequestIds[m.id] || newRequestId();
    setResendRequestIds((ids) => ({ ...ids, [m.id]: rid })); // kept so a retry of THIS resend cannot send a third message
    try {
      await resendMessage(token, m.id, { requestId: rid, confirmDuplicateRisk: confirmed });
      setConfirmingFor(null);
      setUnderstood(false);
      setResendRequestIds((ids) => {
        const next = { ...ids };
        delete next[m.id];
        return next;
      });
      await load();
    } catch (err) {
      if (err instanceof PdfExportError) setPdfProblem({ kind: err.kind, excluded: err.excluded });
      else setError(err.message);
    } finally {
      setResending(null);
    }
  }

  async function handleDraftWithAi() {
    setDraftError("");
    setDrafting(true);
    try {
      const { draft } = await draftMessage(token, { docType, docId, channel });
      setNote(draft);
    } catch (err) {
      setDraftError(err.message);
    } finally {
      setDrafting(false);
    }
  }

  if (loading) return <p className="text-xs text-text-secondary">Loading messages…</p>;

  return (
    <div className="border border-dashed border-border-dark bg-surface-raised text-text-primary rounded p-3 space-y-2 bg-surface-raised">
      <div>
        <p className="text-xs font-semibold text-text-secondary">Messages (M.7.2)</p>
        <p className="text-[11px] text-text-secondary">
          {isRealSend
            ? "Amendment 8: this actually sends via the company's WhatsApp/Telegram/Email integration -- real delivery status below, never a status this app can't verify (see Section 8 and Section 17 specs)."
            : "This channel has no provider wired up -- logging a message here records that you sent this document yourself (by whatever means), for an audit trail. It does not actually send anything."}
        </p>
      </div>
      {error && (
        <p className="text-xs text-red-400" role="alert">
          {error}
          {lostConnection && (
            <>
              {" "}
              <button type="button" onClick={submitSend} disabled={sending} className="underline disabled:opacity-50">
                {sending ? "Checking…" : "Retry (will not send twice)"}
              </button>
            </>
          )}
        </p>
      )}
      {pdfProblem && (
        <PdfExportProblem
          token={token}
          docType={docType}
          docId={docId}
          problem={pdfProblem}
          retrying={sending}
          onChanged={() => {}}
          onRetry={submitSend}
        />
      )}
      {draftError && <p className="text-xs text-red-400">{draftError}</p>}
      {messages.length === 0 && <p className="text-xs text-text-secondary">No messages yet.</p>}
      {messages.map((m) => (
        <div key={m.id} className="text-xs bg-surface rounded px-2 py-1 border border-border-dark space-y-1">
          <div className="flex flex-wrap items-center gap-1">
            <span className="font-medium">{m.channel}</span>
            <span>&rarr; {m.recipient}</span>
            {m.subject && <span className="text-text-secondary">· {m.subject}</span>}
            <span className={OUTCOME_STYLE[m.attempt_state] || "text-text-secondary"}>· {m.outcome_label || m.status}</span>
            <span className="text-text-secondary">· {new Date(m.created_at).toLocaleString()}</span>
            {m.previous_attempt_id && <span className="text-text-secondary">· sent again after an earlier attempt</span>}
          </div>
          {m.attempt_state === "failed" && (
            <button type="button" disabled={resending === m.id} onClick={() => handleResend(m, { confirmed: false })} className="text-gold hover:underline disabled:opacity-50">
              {resending === m.id ? "Sending…" : "Try again"}
            </button>
          )}
          {["pending", "unknown", "accepted"].includes(m.attempt_state) && confirmingFor !== m.id && (
            <button type="button" onClick={() => { setConfirmingFor(m.id); setUnderstood(false); }} className="text-gold hover:underline">
              Send again anyway
            </button>
          )}
          {confirmingFor === m.id && (
            <div className="rounded border border-yellow-700 bg-yellow-950/30 p-2 space-y-1" role="alertdialog" aria-label="Confirm sending again">
              <p className="text-yellow-200">{DUPLICATE_WARNING}</p>
              <label className="flex items-center gap-1">
                <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
                I understand and want to send it again
              </label>
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={!understood || resending === m.id}
                  onClick={() => handleResend(m, { confirmed: true })}
                  className="bg-gold text-base rounded px-2 py-0.5 disabled:opacity-50"
                >
                  {resending === m.id ? "Sending…" : "Send again"}
                </button>
                <button type="button" onClick={() => setConfirmingFor(null)} className="text-text-secondary hover:underline">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ))}

      <form onSubmit={handleLog} className="flex flex-wrap items-center gap-2 pt-1">
        <select value={channel} onChange={(e) => setChannel(e.target.value)} className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs">
          <option value="email">email</option>
          <option value="whatsapp">whatsapp</option>
          <option value="telegram">telegram</option>
        </select>
        <select
          value={templateId}
          onChange={(e) => selectTemplate(e.target.value)}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs"
          title="M.7.2 rule 6: Director-managed template library"
        >
          <option value="">(no template)</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id} disabled={channel === "whatsapp" && t.whatsapp_template_status !== "approved"}>
              {t.name}
              {channel === "whatsapp" && t.whatsapp_template_status !== "approved" ? ` (${t.whatsapp_template_status})` : ""}
            </option>
          ))}
        </select>
        <input
          value={recipient}
          onChange={(e) => setRecipient(e.target.value)}
          placeholder={channel === "telegram" ? "Telegram chat id" : "Recipient (email or phone)"}
          required
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs w-48"
        />
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Subject (optional)"
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs w-40"
        />
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={isRealSend ? "Message text ({client_name}, {amount}, {validity}...)" : "Note (optional)"}
          className="rounded border border-border-dark bg-surface-raised text-text-primary px-2 py-1 text-xs flex-1 min-w-[8rem]"
        />
        <button
          type="button"
          onClick={handleDraftWithAi}
          disabled={drafting}
          className="text-xs bg-surface text-gold border border-gold/40 rounded px-2 py-1 hover:bg-gold/10 hover:-translate-y-0.5 transition-all duration-250 ease-out disabled:opacity-50"
        >
          {drafting ? "Drafting…" : "Draft with AI"}
        </button>
        {canIncludeDocument && (
          <label className="flex items-center gap-1 text-xs text-text-secondary">
            <input type="checkbox" checked={includeDocument} onChange={(e) => setIncludeDocument(e.target.checked)} />
            Attach {docType} PDF
          </label>
        )}
        <button
          type="submit"
          disabled={!recipient || sending}
          className="bg-gold text-base text-xs rounded px-3 py-1 hover:bg-gold-hover disabled:opacity-50"
        >
          {sending ? (isRealSend ? "Sending…" : "Logging…") : isRealSend ? "Send" : "Log sent message"}
        </button>
      </form>
    </div>
  );
}
