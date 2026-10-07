import { useCallback, useReducer } from "react";
import { updateUser } from "./api";
import { editorReducer, initialEditorState, runIdentifierSave } from "./identifierEditSession";

// The "Edit sign-in" editor of a People screen: which person's editor is open, under which session key, and the server's
// answer for THAT session. Used by both UserManagement.jsx and AdminPeoplePanel.jsx; the rules are in identifierEditSession.js.
// `reload` refreshes the people list and must handle its own errors (a refresh failure is not an editor error).
export function useIdentifierEditor({ token, reload }) {
  const [state, dispatch] = useReducer(editorReducer, initialEditorState);

  const toggle = useCallback((userId) => dispatch({ type: "toggle", userId }), []);
  const close = useCallback(() => dispatch({ type: "close" }), []);
  const save = useCallback(
    (key, userId, payload) =>
      runIdentifierSave({ key, userId, payload, dispatch, reload, update: (id, body) => updateUser(token, id, body) }),
    [token, reload],
  );

  return {
    userId: state.active ? state.active.userId : null,
    key: state.active ? state.active.key : null,
    error: state.error,
    toggle,
    close,
    save,
  };
}
