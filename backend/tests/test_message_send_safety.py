"""Message send safety: record the attempt BEFORE contacting the provider; truthful outcomes; retry never double-sends;
'send again anyway' needs explicit, audited confirmation.

  accepted -- the provider accepted it: "Accepted by provider—delivery unconfirmed" (NOT a delivery receipt)
  failed   -- confirmed NOT sent
  unknown  -- may or may not have been sent (timeout/dropped connection after the request left, 5xx, or a stale pending attempt)
  pending  -- recorded, provider not yet answered
All provider calls are monkeypatched (no network)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import text

from app.api import messages as messages_api
from app.models.audit_log import AuditLogEntry
from app.models.message import Message
from app.services import telegram as telegram_service
from app.services import wa_gateway as wa_service
from app.services.email_gateway import EmailGatewayError
from app.services.wa_gateway import WaGatewayError
from tests.concurrency_harness import Session
from tests.test_wa_gateway_integration import _client_facing_estimate, _director_headers, _opt_in_whatsapp

ACCEPTED_LABEL = "Accepted by provider—delivery unconfirmed"
WARNING = "The previous message may already have been sent. Sending again could create a duplicate."


class Crash(BaseException):
    """Simulates the process dying after transmission (not an Exception, so nothing in the app can catch it)."""


@pytest.fixture()
def wa(client, director_user, db_session, monkeypatch):
    headers = _director_headers(client, director_user)
    client_id, _, estimate_id = _client_facing_estimate(client, headers)
    _opt_in_whatsapp(client, headers, client_id)
    calls = []
    behaviour = {"fn": lambda to, text: "wamid.1"}

    def fake_send_text(to, body):
        calls.append((to, body))
        return behaviour["fn"](to, body)

    monkeypatch.setattr(messages_api.wa_gateway, "send_text", fake_send_text)
    return dict(client=client, h=headers, estimate_id=estimate_id, calls=calls, behaviour=behaviour, db=db_session)


def _body(w, request_id=None, recipient="+911234567890", note="hello"):
    body = {"doc_type": "estimate", "doc_id": w["estimate_id"], "channel": "whatsapp", "recipient": recipient, "body_note": note}
    if request_id:
        body["request_id"] = request_id
    return body


def _post(w, **kw):
    return w["client"].post("/messages", json=_body(w, **kw), headers=w["h"])


def _row(db, request_id):
    db.rollback()
    db.expire_all()
    return db.query(Message).filter(Message.request_id == request_id).one()


# ---------------------------------------------------------------- recorded BEFORE the provider is contacted


def test_the_attempt_is_committed_before_the_provider_is_contacted(wa):
    rid = str(uuid.uuid4())
    seen = {}

    def inspect(to, body):
        other = Session()  # a different connection sees only COMMITTED data
        try:
            row = other.execute(text(
                "SELECT attempt_state, recipient, request_fingerprint, status FROM messages WHERE request_id = :r"), {"r": rid}).one_or_none()
        finally:
            other.close()
        seen["row"] = row
        return "wamid.1"

    wa["behaviour"]["fn"] = inspect
    assert _post(wa, request_id=rid).status_code == 201
    row = seen["row"]
    assert row is not None, "the attempt was not committed before the provider call"
    assert row.attempt_state == "pending" and row.recipient == "+911234567890" and len(row.request_fingerprint) == 64
    assert row.status.lower() == "recorded"  # not yet claimed sent
    assert _row(wa["db"], rid).attempt_state == "accepted"


def test_a_crash_after_transmission_leaves_a_recoverable_attempt_that_blocks_a_blind_duplicate(wa):
    rid = str(uuid.uuid4())

    def die(to, body):
        raise Crash()

    wa["behaviour"]["fn"] = die
    with pytest.raises((Crash, BaseExceptionGroup)):  # the test client's event loop may wrap it in a group
        _post(wa, request_id=rid)
    wa["db"].rollback()
    row = _row(wa["db"], rid)
    assert row.attempt_state == "pending" and row.recipient == "+911234567890"  # recorded, never finalized

    listed = wa["client"].get("/messages", params={"doc_type": "estimate", "doc_id": wa["estimate_id"]}, headers=wa["h"]).json()
    assert [(m["request_id"], m["attempt_state"]) for m in listed] == [(rid, "pending")]

    wa["db"].execute(text("UPDATE messages SET attempt_state_at = :t WHERE request_id = :r"),
                     {"t": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10), "r": rid})
    wa["db"].commit()
    listed = wa["client"].get("/messages", params={"doc_type": "estimate", "doc_id": wa["estimate_id"]}, headers=wa["h"]).json()
    assert listed[0]["attempt_state"] == "unknown" and "may or may not" in listed[0]["outcome_label"]  # never "not sent"

    calls_before = len(wa["calls"])
    retry = _post(wa, request_id=rid)  # the ordinary retry
    assert retry.status_code == 200 and retry.json()["already_recorded"] is True and retry.json()["attempt_state"] == "unknown"
    assert len(wa["calls"]) == calls_before  # and nothing was sent again


# ---------------------------------------------------------------- ordinary retry never sends again


def test_an_ordinary_retry_returns_the_existing_outcome_without_sending_again(wa):
    rid = str(uuid.uuid4())
    first = _post(wa, request_id=rid)
    assert first.status_code == 201 and first.json()["attempt_state"] == "accepted"
    assert first.json()["outcome_label"] == ACCEPTED_LABEL and first.json()["resend_requires_confirmation"] is True
    second = _post(wa, request_id=rid)
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"] and second.json()["already_recorded"] is True
    assert len(wa["calls"]) == 1


def test_a_request_id_reused_with_different_content_is_refused(wa):
    rid = str(uuid.uuid4())
    assert _post(wa, request_id=rid).status_code == 201
    for changed in (dict(recipient="+919999999999"), dict(note="a different message")):
        res = _post(wa, request_id=rid, **changed)
        assert res.status_code == 409 and res.json()["detail"]["code"] == "request_id_reused", res.text
    assert len(wa["calls"]) == 1


def test_a_request_id_cannot_be_used_by_another_user(wa, db_session):
    from tests.test_upload_hardening import make_user, user_headers

    rid = str(uuid.uuid4())
    assert _post(wa, request_id=rid).status_code == 201
    other = make_user(db_session, "pm", name="Other PM")
    res = wa["client"].post("/messages", json=_body(wa, request_id=rid), headers=user_headers(wa["client"], other))
    assert res.status_code == 409 and res.json()["detail"]["code"] == "request_id_reused"
    assert len(wa["calls"]) == 1


def test_the_request_id_is_uniquely_constrained_in_the_database(wa):
    rid = str(uuid.uuid4())
    assert _post(wa, request_id=rid).status_code == 201
    row = _row(wa["db"], rid)
    s = Session()
    try:
        with pytest.raises(Exception) as caught:
            s.add(Message(
                doc_type=row.doc_type, doc_id=row.doc_id, channel=row.channel, recipient="x", sender_id=row.sender_id,
                status=row.status, request_id=rid))
            s.commit()
        assert "uq_messages_request_id" in str(caught.value) or "duplicate key" in str(caught.value).lower()
    finally:
        s.rollback()
        s.close()


def test_a_refusal_before_the_provider_is_contacted_records_no_attempt(wa):
    rid = str(uuid.uuid4())
    bad = {**_body(wa, request_id=rid), "include_document": True, "doc_type": "cost_sheet", "doc_id": str(uuid.uuid4())}
    res = wa["client"].post("/messages", json=bad, headers=wa["h"])
    assert res.status_code >= 400
    wa["db"].rollback()
    assert wa["db"].query(Message).filter(Message.request_id == rid).count() == 0
    assert wa["calls"] == []


# ---------------------------------------------------------------- truthful outcomes


def test_provider_acceptance_failure_and_ambiguity_are_distinguished(wa):
    ok = _post(wa).json()
    assert (ok["attempt_state"], ok["status"], ok["outcome_label"]) == ("accepted", "sent", ACCEPTED_LABEL)

    def refused(to, body):
        raise WaGatewayError("instance not connected")  # definite: nothing went out

    wa["behaviour"]["fn"] = refused
    failed = _post(wa).json()
    assert (failed["attempt_state"], failed["status"]) == ("failed", "failed") and failed["resend_requires_confirmation"] is False

    def ambiguous(to, body):
        raise WaGatewayError("read timed out", ambiguous=True)

    wa["behaviour"]["fn"] = ambiguous
    unknown = _post(wa).json()
    assert (unknown["attempt_state"], unknown["status"]) == ("unknown", "recorded")  # NOT claimed failed, NOT claimed sent
    assert unknown["resend_requires_confirmation"] is True and "may or may not" in unknown["outcome_label"]


def test_an_unexpected_error_after_the_attempt_is_recorded_reads_as_unknown_not_failed(wa):
    def bug(to, body):
        raise RuntimeError("something unexpected inside the send")

    wa["behaviour"]["fn"] = bug
    res = _post(wa)
    assert res.status_code == 201 and res.json()["attempt_state"] == "unknown"


class _Resp:
    def __init__(self, status):
        self.status_code = status
        self.text = "x"
        self.headers = {"content-type": "application/json"}

    def json(self):
        return {"ok": False, "description": "x"}


@pytest.mark.parametrize("effect,ambiguous", [
    (httpx.ConnectError("refused"), False), (httpx.ConnectTimeout("t"), False),
    (httpx.ReadTimeout("t"), True), (httpx.RemoteProtocolError("dropped"), True), (httpx.WriteError("w"), True),
    (_Resp(409), False), (_Resp(400), False), (_Resp(500), True), (_Resp(503), True),
])
def test_whatsapp_and_telegram_classify_transport_and_http_failures(monkeypatch, effect, ambiguous):
    def post(*a, **k):
        if isinstance(effect, Exception):
            raise effect
        return effect

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(wa_service.settings, "wa_gateway_base_url", "http://gw")
    monkeypatch.setattr(wa_service.settings, "wa_gateway_api_key", "k")
    with pytest.raises(WaGatewayError) as wa_error:
        wa_service.send_text("+91", "hi")
    assert wa_error.value.ambiguous is ambiguous
    monkeypatch.setattr(telegram_service.settings, "telegram_bot_token", "t")
    with pytest.raises(telegram_service.TelegramError) as tg_error:
        telegram_service.send_text("1", "hi")
    assert tg_error.value.ambiguous is ambiguous


def test_not_configured_is_a_confirmed_failure_not_ambiguous():
    with pytest.raises(WaGatewayError) as error:
        wa_service.send_text("+91", "hi")
    assert error.value.ambiguous is False


class _FakeSMTP:
    """smtplib.SMTP stand-in that fails at a chosen stage."""
    stage_failure = None  # (stage, exception)
    close_error = None

    def __init__(self, *a, **k):
        self._fail("connect")

    def _fail(self, stage):
        if _FakeSMTP.stage_failure and _FakeSMTP.stage_failure[0] == stage:
            raise _FakeSMTP.stage_failure[1]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if _FakeSMTP.close_error and exc[0] is None:
            raise _FakeSMTP.close_error
        return False

    def starttls(self):
        pass

    def login(self, *a):
        self._fail("login")

    def sendmail(self, *a):
        self._fail("transfer")


@pytest.mark.parametrize("stage,exc,ambiguous", [
    ("connect", OSError("connection refused"), False),
    ("login", __import__("smtplib").SMTPAuthenticationError(535, b"bad"), False),
    ("transfer", __import__("smtplib").SMTPRecipientsRefused({"x@y": (550, b"no")}), False),
    ("transfer", __import__("smtplib").SMTPDataError(554, b"rejected"), False),
    ("transfer", TimeoutError("timed out"), True),
    ("transfer", __import__("smtplib").SMTPServerDisconnected("dropped"), True),
])
def test_email_classifies_failures_by_stage(monkeypatch, stage, exc, ambiguous):
    import smtplib

    from app.services import email_gateway

    monkeypatch.setattr(email_gateway.settings, "smtp_host", "h")
    monkeypatch.setattr(email_gateway.settings, "smtp_username", "u")
    monkeypatch.setattr(email_gateway.settings, "smtp_password", "p")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.stage_failure, _FakeSMTP.close_error = (stage, exc), None
    with pytest.raises(EmailGatewayError) as error:
        email_gateway.send_email("a@b.c", "s", "b")
    assert error.value.ambiguous is ambiguous


def test_a_failure_while_closing_the_connection_after_the_server_accepted_the_message_is_not_a_send_failure(monkeypatch):
    import smtplib

    from app.services import email_gateway

    monkeypatch.setattr(email_gateway.settings, "smtp_host", "h")
    monkeypatch.setattr(email_gateway.settings, "smtp_username", "u")
    monkeypatch.setattr(email_gateway.settings, "smtp_password", "p")
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.stage_failure, _FakeSMTP.close_error = None, smtplib.SMTPServerDisconnected("closed")
    try:
        email_gateway.send_email("a@b.c", "s", "b")  # returns normally: the server had accepted it
    finally:
        _FakeSMTP.close_error = None


# ---------------------------------------------------------------- "send again anyway"


def _make_unknown(wa):
    wa["behaviour"]["fn"] = lambda to, body: (_ for _ in ()).throw(WaGatewayError("read timed out", ambiguous=True))
    first = _post(wa).json()
    assert first["attempt_state"] == "unknown"
    wa["behaviour"]["fn"] = lambda to, body: "wamid.2"
    return first


def test_resending_after_an_unknown_outcome_requires_explicit_confirmation(wa):
    first = _make_unknown(wa)
    calls_before = len(wa["calls"])
    refused = wa["client"].post(f"/messages/{first['id']}/resend", json={}, headers=wa["h"])
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["code"] == "duplicate_risk_confirmation_required" and detail["message"] == WARNING
    assert detail["previous_outcome"] == "unknown"
    refused_false = wa["client"].post(f"/messages/{first['id']}/resend", json={"confirm_duplicate_risk": False}, headers=wa["h"])
    assert refused_false.status_code == 409
    assert len(wa["calls"]) == calls_before  # nothing was sent without the confirmation


def test_a_confirmed_resend_is_a_new_linked_audited_attempt_and_its_own_retry_never_sends_again(wa, director_user):
    first = _make_unknown(wa)
    rid = str(uuid.uuid4())
    calls_before = len(wa["calls"])
    res = wa["client"].post(f"/messages/{first['id']}/resend", json={"confirm_duplicate_risk": True, "request_id": rid}, headers=wa["h"])
    assert res.status_code == 201, res.text
    new = res.json()
    assert new["id"] != first["id"] and new["previous_attempt_id"] == first["id"]
    assert new["attempt_state"] == "accepted" and new["resend_confirmed_at"] is not None
    assert len(wa["calls"]) == calls_before + 1
    db = wa["db"]
    db.rollback()
    row = db.get(Message, uuid.UUID(new["id"]))
    assert row.resend_confirmed_by_id == director_user.id and row.request_id == rid
    entry = db.query(AuditLogEntry).filter(AuditLogEntry.field == "resend_confirmed", AuditLogEntry.document_id == row.id).one()
    assert entry.reason == WARNING and entry.old_value == "unknown" and entry.document_type == "message"
    # the original attempt is untouched
    assert db.get(Message, uuid.UUID(first["id"])).attempt_state == "unknown"

    again = wa["client"].post(f"/messages/{first['id']}/resend", json={"confirm_duplicate_risk": True, "request_id": rid}, headers=wa["h"])
    assert again.status_code == 200 and again.json()["id"] == new["id"] and again.json()["already_recorded"] is True
    assert len(wa["calls"]) == calls_before + 1  # the retry of the resend did not send a third message


def test_a_confirmed_failure_can_be_retried_without_the_duplicate_warning(wa):
    wa["behaviour"]["fn"] = lambda to, body: (_ for _ in ()).throw(WaGatewayError("instance not connected"))
    failed = _post(wa).json()
    assert failed["attempt_state"] == "failed"
    wa["behaviour"]["fn"] = lambda to, body: "wamid.3"
    res = wa["client"].post(f"/messages/{failed['id']}/resend", json={}, headers=wa["h"])
    assert res.status_code == 201 and res.json()["previous_attempt_id"] == failed["id"] and res.json()["resend_confirmed_at"] is None


@pytest.mark.parametrize("state_setup", ["accepted", "pending"])
def test_accepted_and_pending_attempts_also_require_confirmation(wa, state_setup):
    first = _post(wa).json()  # accepted
    if state_setup == "pending":
        wa["db"].execute(text("UPDATE messages SET attempt_state = 'pending', attempt_state_at = now() WHERE id = :i"), {"i": first["id"]})
        wa["db"].commit()
    res = wa["client"].post(f"/messages/{first['id']}/resend", json={}, headers=wa["h"])
    assert res.status_code == 409 and res.json()["detail"]["code"] == "duplicate_risk_confirmation_required"


def test_resend_is_limited_to_document_roles_and_visible_documents(wa, db_session):
    from tests.test_upload_hardening import make_user, user_headers

    first = _post(wa).json()
    procurement = make_user(db_session, "procurement", name="Buyer")
    res = wa["client"].post(f"/messages/{first['id']}/resend", json={"confirm_duplicate_risk": True}, headers=user_headers(wa["client"], procurement))
    assert res.status_code == 403
    assert wa["client"].post(f"/messages/{uuid.uuid4()}/resend", json={}, headers=wa["h"]).status_code == 404


def test_a_resend_reuses_the_original_content_including_the_generated_document_flag(wa):
    body = {**_body(wa), "include_document": True}
    sent = []
    wa["behaviour"]["fn"] = lambda to, text: (_ for _ in ()).throw(WaGatewayError("timeout", ambiguous=True))
    import app.api.messages as m

    original_media = m.wa_gateway.send_media
    m.wa_gateway.send_media = lambda *a, **k: (sent.append((a, k)), (_ for _ in ()).throw(WaGatewayError("timeout", ambiguous=True)))[1]
    try:
        first = wa["client"].post("/messages", json=body, headers=wa["h"]).json()
        assert first["include_document"] is True and first["attempt_state"] == "unknown"
        m.wa_gateway.send_media = lambda *a, **k: (sent.append((a, k)), "wamid.9")[1]
        res = wa["client"].post(f"/messages/{first['id']}/resend", json={"confirm_duplicate_risk": True}, headers=wa["h"])
    finally:
        m.wa_gateway.send_media = original_media
    assert res.status_code == 201 and res.json()["include_document"] is True and len(sent) == 2  # media was sent both times
