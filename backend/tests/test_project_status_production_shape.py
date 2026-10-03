"""The production-shaped fixture (six projects), the compatibility decisions this fix deliberately PRESERVES, and scoping.

Preserved, not new: a project is closed only when EVERY quotation is Won or Lost (Amendment 28 Part A). So Won + a live newer
quotation stays Open, and stored SUPERSEDED/EXPIRED rows count as 'not yet closed', in the Dashboard and now in the list.
Known separate inconsistency, deliberately not changed here: the Dashboard's 'Recent projects' list calls GET /projects
without include_calibration=false and therefore still shows calibration projects.
"""
from datetime import datetime, timedelta

import pytest

from app.core.security import hash_password
from app.models.document import Quotation, QuotationStatus
from app.models.user import User, UserRole
from tests.test_dashboard import _create_client_record, _create_project, _director_headers, _login, _released_quotation
from tests.test_project_status_consistency import (
    _create_calibration_project,
    _dashboard_open,
    _list_open,
    _mark_lost,
    _mark_won,
    _newer_draft_quotation,
    _row,
)


def _tally(rows):
    return {
        "total": len(rows),
        "open": sum(r["status"] == "open" for r in rows),
        "won": sum(r["status"] == "won" for r in rows),
        "lost": sum(r["status"] == "lost" for r in rows),
    }


def _production_shaped_world(client, headers):
    """Two calibration projects and three ordinary projects, none with a quotation, plus one ordinary project with an
    OLDER Lost and a NEWER Draft quotation: six projects, the shape of the production database on 2026-10-03."""
    calibration = [_create_calibration_project(client, headers) for _ in range(2)]
    plain = [_create_project(client, headers, _create_client_record(client, headers, name=f"Ordinary {i}")) for i in range(3)]
    quotation, rebid = _released_quotation(client, headers)
    _mark_lost(client, headers, quotation["id"])
    _newer_draft_quotation(client, headers, rebid)
    return calibration, plain, rebid


def test_production_shaped_fixture_counts(client, director_user):
    headers = _director_headers(client, director_user)
    calibration, plain, rebid = _production_shaped_world(client, headers)

    # Dashboard "Active projects": the three plain projects + the re-bid project; calibration never counts.
    assert _dashboard_open(client, headers) == 4

    hidden = client.get("/projects", params={"include_calibration": "false"}, headers=headers).json()
    assert _tally(hidden) == {"total": 4, "open": 4, "won": 0, "lost": 0}
    assert {r["id"] for r in hidden} == {*plain, rebid}
    assert len(hidden) == _dashboard_open(client, headers)

    shown = client.get("/projects", headers=headers).json()  # default: calibration records stay listed
    assert _tally(shown) == {"total": 6, "open": 6, "won": 0, "lost": 0}
    assert {r["id"] for r in shown if r["is_calibration"]} == set(calibration)

    # The screen counts from this one unfiltered list, so choosing a status cannot change the population.
    for status, expected in (("open", 6), ("won", 0), ("lost", 0)):
        assert len(client.get("/projects", params={"status": status}, headers=headers).json()) == expected
    assert _tally(client.get("/projects", headers=headers).json()) == {"total": 6, "open": 6, "won": 0, "lost": 0}


def test_compat_won_with_a_live_quotation_stays_open_as_on_the_dashboard(client, director_user):
    headers = _director_headers(client, director_user)
    quotation, project_id = _released_quotation(client, headers)
    _mark_won(client, headers, quotation["id"])
    _newer_draft_quotation(client, headers, project_id)
    assert _dashboard_open(client, headers) == 1
    assert _row(client, headers, project_id)["status"] == "open"


@pytest.mark.parametrize("stored", ["SUPERSEDED", "EXPIRED"])
def test_compat_stored_superseded_and_expired_rows_count_as_not_yet_closed(client, director_user, db_session, stored):
    """Only Won and Lost close a quotation, so a project whose rows are Won + SUPERSEDED (or EXPIRED) is Open in the
    Dashboard AND in the list. EXPIRED is normally a read-time label; the stored value is forced here to pin the rule."""
    headers = _director_headers(client, director_user)
    quotation, project_id = _released_quotation(client, headers)
    _mark_won(client, headers, quotation["id"])
    assert _row(client, headers, project_id)["status"] == "won"
    extra = _newer_draft_quotation(client, headers, project_id)
    db_session.query(Quotation).filter(Quotation.id == extra["id"]).update({"status": QuotationStatus[stored]})
    db_session.commit()

    assert _dashboard_open(client, headers) == 1
    assert _row(client, headers, project_id)["status"] == "open"
    assert _list_open(client, headers) == _dashboard_open(client, headers)


def test_a_sent_quotation_past_its_expiry_is_still_open_in_both(client, director_user, db_session):
    """EXPIRED is computed at read time and the stored status stays SENT, so such a project is Open everywhere."""
    headers = _director_headers(client, director_user)
    quotation, project_id = _released_quotation(client, headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    db_session.query(Quotation).filter(Quotation.id == quotation["id"]).update({"expires_at": datetime.now() - timedelta(days=5)})
    db_session.commit()
    assert _dashboard_open(client, headers) == 1
    assert _row(client, headers, project_id)["status"] == "open"


def _sales(db_session, email):
    user = User(name=email.split("@")[0], email=email, hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return user


def test_sales_scoping_is_preserved_and_include_calibration_cannot_widen_it(client, director_user, db_session):
    director = _director_headers(client, director_user)
    a, b = _sales(db_session, "sales.a@test.local"), _sales(db_session, "sales.b@test.local")
    own = _create_project(client, director, _create_client_record(client, director, name="Client of A"))
    others = _create_project(client, director, _create_client_record(client, director, name="Client of B"))
    others_calibration = _create_calibration_project(client, director)
    for pid, owner in ((own, a), (others, b), (others_calibration, b)):
        res = client.patch(f"/ownership/project/{pid}", json={"owner_id": str(owner.id), "cascade": False}, headers=director)
        assert res.status_code == 200, res.text
    a_headers = _login(client, "sales.a@test.local")

    assert client.put("/ownership/switch", json={"on": True}, headers=director).status_code == 200
    for params in ({}, {"include_calibration": "true"}, {"include_calibration": "false"}, {"status": "open"}):
        ids = {r["id"] for r in client.get("/projects", params=params, headers=a_headers).json()}
        assert ids == {own}, (params, ids)  # someone else's project AND someone else's calibration project stay invisible
    assert _dashboard_open(client, a_headers) == _list_open(client, a_headers, include_calibration="false") == 1

    # Switch off = the existing org-wide behaviour (unchanged): everything is listed, calibration still excludable.
    assert client.put("/ownership/switch", json={"on": False}, headers=director).status_code == 200
    everything = {r["id"] for r in client.get("/projects", headers=a_headers).json()}
    assert everything == {own, others, others_calibration}
    without = {r["id"] for r in client.get("/projects", params={"include_calibration": "false"}, headers=a_headers).json()}
    assert without == {own, others}
