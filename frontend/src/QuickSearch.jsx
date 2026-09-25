import { useEffect, useRef, useState } from "react";
import { globalSearch } from "./api";
import { SearchIcon } from "./Icons";

// Amendment 53 (Section 57): the global quick search palette. Opens from the
// sidebar button, the phone top-bar magnifier, "/" and Ctrl/Cmd+K (wired in
// App.jsx). Results come from GET /search, which already limits each kind to what
// the signed-in role can open; nothing here decides visibility. Every state reads
// differently -- a failed search must never look like an empty one.
const MIN_LENGTH = 2;
const DEBOUNCE_MS = 250;

const KIND_NOUN = { client: "clients", lead: "leads", project: "projects", quotation: "quotations" };

export default function QuickSearch({ token, onClose, onOpenResult }) {
  const [q, setQ] = useState("");
  const [state, setState] = useState({ status: "idle", groups: [], message: "" });
  const [active, setActive] = useState(0);
  const [retry, setRetry] = useState(0);
  const inputRef = useRef(null);
  const activeRef = useRef(null);

  const trimmed = q.trim();
  const tooShort = trimmed.length < MIN_LENGTH;

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (tooShort) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setState((s) => ({ ...s, status: "loading", message: "" }));
      globalSearch(token, trimmed, { signal: controller.signal })
        .then((data) => {
          setState({ status: "done", groups: data.groups, message: "" });
          setActive(0);
        })
        .catch((err) => {
          if (err.name === "AbortError") return;
          setState({ status: "error", groups: [], message: err.message || "Search failed" });
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [trimmed, tooShort, token, retry]);

  // Flat, ordered list of every row shown, for arrow-key navigation.
  const rows = state.status === "done" && !tooShort ? state.groups.flatMap((g) => g.items) : [];

  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [active, rows.length]);

  function handleKeyDown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "ArrowDown" && rows.length) {
      e.preventDefault();
      setActive((i) => (i + 1) % rows.length);
    } else if (e.key === "ArrowUp" && rows.length) {
      e.preventDefault();
      setActive((i) => (i - 1 + rows.length) % rows.length);
    } else if (e.key === "Enter" && rows[active]) {
      e.preventDefault();
      onOpenResult(rows[active]);
    }
  }

  let flatIndex = -1;
  const noMatches = state.status === "done" && !tooShort && rows.length === 0;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 print:hidden"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search"
        onKeyDown={handleKeyDown}
        className="bg-surface border border-border-dark shadow-xl flex flex-col w-full h-full sm:h-auto sm:max-h-[75vh] sm:max-w-xl sm:mx-auto sm:mt-[10vh] sm:rounded-lg"
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border-dark">
          <SearchIcon className="w-5 h-5 text-text-secondary shrink-0" />
          <input
            ref={inputRef}
            id="quick-search-input"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search clients, leads, projects, quotations"
            aria-label="Search clients, leads, projects and quotations"
            aria-controls="quick-search-results"
            aria-activedescendant={rows[active] ? `qs-row-${active}` : undefined}
            autoComplete="off"
            className="flex-1 min-w-0 bg-transparent text-text-primary text-base outline-none placeholder:text-text-secondary/60"
          />
          <button onClick={onClose} className="text-xs uppercase tracking-wider text-text-secondary hover:text-text-primary shrink-0">
            Close
          </button>
        </div>

        <div id="quick-search-results" role="listbox" className="flex-1 overflow-y-auto px-2 py-2">
          {trimmed.length === 0 && (
            <p className="px-3 py-4 text-sm text-text-secondary">
              Type a name, phone number, email, city, project number or quotation number.
            </p>
          )}
          {trimmed.length > 0 && tooShort && (
            <p className="px-3 py-4 text-sm text-text-secondary">Type at least {MIN_LENGTH} characters to search.</p>
          )}
          {!tooShort && state.status === "loading" && <p className="px-3 py-4 text-sm text-text-secondary">Searching…</p>}
          {!tooShort && state.status === "error" && (
            <div className="px-3 py-4 text-sm">
              <p className="text-red-400">{state.message}</p>
              <button onClick={() => setRetry((n) => n + 1)} className="mt-2 text-xs text-gold hover:underline">
                Try again
              </button>
            </div>
          )}
          {noMatches && <p className="px-3 py-4 text-sm text-text-secondary">Nothing matches &ldquo;{trimmed}&rdquo;.</p>}

          {!tooShort &&
            state.status === "done" &&
            state.groups
              .filter((g) => g.items.length > 0)
              .map((g) => (
                <div key={g.kind} role="group" aria-label={g.label} className="mb-2">
                  <p className="px-3 py-1.5 text-[11px] uppercase tracking-wider text-text-secondary/70">
                    {g.label} <span className="text-text-secondary/50">({g.total})</span>
                  </p>
                  {g.items.map((item) => {
                    flatIndex += 1;
                    const index = flatIndex;
                    const isActive = index === active;
                    return (
                      <button
                        key={`${item.kind}-${item.id}`}
                        id={`qs-row-${index}`}
                        ref={isActive ? activeRef : null}
                        role="option"
                        aria-selected={isActive}
                        onMouseEnter={() => setActive(index)}
                        onClick={() => onOpenResult(item)}
                        className={`w-full text-left rounded px-3 py-2 ${
                          isActive ? "bg-gold-muted" : "hover:bg-surface-raised"
                        }`}
                      >
                        <span className={`block text-sm font-medium break-words ${isActive ? "text-gold" : "text-text-primary"}`}>
                          {item.primary}
                        </span>
                        {item.secondary && (
                          <span className="block text-xs text-text-secondary break-words">{item.secondary}</span>
                        )}
                      </button>
                    );
                  })}
                  {g.total > g.items.length && (
                    <p className="px-3 py-1 text-xs text-text-secondary">
                      Showing the first {g.items.length} of {g.total} {KIND_NOUN[g.kind] || g.label.toLowerCase()} — type more to narrow it down.
                    </p>
                  )}
                </div>
              ))}
        </div>

        <p className="hidden sm:block px-4 py-2 border-t border-border-dark text-[11px] text-text-secondary/70">
          ↑ ↓ to move &middot; Enter to open &middot; Esc to close
        </p>
      </div>
    </div>
  );
}
