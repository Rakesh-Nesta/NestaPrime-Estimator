import { useEffect, useState } from "react";
import { createMessage, draftMessage, listMessages, listMessageTemplates } from "./api";

// Amendment 8 (Sections 8 and 17): WhatsApp (wa-gateway), Telegram (Bot API)
// and Email (SMTP) are all real sends now.
const REAL_SEND_CHANNELS = ["whatsapp", "telegram", "email"];
const DOC_TYPES_WITH_PDF = ["estimate", "quotation"];

const STATUS_STYLE = {
  recorded: "text-text-secondary",
  sent: "text-green-400",
  delivered: "text-green-400",
  failed: "text-red-400",
};

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

  async function handleLog(e) {
    e.preventDefault();
    setError("");
    if (!recipient) return;
    setSending(true);
    try {
      await createMessage(token, {
        docType, docId, channel, recipient, templateId: templateId || undefined,
        subject: subject || undefined, bodyNote: note || undefined,
        includeDocument: canIncludeDocument && includeDocument,
      });
      setRecipient("");
      setTemplateId("");
      setSubject("");
      setNote("");
      setIncludeDocument(false);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
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
      {error && <p className="text-xs text-red-400">{error}</p>}
      {draftError && <p className="text-xs text-red-400">{draftError}</p>}
      {messages.length === 0 && <p className="text-xs text-text-secondary">No messages yet.</p>}
      {messages.map((m) => (
        <div key={m.id} className="flex flex-wrap items-center gap-1 text-xs bg-surface rounded px-2 py-1 border border-border-dark">
          <span className="font-medium">{m.channel}</span>
          <span>&rarr; {m.recipient}</span>
          {m.subject && <span className="text-text-secondary">· {m.subject}</span>}
          <span className={STATUS_STYLE[m.status] || "text-text-secondary"}>· {m.status}</span>
          <span className="text-text-secondary">· {new Date(m.created_at).toLocaleString()}</span>
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
