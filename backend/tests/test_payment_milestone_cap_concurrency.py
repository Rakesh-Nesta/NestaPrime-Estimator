"""Finance milestone-cap: reproduction of the race (PR #289) and the regression tests for its fix.

Invariant under test (Section 54, item 4): the milestones of a Work Order may not total more than its order value.

Suspected defect (an *inspection finding* until reproduced): `_check_milestone_cap` (api/work_orders.py) reads the sum
of the other milestones and the endpoint then writes, with no lock, so two requests can each pass the check and
together exceed the cap.

Method. Each racing operation runs the REAL endpoint function (same check, same audit write, same commit) on its OWN
database session/connection. Both are gated at the COMMIT (the harness replaces `commit` on the session), so each has
already passed `_check_milestone_cap` and read the committed state before either commits -- the real transaction
boundary, not a sleep or a delay injected into the database. A second operation that BLOCKS on a lock (which a future
fix might introduce) is detected through pg_stat_activity and then allowed to proceed after the first commits. The
gate widens the window; it shows the invariant CAN break, not how often it does in production.

Cases (R-numbers follow the pending-work register r3, section F):
  R1 create/create    R2 edit/edit (two different milestones)    R3 create/edit
  R4 delete/create (control)    R5 boundary (independent fixtures, sequential)    R6 order-value control

HISTORY: on 17a67113 R1, R2 and R3 REPRODUCED the defect (both operations committed, neither blocked, stored total
1,295,012.65 > V = 1,269,620.25). The fix (api/work_orders.py: the common Work Order locking protocol,
`_lock_work_order_or_404` / `_locked_milestone_or_404`) serialises milestone writers per Work Order. These tests now
assert the EXPECTED outcomes: the second request WAITS for the lock, then re-reads, and receives the existing cap
refusal (HTTP 400 "Milestones would total ..."); exactly one request succeeds; no other exception is accepted.
"""

import time
import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.work_orders import (
    PaymentMilestoneCreate,
    PaymentMilestoneUpdate,
    add_payment_milestone,
    delete_payment_milestone,
    update_payment_milestone,
)
from app.models.document import Quotation, QuotationStatus
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderPaymentMilestone
from tests.concurrency_harness import Op, Session, lock_waiters
from tests.test_payments import _director_headers, _milestone, _won_work_order

DUE = date(2030, 1, 1)


class _Req:  # the endpoints only read request.client for the audit row's IP
    client = None


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _stored_total(work_order_id) -> Decimal:
    with Session() as db:
        rows = db.query(WorkOrderPaymentMilestone.amount_due).filter(
            WorkOrderPaymentMilestone.work_order_id == uuid.UUID(str(work_order_id))
        ).all()
        return sum((_money(r[0]) for r in rows), Decimal("0"))


def _director(session):
    return session.query(User).filter(User.email == "director@test.local").one()


def _create_fn(work_order_id, amount, name):
    def fn(session):
        return add_payment_milestone(
            work_order_id=uuid.UUID(str(work_order_id)),
            payload=PaymentMilestoneCreate(name=name, amount_due=float(amount), due_date=DUE),
            request=_Req(), db=session, current_user=_director(session),
        )
    return fn


def _edit_fn(milestone_id, amount):
    def fn(session):
        return update_payment_milestone(
            milestone_id=uuid.UUID(str(milestone_id)), payload=PaymentMilestoneUpdate(amount_due=float(amount)),
            request=_Req(), db=session, current_user=_director(session),
        )
    return fn


def _delete_fn(milestone_id):
    def fn(session):
        return delete_payment_milestone(
            milestone_id=uuid.UUID(str(milestone_id)), request=_Req(), db=session, current_user=_director(session)
        )
    return fn


def _race(fn1, fn2, wait: float = 6.0):
    """Both operations parked at their commit (or the second blocked on a lock), then released together."""
    op1 = Op(fn1, gate=True).start().wait_holding_locks()
    op2 = Op(fn2, gate=True).start()
    deadline = time.time() + wait
    while time.time() < deadline and not op2.reached_commit.is_set() and lock_waiters() < 1 and op2.thread.is_alive():
        time.sleep(0.05)
    second_blocked_on_lock = (not op2.reached_commit.is_set()) and lock_waiters() >= 1
    op1.release()
    op2.release()
    op1.join()
    op2.join()
    return op1, op2, second_blocked_on_lock


