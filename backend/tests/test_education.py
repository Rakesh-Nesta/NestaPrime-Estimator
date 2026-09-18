"""Section 15 (Amendment 15): POST /education/ask -- a chat assistant
grounded only in whatever reference text the frontend sends as `context`
(the handbook), never live app data. Open to every role. No network
access in tests -- app.api.education.ai_content is monkeypatched, same
discipline as test_message_draft.py."""

from app.api import education as education_api
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.ai_content import AiContentError


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _site_engineer_headers(client, db_session):
    user = User(
        name="Test Site Engineer", email="site-engineer-education@test.local",
        hashed_password=hash_password("TestPass!1"), role=UserRole.SITE_ENGINEER,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "site-engineer-education@test.local")


def test_ask_requires_auth(client):
    res = client.post("/education/ask", json={"question": "How do I create a project?", "context": "handbook text"})
    assert res.status_code == 401


def test_ask_not_configured_fails_fast(client, director_user, monkeypatch):
    """Forces the key unset regardless of the real environment's own
    .env -- this must fail immediately with a clear 503 either way."""
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    headers = _director_headers(client, director_user)

    res = client.post(
        "/education/ask", json={"question": "How do I create a project?", "context": "handbook text"}, headers=headers
    )
    assert res.status_code == 503
    assert "not configured" in res.json()["detail"].lower()


def test_ask_returns_answer_grounded_in_the_sent_context(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)

    captured = {}

    def _fake_generate_chat_reply(system, messages, max_tokens=600):
        captured["system"] = system
        captured["messages"] = messages
        return "Use Dashboard -> + New project."

    monkeypatch.setattr(education_api.ai_content, "generate_chat_reply", _fake_generate_chat_reply)

    res = client.post(
        "/education/ask",
        json={"question": "How do I start a new project?", "context": "Quick mode asks 4 things."},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"answer": "Use Dashboard -> + New project."}
    assert "Quick mode asks 4 things." in captured["system"]
    assert captured["messages"] == [{"role": "user", "content": "How do I start a new project?"}]


def test_ask_forwards_prior_turns_as_messages(client, director_user, monkeypatch):
    """Multi-turn: earlier turns from the frontend's own conversation
    state are threaded into the messages array exactly as given, ahead
    of the new question."""
    headers = _director_headers(client, director_user)

    captured = {}

    def _fake_generate_chat_reply(system, messages, max_tokens=600):
        captured["messages"] = messages
        return "Yes, click Customize size."

    monkeypatch.setattr(education_api.ai_content, "generate_chat_reply", _fake_generate_chat_reply)

    res = client.post(
        "/education/ask",
        json={
            "question": "Can I change it later?",
            "context": "Sport Selection lets you customize court size.",
            "history": [
                {"role": "user", "content": "What is Sport Selection?"},
                {"role": "assistant", "content": "It's where you pick sports and court size."},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert captured["messages"] == [
        {"role": "user", "content": "What is Sport Selection?"},
        {"role": "assistant", "content": "It's where you pick sports and court size."},
        {"role": "user", "content": "Can I change it later?"},
    ]


def test_ask_service_failure_surfaces_as_503(client, director_user, monkeypatch):
    headers = _director_headers(client, director_user)

    def _boom(system, messages, max_tokens=600):
        raise AiContentError("AI chat returned 401: invalid api key")

    monkeypatch.setattr(education_api.ai_content, "generate_chat_reply", _boom)

    res = client.post(
        "/education/ask", json={"question": "How do I use this app?", "context": "handbook text"}, headers=headers
    )
    assert res.status_code == 503
    assert "invalid api key" in res.json()["detail"].lower()


def test_ask_is_open_to_every_role(client, db_session, monkeypatch):
    """Education has never been role-gated in the nav -- the assistant
    over it shouldn't be either, unlike e.g. Reports/Rate Sheet."""
    monkeypatch.setattr(education_api.ai_content, "generate_chat_reply", lambda system, messages, max_tokens=600: "ok")

    headers = _site_engineer_headers(client, db_session)
    res = client.post(
        "/education/ask", json={"question": "How do I use this app?", "context": "handbook text"}, headers=headers
    )
    assert res.status_code == 200, res.text
