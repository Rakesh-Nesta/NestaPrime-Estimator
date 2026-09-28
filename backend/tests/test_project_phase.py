"""WP6 (correction plan, 2026-09-28): the Pre-sales project phase. "Start Project" moves
from Won to Qualified (covered in test_opportunities.py); this file covers the other
half -- mark_quotation_won confirming the Project and closing its Opportunity as Won
together, the two consistency rejections, an Opportunity going Lost abandoning its
still-Pre-sales Project (and never touching an already-Confirmed one), and containment."""
from datetime import date

from app.core.security import hash_password
from app.models.setting import Setting, SettingScope
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_client_record(client, headers, client_type="government", name="Municipal Corp"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _qualified_opportunity(client, headers, client_id, lead_name="WP6 Test Lead"):
    opp = client.post(
        "/opportunities", json={"lead_name": lead_name, "next_follow_up_date": "2099-01-01"}, headers=headers
    ).json()
    res = client.patch(
        f"/opportunities/{opp['id']}/stage",
        json={"stage": "qualified", "next_follow_up_date": "2099-01-01"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    link = client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": client_id}, headers=headers)
    assert link.status_code == 200, link.text
    return opp["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard", **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return cost_sheet_id


def _sent_quotation(client, headers, project_id, project_sport_id):
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    res = client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _presales_project_with_sent_quotation(client, headers, client_id=None, opportunity_id=None):
    if client_id is None:
        client_id = _create_client_record(client, headers)
    project = _create_project(client, headers, client_id, opportunity_id=opportunity_id)
    project_sport_id = _add_project_sport(client, headers, project["id"])
    _verified_cost_sheet(client, headers, project["id"])
    quotation_id = _sent_quotation(client, headers, project["id"], project_sport_id)
    return project["id"], quotation_id


def test_marking_quotation_won_confirms_project_and_closes_linked_opportunity_as_won(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project_id, quotation_id = _presales_project_with_sent_quotation(client, headers, client_id=client_id, opportunity_id=opp_id)
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "presales"

    res = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "confirmed"
    opp = client.get(f"/opportunities/{opp_id}", headers=headers).json()
    assert opp["stage"] == "won"
    assert opp["next_follow_up_date"] is None

    # Both writes landed in one transaction -- both audit entries exist.
    q_entries = client.get(
        "/audit-log", params={"document_type": "quotation", "document_id": quotation_id}, headers=headers
    ).json()
    assert any(e["field"] == "status" and e["new_value"] == "won" for e in q_entries)
    o_entries = client.get(
        "/audit-log", params={"document_type": "opportunity", "document_id": opp_id}, headers=headers
    ).json()
    assert any(e["field"] == "stage" and e["new_value"] == "won" for e in o_entries)

    # The Opportunity's shared follow-up was completed, not left dangling open.
    follow_ups = client.get(
        f"/follow-ups?entity_type=opportunity&entity_id={opp_id}", headers=headers
    ).json()
    assert all(f["status"] == "completed" for f in follow_ups)


def test_marking_quotation_won_without_a_linked_opportunity_confirms_the_project_only(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, quotation_id = _presales_project_with_sent_quotation(client, headers, opportunity_id=None)

    res = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "confirmed"


def test_marking_quotation_won_is_rejected_when_the_opportunity_was_marked_lost_first(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project_id, quotation_id = _presales_project_with_sent_quotation(client, headers, client_id=client_id, opportunity_id=opp_id)

    lost = client.patch(f"/opportunities/{opp_id}/stage", json={"stage": "lost"}, headers=headers)
    assert lost.status_code == 200, lost.text
    # The same stage change already abandoned the still-Pre-sales Project.
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "abandoned"

    res = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 409, res.text

    # No partial change: neither the Quotation nor the Project moved.
    quotation = client.get(f"/quotations/{quotation_id}", headers=headers).json()
    assert quotation["status"] == "sent"
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "abandoned"


def test_opportunity_marked_lost_abandons_its_presales_project_but_preserves_its_records(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project = _create_project(client, headers, client_id, opportunity_id=opp_id)
    project_sport_id = _add_project_sport(client, headers, project["id"])
    cost_sheet_id = _verified_cost_sheet(client, headers, project["id"])

    res = client.patch(f"/opportunities/{opp_id}/stage", json={"stage": "lost"}, headers=headers)
    assert res.status_code == 200, res.text

    updated = client.get(f"/projects/{project['id']}", headers=headers).json()
    assert updated["phase"] == "abandoned"
    # Kept, not deleted -- the project and everything already built on it are still there.
    assert client.get(f"/projects/{project['id']}/sports", headers=headers).status_code == 200
    assert client.get(f"/cost-sheets/{cost_sheet_id}", headers=headers).status_code == 200
    _ = project_sport_id


def test_opportunity_marked_lost_does_not_touch_an_already_confirmed_project(client, director_user):
    """A confirmed Project's Opportunity moving to Lost afterwards (a data-entry
    correction, however unusual) must never un-confirm it -- only a still-Pre-sales
    Project is ever abandoned."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project_id, quotation_id = _presales_project_with_sent_quotation(client, headers, client_id=client_id, opportunity_id=opp_id)
    won = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won.status_code == 200, won.text
    assert client.get(f"/opportunities/{opp_id}", headers=headers).json()["stage"] == "won"
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "confirmed"

    # The API itself has no state-machine guard against re-patching a terminal stage --
    # exercising that edge case directly is the point of this test.
    res = client.patch(f"/opportunities/{opp_id}/stage", json={"stage": "lost"}, headers=headers)
    assert res.status_code == 200, res.text

    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "confirmed"


def _lock_writes(db_session, director):
    db_session.add(
        Setting(
            key="follow_ups_writes_locked", scope=SettingScope.GLOBAL, value="on",
            effective_from=date(2020, 1, 1), changed_by_id=director.id,
        )
    )
    db_session.commit()


def test_containment_lock_blocks_marking_quotation_won_only_when_it_would_close_an_opportunity(
    client, director_user, db_session
):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project_id, quotation_id = _presales_project_with_sent_quotation(client, headers, client_id=client_id, opportunity_id=opp_id)

    # A second project with no linked Opportunity -- containment must not block this one,
    # since nothing in the follow-up system would be written.
    plain_project_id, plain_quotation_id = _presales_project_with_sent_quotation(client, headers, opportunity_id=None)

    _lock_writes(db_session, director_user)

    blocked = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert blocked.status_code == 423, blocked.text
    assert client.get(f"/quotations/{quotation_id}", headers=headers).json()["status"] == "sent"
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "presales"
    assert client.get(f"/opportunities/{opp_id}", headers=headers).json()["stage"] == "qualified"

    ok = client.post(
        f"/quotations/{plain_quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert client.get(f"/projects/{plain_project_id}", headers=headers).json()["phase"] == "confirmed"


def test_an_opportunity_marked_won_directly_without_starting_a_project_first_cannot_retroactively_start_one(
    client, director_user
):
    """Documents a known, accepted edge case (not a bug fixed by WP6): the API has
    always allowed PATCH /opportunities/{id}/stage to set any stage directly, including
    straight from Qualified to Won, bypassing "Start Project" entirely -- this was true
    before WP6 too, and plenty of existing tests rely on exactly this shortcut (e.g.
    test_opportunities.py's own stage-change tests, which never touch a Project at all).
    WP6 does not add a new restriction on that direct PATCH -- doing so would break that
    existing, legitimate use and is not something the design asked for. The real
    consequence, worth locking in with a test: once such an Opportunity is Won without
    ever starting a Project, it can no longer start one through the normal flow, because
    the gate is now Qualified specifically, not "Qualified or later" -- it is stuck. The
    intended way to reach Won is still via mark_quotation_won on a Project that WAS
    started while Qualified; a direct stage PATCH to Won is a manual override, same as
    it always was, and inherits this one limitation from moving the gate."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp = client.post(
        "/opportunities", json={"lead_name": "Skips Start Project", "next_follow_up_date": "2099-01-01"},
        headers=headers,
    ).json()
    client.patch(
        f"/opportunities/{opp['id']}/stage",
        json={"stage": "qualified", "next_follow_up_date": "2099-01-01"},
        headers=headers,
    )
    client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": client_id}, headers=headers)
    won = client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers)
    assert won.status_code == 200, won.text
    assert client.get(f"/opportunities/{opp['id']}", headers=headers).json()["project_id"] is None

    res = client.post(
        "/projects",
        json={"client_id": client_id, "opportunity_id": opp["id"], **{
            "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
            "building_status": "open_air", "site_access": "good", "power_available": "yes",
            "water_available": True, "package": "standard",
        }},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Qualified" in res.json()["detail"]


def test_an_opportunity_can_pass_through_earlier_stages_before_qualifying_and_still_start_a_project(
    client, director_user
):
    """Sub-question from review: an Opportunity moving New -> Contacted -> Qualified
    before "Start Project" is the ordinary path, not a special case -- the gate checks
    the Opportunity's current stage at the moment of the call, not its history."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp = client.post(
        "/opportunities", json={"lead_name": "Multi-hop Lead", "next_follow_up_date": "2099-01-01"},
        headers=headers,
    ).json()
    client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": client_id}, headers=headers)
    for stage in ("contacted", "qualified"):
        res = client.patch(
            f"/opportunities/{opp['id']}/stage",
            json={"stage": stage, "next_follow_up_date": "2099-01-01"},
            headers=headers,
        )
        assert res.status_code == 200, res.text

    res = client.post(
        "/projects",
        json={"client_id": client_id, "opportunity_id": opp["id"], **{
            "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
            "building_status": "open_air", "site_access": "good", "power_available": "yes",
            "water_available": True, "package": "standard",
        }},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["phase"] == "presales"


def test_directly_marking_an_opportunity_won_is_rejected_while_its_project_is_still_presales(client, director_user):
    """The gap this review round surfaced: a direct PATCH .../stage {"stage": "won"} used
    to bypass mark_quotation_won entirely, leaving the Opportunity Won with its Project
    never confirmed -- exactly the inconsistency the design says must never happen
    silently. No partial change on rejection."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project = _create_project(client, headers, client_id, opportunity_id=opp_id)
    assert project["phase"] == "presales"

    res = client.patch(f"/opportunities/{opp_id}/stage", json={"stage": "won"}, headers=headers)
    assert res.status_code == 409, res.text

    # No partial change: stage and phase both untouched.
    assert client.get(f"/opportunities/{opp_id}", headers=headers).json()["stage"] == "qualified"
    assert client.get(f"/projects/{project['id']}", headers=headers).json()["phase"] == "presales"


def test_directly_marking_an_opportunity_won_still_works_once_its_project_is_confirmed(client, director_user):
    """The new guard only protects a still-Pre-sales Project -- it must never block a
    redundant or otherwise legitimate Won transition once the Project is already
    Confirmed (via mark_quotation_won) or has no linked Project at all."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    opp_id = _qualified_opportunity(client, headers, client_id)
    project_id, quotation_id = _presales_project_with_sent_quotation(client, headers, client_id=client_id, opportunity_id=opp_id)
    won = client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert won.status_code == 200, won.text
    assert client.get(f"/opportunities/{opp_id}", headers=headers).json()["stage"] == "won"

    # Redundant PATCH to the same stage the Opportunity is already at -- allowed.
    res = client.patch(f"/opportunities/{opp_id}/stage", json={"stage": "won"}, headers=headers)
    assert res.status_code == 200, res.text
    assert client.get(f"/projects/{project_id}", headers=headers).json()["phase"] == "confirmed"