def _outcome(op) -> str:
    if op.exc is None:
        return "committed"
    if isinstance(op.exc, HTTPException):
        return f"refused {op.exc.status_code}"
    return f"error {type(op.exc).__name__}: {op.exc}"


def _record(case, work_order_value, before, op1, op2, blocked, after):
    print(
        f"\n[{case}] V={work_order_value} total_before={before} op1={_outcome(op1)} op2={_outcome(op2)} "
        f"second_blocked_on_lock={blocked} total_after={after} violated={after > work_order_value}"
    )


@pytest.fixture()
def wo(client, director_user):
    headers = _director_headers(client, director_user)
    work_order_id, _project_id, order_value = _won_work_order(client, headers)
    return headers, work_order_id, _money(order_value)


def _assert_serialised(op1, op2, blocked, expected_total, V, after):
    """The fix's expected outcome: the second request waited on the Work Order lock, re-read the committed state and
    got the EXISTING cap refusal; exactly one request succeeded; nothing else went wrong."""
    assert blocked, "the second request did not wait for the Work Order lock"
    assert op1.exc is None, f"first request failed: {op1.exc!r}"
    assert isinstance(op2.exc, HTTPException), f"second request should have been refused, got {op2.exc!r}"
    assert op2.exc.status_code == 400 and "Milestones would total" in str(op2.exc.detail), repr(op2.exc.detail)
    assert after == expected_total, f"stored total {after}, expected {expected_total}"
    assert after <= V


# ---------------------------------------------------------------------------------------------------------------
# R1-R3 and R4: concurrent cases. The expected outcomes are asserted; a violation would be a regression of the fix.
# ---------------------------------------------------------------------------------------------------------------

REPEATS = pytest.mark.parametrize("repeat", [1, 2, 3])


@REPEATS
def test_r1_create_create(client, wo, repeat):
    headers, work_order_id, V = wo
    x = _money(V * Decimal("0.10"))
    _milestone(client, headers, work_order_id, float(V - x), DUE, name="base")
    a = _money(x * Decimal("0.6"))  # a <= x and 2a > x: each create is valid on its own, together they exceed V
    assert a <= x < 2 * a
    before = _stored_total(work_order_id)
    op1, op2, blocked = _race(_create_fn(work_order_id, a, "race-1"), _create_fn(work_order_id, a, "race-2"))
    after = _stored_total(work_order_id)
    _record("R1 create/create", V, before, op1, op2, blocked, after)
    _assert_serialised(op1, op2, blocked, before + a, V, after)


@REPEATS
def test_r2_edit_edit_two_different_milestones(client, wo, repeat):
    headers, work_order_id, V = wo
    x = _money(V * Decimal("0.10"))  # headroom: milestones total V - x
    half = _money((V - x) / 2)
    ma = _milestone(client, headers, work_order_id, float(half), DUE, name="A")
    mb = _milestone(client, headers, work_order_id, float((V - x) - half), DUE, name="B")
    assert _stored_total(work_order_id) == V - x
    d = _money(x * Decimal("0.6"))  # d <= x and 2d > x: each edit is valid alone (V - x + d <= V); together > V
    assert d <= x < 2 * d
    before = _stored_total(work_order_id)
    op1, op2, blocked = _race(
        _edit_fn(ma["id"], _money(Decimal(str(ma["amount_due"])) + d)),
        _edit_fn(mb["id"], _money(Decimal(str(mb["amount_due"])) + d)),
    )
    after = _stored_total(work_order_id)
    _record("R2 edit/edit", V, before, op1, op2, blocked, after)
    _assert_serialised(op1, op2, blocked, before + d, V, after)


