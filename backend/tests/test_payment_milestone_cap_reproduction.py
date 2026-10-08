"""Finance milestone-cap reproduction (TEST-ONLY; no product code changes).

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

RESULT (17a67113, local throwaway Postgres): R1, R2 and R3 REPRODUCED -- both operations committed, neither blocked on a
lock, and the stored total exceeded the order value (V = 1,269,620.25; stored 1,295,012.65). R4 control: no violation
(the create was refused 400 because the delete had not committed). R5 a-d: boundary behaviour correct. R6: no path
changed the Won quotation. The fix design is NOT part of this package.
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


# ---------------------------------------------------------------------------------------------------------------
# R1-R3 and R4: concurrent cases. The invariant is asserted; a violation is a REPRODUCED defect.
# ---------------------------------------------------------------------------------------------------------------

# R1-R3 REPRODUCE the suspected defect (recorded 5 Oct 2026 on 17a67113: 3 of 3 cases, every repeat). They are marked
# xfail(strict=True) so the suite stays green while the defect is open, and so that the day a fix lands the unexpected
# pass FAILS the build and forces this marker to be removed deliberately. Remove the marker with the fix.
REPRODUCED = pytest.mark.xfail(
    strict=True,
    reason="REPRODUCED: _check_milestone_cap has no lock; concurrent requests that each pass the check exceed the order value",
)
REPEATS = pytest.mark.parametrize("repeat", [1, 2, 3])


@REPRODUCED
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
    assert after <= V, f"cap violated: stored total {after} > order value {V}"


@REPRODUCED
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
    assert after <= V, f"cap violated: stored total {after} > order value {V}"


@REPRODUCED
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
    assert after <= V, f"cap violated: stored total {after} > order value {V}"


def test_r4_delete_create_control(client, wo):
    """Control: total == V; a create that only fits if a concurrent delete lands first. Either outcome keeps the cap."""
    headers, work_order_id, V = wo
    half = _money(V / 2)
    ma = _milestone(client, headers, work_order_id, float(half), DUE, name="A")
    _milestone(client, headers, work_order_id, float(V - half), DUE, name="B")
    before = _stored_total(work_order_id)
    assert before == V
    op1, op2, blocked = _race(_delete_fn(ma["id"]), _create_fn(work_order_id, half, "replacement"))
    after = _stored_total(work_order_id)
    _record("R4 delete/create (control)", V, before, op1, op2, blocked, after)
    assert op1.exc is None
    assert after <= V


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
