import { useEffect, useState } from "react";
import { createMessage, listMessages, listMessageTemplates } from "./api";

export default function MessagesPanel({ token, docType, docId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [channel, setChannel] = useState("email");
  const [recipient, setRecipient] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [subject, setSubject] = useState("");
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);
  const [templates, setTemplates] = useState([]);

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
      });
      setRecipient("");
      setTemplateId("");
      setSubject("");
      setNote("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (loading) return <p className="text-xs text-gray-400">Loading messages…</p>;

  return (
    <div className="border border-dashed border-gray-300 rounded p-3 space-y-2 bg-gray-50">
      <div>
        <p className="text-xs font-semibold text-gray-600">Messages (M.7.2)</p>
        <p className="text-[11px] text-gray-400">
          This app has no email/WhatsApp provider wired up -- logging a message here records that you sent this
          document yourself (by whatever means), for an audit trail. It does not actually send anything.
        </p>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {messages.length === 0 && <p className="text-xs text-gray-400">No messages logged yet.</p>}
      {messages.map((m) => (
        <div key={m.id} className="flex flex-wrap items-center gap-1 text-xs bg-white rounded px-2 py-1 border border-gray-200">
          <span className="font-medium">{m.channel}</span>
          <span>&rarr; {m.recipient}</span>
          {m.subject && <span className="text-gray-500">· {m.subject}</span>}
          <span className="text-gray-400">· {new Date(m.created_at).toLocaleString()}</span>
        </div>
      ))}

      <form onSubmit={handleLog} className="flex flex-wrap items-center gap-2 pt-1">
        <select value={channel} onChange={(e) => setChannel(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs">
          <option value="email">email</option>
          <option value="whatsapp">whatsapp</option>
        </select>
        <select
          value={templateId}
          onChange={(e) => selectTemplate(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-xs"
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
          placeholder="Recipient (email or phone)"
          required
          className="rounded border border-gray-300 px-2 py-1 text-xs w-48"
        />
        <input
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Subject (optional)"
          className="rounded border border-gray-300 px-2 py-1 text-xs w-40"
        />
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional)"
          className="rounded border border-gray-300 px-2 py-1 text-xs flex-1 min-w-[8rem]"
        />
        <button
          type="submit"
          disabled={!recipient || sending}
          className="bg-blue-600 text-white text-xs rounded px-3 py-1 hover:bg-blue-700 disabled:opacity-50"
        >
          {sending ? "Logging…" : "Log sent message"}
        </button>
      </form>
    </div>
  );
}