@REPEATS
def test_r3_create_edit(client, wo, repeat):
    headers, work_order_id, V = wo
    x = _money(V * Decimal("0.10"))
    half = _money((V - x) / 2)
    ma = _milestone(client, headers, work_order_id, float(half), DUE, name="A")
    _milestone(client, headers, work_order_id, float((V - x) - half), DUE, name="B")
    a = _money(x * Decimal("0.6"))
    d = _money(x * Decimal("0.6"))
    assert a <= x and d <= x and a + d > x
    before = _stored_total(work_order_id)
    op1, op2, blocked = _race(
        _create_fn(work_order_id, a, "race-create"), _edit_fn(ma["id"], _money(Decimal(str(ma["amount_due"])) + d))
    )
    after = _stored_total(work_order_id)
    _record("R3 create/edit", V, before, op1, op2, blocked, after)
    _assert_serialised(op1, op2, blocked, before + a, V, after)  # the create (first) wins; the edit is refused


def test_r4_delete_create_control(client, wo):
    """Control: total == V; a create that only fits once a concurrent delete has committed. With the lock the create
    WAITS for the delete, re-reads, and now fits: both succeed and the cap holds (before the fix it was refused)."""
    headers, work_order_id, V = wo
    half = _money(V / 2)
    ma = _milestone(client, headers, work_order_id, float(half), DUE, name="A")
    _milestone(client, headers, work_order_id, float(V - half), DUE, name="B")
    before = _stored_total(work_order_id)
    assert before == V
    op1, op2, blocked = _race(_delete_fn(ma["id"]), _create_fn(work_order_id, half, "replacement"))
    after = _stored_total(work_order_id)
    _record("R4 delete/create (control)", V, before, op1, op2, blocked, after)
    assert blocked and op1.exc is None and op2.exc is None, (op1.exc, op2.exc)
    assert after == V


def test_edit_of_a_milestone_deleted_while_waiting_gets_the_normal_404(client, wo):
    """The milestone is re-read under the lock: an edit that waited behind a delete of the same milestone is refused
    with the ordinary 404, not an error."""
    headers, work_order_id, V = wo
    ma = _milestone(client, headers, work_order_id, float(_money(V / 4)), DUE, name="A")
    op1, op2, blocked = _race(_delete_fn(ma["id"]), _edit_fn(ma["id"], _money(V / 5)))
    assert blocked and op1.exc is None
    assert isinstance(op2.exc, HTTPException) and op2.exc.status_code == 404, repr(op2.exc)
    assert _stored_total(work_order_id) == 0


def test_different_work_orders_proceed_independently(client, director_user):
    headers = _director_headers(client, director_user)
    wo1, _p1, v1 = _won_work_order(client, headers, name="Independent One")
    wo2, _p2, v2 = _won_work_order(client, headers, name="Independent Two")
    a1, a2 = _money(_money(v1) / 4), _money(_money(v2) / 4)
    op1 = Op(_create_fn(wo1, a1, "one"), gate=True).start().wait_holding_locks()  # holds Work Order 1's lock
    op2 = Op(_create_fn(wo2, a2, "two"), gate=True).start()
    assert op2.reached_commit.wait(8), f"a different Work Order must not wait; exception: {op2.exc!r}"
    assert lock_waiters() == 0
    op1.release()
    op2.release()
    op1.join()
    op2.join()
    assert op1.exc is None and op2.exc is None, (op1.exc, op2.exc)
    assert _stored_total(wo1) == a1 and _stored_total(wo2) == a2


def test_a_refused_request_releases_its_lock(client, wo):
    headers, work_order_id, V = wo
    over = _money(V + Decimal("1"))
    refused = Op(_create_fn(work_order_id, over, "too-big")).start().join()
    assert isinstance(refused.exc, HTTPException) and refused.exc.status_code == 400
    # the next writer on the same Work Order is not blocked by the refused one
    nxt = Op(_create_fn(work_order_id, _money(V / 4), "fits"), gate=True).start()
    nxt.wait_holding_locks(timeout=8)
    assert lock_waiters() == 0
    nxt.release().join()
    assert nxt.exc is None and _stored_total(work_order_id) == _money(V / 4)


def test_a_failed_audit_write_rolls_back_and_releases_its_lock(client, wo, monkeypatch):
    """The business change and its audit entry share one transaction: if the audit write fails, nothing is committed
    and the Work Order lock is released for the next writer."""
    headers, work_order_id, V = wo

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr("app.api.work_orders.write_audit_log_entry", boom)
    failed = Op(_create_fn(work_order_id, _money(V / 4), "will-fail")).start().join()
    monkeypatch.undo()
    assert isinstance(failed.exc, RuntimeError)
    assert _stored_total(work_order_id) == 0
    nxt = Op(_create_fn(work_order_id, _money(V / 4), "after"), gate=True).start()
    nxt.wait_holding_locks(timeout=8)
    assert lock_waiters() == 0
    nxt.release().join()
    assert nxt.exc is None and _stored_total(work_order_id) == _money(V / 4)


