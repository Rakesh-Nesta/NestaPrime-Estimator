// Amendment 61 Part B: the "Edit sign-in" editor session shared by BOTH People screens (UserManagement.jsx and
// AdminPeoplePanel.jsx, through useIdentifierEditor.js). Pure state transitions, so the timing rules are testable.
//
// Every time an editor is OPENED it gets a new, never-reused session key. A save remembers the key of the session it was
// started from, and its outcome (close the editor, show an error) applies only if that same session is still the open one.
// The person's ID alone cannot do this job: cancel and reopen the same person and the ID is the same but the session is new.
// The key is also the React key of the editor, so a new session is a fresh editor (fresh draft) and a stale outcome never
// touches the draft of the current one.

export const initialEditorState = { counter: 0, active: null, error: "" };

function isCurrent(state, key) {
  return state.active !== null && state.active.key === key;
}

export function editorReducer(state, action) {
  switch (action.type) {
    case "toggle": {
      if (state.active && state.active.userId === action.userId) return { ...state, active: null, error: "" };
      const key = state.counter + 1;
      return { counter: key, active: { key, userId: action.userId }, error: "" };
    }
    case "close":
      return { ...state, active: null, error: "" };
    case "save_started":
      return isCurrent(state, action.key) ? { ...state, error: "" } : state;
    case "save_failed":
      return isCurrent(state, action.key) ? { ...state, error: action.message } : state;
    case "save_succeeded":
      return isCurrent(state, action.key) ? { ...state, active: null, error: "" } : state;
    default:
      return state;
  }
}

// One save, from the editor session `key`. Dispatches the outcome for that session only, and ALWAYS refreshes the people list
// after a successful save (the saved data changed whichever editor is open now, or none). Never throws.
export async function runIdentifierSave({ key, userId, payload, update, dispatch, reload }) {
  dispatch({ type: "save_started", key });
  try {
    await update(userId, payload);
  } catch (err) {
    dispatch({ type: "save_failed", key, message: err.message });
    return false;
  }
  dispatch({ type: "save_succeeded", key });
  await reload();
  return true;
}
