import { useEffect, useState } from "react";
import {
  listNotifications, listNotificationDeliveryFailures, markAllNotificationsRead, markNotificationRead,
} from "./api";

const KIND_LABELS = {
  follow_up_reminder: "Reminder",
  follow_up_overdue_escalation: "Overdue escalation",
  access_mismatch_escalation: "Access mismatch",
};
const KIND_COLORS = {
  follow_up_reminder: "bg-amber-500/10 text-amber-400",
  follow_up_overdue_escalation: "bg-red-500/10 text-red-400",
  access_mismatch_escalation: "bg-purple-500/10 text-purple-400",
};

function NotificationRow({ note, onRead }) {
  const unread = !note.read_at;
  return (
    <div
      className={`border rounded px-3 py-2 text-sm space-y-1 ${unread ? "border-gold/40 bg-gold-muted/20" : "border-border-dark"}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {unread && <span className="w-1.5 h-1.5 rounded-full bg-gold shrink-0" />}
          <span className="text-text-primary truncate">{note.title}</span>
        </div>
        <span className={`text-xs rounded px-1.5 py-0.5 shrink-0 ${KIND_COLORS[note.kind] ?? "bg-surface-raised text-text-secondary"}`}>
          {KIND_LABELS[note.kind] ?? note.kind}
        </span>
      </div>
      <p className="text-xs text-text-secondary">{note.body}</p>
      <div className="flex items-center justify-between text-xs text-text-secondary">
        <span>{new Date(note.created_at).toLocaleString()}</span>
        {unread && (
          <button onClick={() => onRead(note.id)} className="text-gold hover:underline">
            Mark read
          </button>
        )}
      </div>
    </div>
  );
}

export default function NotificationInbox({ token, role }) {
  const [notifications, setNotifications] = useState([]);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [failures, setFailures] = useState(null);
  const canSeeFailures = role === "director" || role === "admin";

  function load() {
    setLoading(true);
    setError("");
    listNotifications(token, { unreadOnly })
      .then(setNotifications)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, unreadOnly]);

  useEffect(() => {
    if (!canSeeFailures) return;
    listNotificationDeliveryFailures(token).then(setFailures).catch(() => setFailures(null));
  }, [token, canSeeFailures]);

  async function handleRead(id) {
    try {
      await markNotificationRead(token, id);
      setNotifications((rows) => rows.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleMarkAllRead() {
    try {
      await markAllNotificationsRead(token);
      setNotifications((rows) => rows.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    } catch (err) {
      setError(err.message);
    }
  }

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  return (
    <div className="max-w-3xl mx-auto mt-8 mb-10 space-y-6">
      <div className="bg-surface shadow rounded-lg p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Notifications</h2>
            <p className="text-sm text-text-secondary">
              Follow-up reminders and escalations addressed to you.
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <label className="flex items-center gap-1.5 text-text-secondary">
              <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} />
              Unread only
            </label>
            <button onClick={handleMarkAllRead} disabled={unreadCount === 0} className="text-gold hover:underline disabled:opacity-40 disabled:no-underline">
              Mark all read
            </button>
          </div>
        </div>
        {error && <p className="text-sm text-red-400 mt-2">{error}</p>}
      </div>

      <div className="bg-surface shadow rounded-lg p-6 space-y-2">
        {loading && <p className="text-sm text-text-secondary">Loading…</p>}
        {!loading && notifications.length === 0 && (
          <p className="text-sm text-text-secondary">
            {unreadOnly ? "Nothing unread." : "No notifications yet."}
          </p>
        )}
        {notifications.map((note) => (
          <NotificationRow key={note.id} note={note} onRead={handleRead} />
        ))}
      </div>

      {canSeeFailures && failures && failures.length > 0 && (
        <div className="bg-surface shadow rounded-lg p-6 space-y-2 border border-red-500/30">
          <h3 className="text-sm font-semibold text-red-400">Delivery failures</h3>
          <p className="text-xs text-text-secondary">
            These emails exhausted their retries and need a look (usually an SMTP configuration or a stale
            recipient address, not a code problem).
          </p>
          <div className="space-y-1.5 text-sm">
            {failures.map((f) => (
              <div key={f.id} className="flex items-center justify-between gap-3 border border-border-dark rounded px-3 py-2">
                <div className="min-w-0">
                  <p className="text-text-primary truncate">{f.title}</p>
                  <p className="text-xs text-text-secondary">
                    To {f.recipient_name} &middot; {f.email_attempts} attempts &middot; {f.email_last_error || "no error recorded"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