# ---------------------------------------------------------------------------------------------------------------
# R5: boundary, independent fixtures (each on its own fresh Work Order; sequential, no concurrency)
# ---------------------------------------------------------------------------------------------------------------


def _fresh(client, director_user, m_fraction="0.5"):
    headers = _director_headers(client, director_user)
    work_order_id, _p, order_value = _won_work_order(client, headers)
    V = _money(order_value)
    m = _money(V * Decimal(m_fraction))
    milestone = _milestone(client, headers, work_order_id, float(m), DUE, name="m")
    return headers, work_order_id, V, m, milestone


def test_r5a_create_exactly_to_the_cap_is_accepted(client, director_user):
    headers, wo_id, V, m, _ = _fresh(client, director_user)
    res = client.post(f"/work-orders/{wo_id}/payment-milestones",
                      json={"name": "rest", "amount_due": float(V - m), "due_date": DUE.isoformat()}, headers=headers)
    assert res.status_code == 201, res.text
    assert _stored_total(wo_id) == V


def test_r5b_create_one_paisa_over_the_cap_is_refused(client, director_user):
    headers, wo_id, V, m, _ = _fresh(client, director_user)
    res = client.post(f"/work-orders/{wo_id}/payment-milestones",
                      json={"name": "rest", "amount_due": float(V - m + Decimal("0.01")), "due_date": DUE.isoformat()},
                      headers=headers)
    assert res.status_code == 400, res.text
    assert _stored_total(wo_id) == m


def test_r5c_edit_exactly_to_the_cap_is_accepted(client, director_user):
    headers, wo_id, V, m, milestone = _fresh(client, director_user)
    res = client.patch(f"/payment-milestones/{milestone['id']}", json={"amount_due": float(V)}, headers=headers)
    assert res.status_code == 200, res.text
    assert _stored_total(wo_id) == V


def test_r5d_edit_one_paisa_over_the_cap_is_refused(client, director_user):
    headers, wo_id, V, m, milestone = _fresh(client, director_user)
    res = client.patch(f"/payment-milestones/{milestone['id']}", json={"amount_due": float(V + Decimal("0.01"))},
                       headers=headers)
    assert res.status_code == 400, res.text
    assert _stored_total(wo_id) == m


# ---------------------------------------------------------------------------------------------------------------
# R6: order-value control -- can anything change a Won quotation's total or status after the Work Order exists?
# ---------------------------------------------------------------------------------------------------------------


def test_r6_order_value_cannot_change_after_won(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    work_order_id, project_id, order_value = _won_work_order(client, headers)
    with Session() as db:
        quotation_id = db.get(WorkOrder, uuid.UUID(str(work_order_id))).quotation_id
        before = db.get(Quotation, quotation_id)
        total_before, status_before = _money(before.quotation_total), before.status
    assert status_before == QuotationStatus.WON

    attempts = {
        "revise": client.post(f"/quotations/{quotation_id}/revise", json={"included_option_ids": [str(uuid.uuid4())]},
                              headers=headers),
        "release": client.post(f"/quotations/{quotation_id}/release", headers=headers),
        "send": client.post(f"/quotations/{quotation_id}/send", headers=headers),
        "reject": client.post(f"/quotations/{quotation_id}/reject",
                              json={"reason_category": "other", "note": "x"}, headers=headers),
        "mark-lost": client.post(f"/quotations/{quotation_id}/mark-lost", json={"reason": "x"}, headers=headers),
        "mark-won again": client.post(f"/quotations/{quotation_id}/mark-won",
                                      json={"reason": "x", "waive_evidence_reason": "x"}, headers=headers),
    }
    print("\n[R6] " + ", ".join(f"{k}={v.status_code}" for k, v in attempts.items()))
    with Session() as db:
        after = db.get(Quotation, quotation_id)
        assert _money(after.quotation_total) == total_before == _money(order_value)
        assert after.status == QuotationStatus.WON
