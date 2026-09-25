"""Amendment 57 (Section 60): a Quotation that covers several sports.

Options can be added to (and removed from) a Draft Estimate, the same sport and package twice is
refused, and a Quotation includes at most one package per sport -- two approved packages of one sport
used to be summed and printed twice."""

import pytest

from app.models.user import UserRole
from tests.test_quotations_admin import (
    _add_project_sport,
    _create_client_record,
    _create_project,
    _login,
    _role_headers,
    _verified_cost_sheet,
)

ROLE_USERS = {
    "sales": (UserRole.SALES, "sales-ms@test.local"),
    "site_engineer": (UserRole.SITE_ENGINEER, "eng-ms@test.local"),
    "procurement": (UserRole.PROCUREMENT, "proc-ms@test.local"),
}


def _director(client, director_user):
    return _login(client, "director@test.local")


def _project(client, headers, name="Multi Sport School", sports=("badminton",), cost=1350000):
    client_id = _create_client_record(client, headers, name)
    project_id = _create_project(client, headers, client_id)
    ps_ids = {key: _add_project_sport(client, headers, project_id, key) for key in sports}
    _verified_cost_sheet(client, headers, project_id, cost)
    return project_id, ps_ids


def _option(ps_id, package="standard", cost=850000):
    return {"project_sport_id": ps_id, "package": package, "cost_for_option": cost}


def _create_estimate(client, headers, project_id, options):
    return client.post(f"/projects/{project_id}/estimates", json={"options": options}, headers=headers)


def _approve(client, headers, estimate_id, option_id):
    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


# --- adding an option to a Draft Estimate -------------------------------------------------------


def test_an_added_option_is_priced_exactly_like_one_created_with_the_estimate(client, director_user):
    headers = _director(client, director_user)
    project_a, ps_a = _project(client, headers, "Added Option School", ("badminton", "table_tennis"))
    estimate = _create_estimate(client, headers, project_a, [_option(ps_a["badminton"])]).json()
    added = client.post(
        f"/estimates/{estimate['id']}/options", json=_option(ps_a["table_tennis"], cost=500000), headers=headers
    )
    assert added.status_code == 201, added.text
    assert len(added.json()["options"]) == 2

    project_b, ps_b = _project(client, headers, "Created Together School", ("badminton", "table_tennis"))
    together = _create_estimate(
        client, headers, project_b, [_option(ps_b["badminton"]), _option(ps_b["table_tennis"], cost=500000)]
    ).json()

    def tt_option(estimate_json, ps):
        return next(o for o in estimate_json["options"] if o["project_sport_id"] == ps["table_tennis"])

    a, b = tt_option(added.json(), ps_a), tt_option(together, ps_b)
    assert (a["price_low"], a["price_high"], a["cost_for_option"]) == (b["price_low"], b["price_high"], 500000.0)
    assert a["client_status"] == "pending"


def test_options_can_only_be_added_to_a_draft_estimate_on_the_same_project(client, director_user, db_session):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Draft Only School", ("badminton", "table_tennis"))
    other_project, other_ps = _project(client, headers, "Other Project School", ("badminton",))
    estimate = _create_estimate(client, headers, project_id, [_option(ps["badminton"])]).json()

    # a sport selection that belongs to a different project
    res = client.post(f"/estimates/{estimate['id']}/options", json=_option(other_ps["badminton"], "premium"), headers=headers)
    assert res.status_code == 404

    # unknown estimate
    assert client.post(
        "/estimates/00000000-0000-0000-0000-000000000000/options", json=_option(ps["table_tennis"]), headers=headers
    ).status_code == 404

    # roles: only PM/Director
    for role, (user_role, email) in ROLE_USERS.items():
        h = _role_headers(client, db_session, user_role, email)
        assert client.post(f"/estimates/{estimate['id']}/options", json=_option(ps["table_tennis"]), headers=h).status_code == 403, role
    assert client.post(f"/estimates/{estimate['id']}/options", json=_option(ps["table_tennis"])).status_code == 401

    # once sent, it is read-only
    assert client.post(f"/estimates/{estimate['id']}/send", headers=headers).status_code == 200
    res = client.post(f"/estimates/{estimate['id']}/options", json=_option(ps["table_tennis"], cost=500000), headers=headers)
    assert res.status_code == 400 and "Draft" in res.json()["detail"]


def test_the_same_sport_and_package_twice_is_refused_but_another_package_is_an_alternative(client, director_user):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Duplicate School", ("badminton",))
    res = _create_estimate(client, headers, project_id, [_option(ps["badminton"]), _option(ps["badminton"], cost=900000)])
    assert res.status_code == 400 and "Badminton (Standard) is already an option" in res.json()["detail"]

    ok = _create_estimate(client, headers, project_id, [_option(ps["badminton"]), _option(ps["badminton"], "premium", 1100000)])
    assert ok.status_code == 201 and len(ok.json()["options"]) == 2  # Standard and Premium: alternatives

    res = client.post(f"/estimates/{ok.json()['id']}/options", json=_option(ps["badminton"], "premium", 1200000), headers=headers)
    assert res.status_code == 400 and "Badminton (Premium) is already an option" in res.json()["detail"]
    res = client.post(f"/estimates/{ok.json()['id']}/options", json=_option(ps["badminton"], "budget", 700000), headers=headers)
    assert res.status_code == 201 and len(res.json()["options"]) == 3


# --- removing an option -------------------------------------------------------------------------


def test_an_option_can_be_removed_from_a_draft_estimate_but_never_the_last_or_a_decided_one(client, director_user):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Remove School", ("badminton", "table_tennis"))
    estimate = _create_estimate(client, headers, project_id, [_option(ps["badminton"]), _option(ps["table_tennis"], cost=500000)]).json()
    badminton, tt = estimate["options"]

    res = client.delete(f"/estimates/{estimate['id']}/options/{tt['id']}", headers=headers)
    assert res.status_code == 200 and [o["id"] for o in res.json()["options"]] == [badminton["id"]]

    last = client.delete(f"/estimates/{estimate['id']}/options/{badminton['id']}", headers=headers)
    assert last.status_code == 400 and "at least one option" in last.json()["detail"]

    added = client.post(f"/estimates/{estimate['id']}/options", json=_option(ps["table_tennis"], cost=500000), headers=headers).json()
    decided = next(o for o in added["options"] if o["project_sport_id"] == ps["table_tennis"])
    _approve(client, headers, estimate["id"], decided["id"])
    res = client.delete(f"/estimates/{estimate['id']}/options/{decided['id']}", headers=headers)
    assert res.status_code == 400 and "client decision" in res.json()["detail"]

    assert client.delete(
        f"/estimates/{estimate['id']}/options/00000000-0000-0000-0000-000000000000", headers=headers
    ).status_code == 404
    assert client.post(f"/estimates/{estimate['id']}/send", headers=headers).status_code == 200
    res = client.delete(f"/estimates/{estimate['id']}/options/{badminton['id']}", headers=headers)
    assert res.status_code == 400 and "Draft" in res.json()["detail"]


def test_only_pm_and_director_can_remove_an_option(client, director_user, db_session):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Role Remove School", ("badminton", "table_tennis"))
    estimate = _create_estimate(client, headers, project_id, [_option(ps["badminton"]), _option(ps["table_tennis"], cost=500000)]).json()
    for role, (user_role, email) in ROLE_USERS.items():
        h = _role_headers(client, db_session, user_role, email)
        res = client.delete(f"/estimates/{estimate['id']}/options/{estimate['options'][1]['id']}", headers=h)
        assert res.status_code == 403, role


# --- the Quotation ------------------------------------------------------------------------------


def test_a_two_sport_quotation_built_by_adding_an_option_sums_cost_and_weights_the_floor(client, director_user):
    headers = _director(client, director_user)
    badminton_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")
    client.put(f"/sport-margin-policies/{badminton_id}", json={"floor_margin_percent": 15.0}, headers=headers)
    project_id, ps = _project(client, headers, "Two Sport School", ("badminton", "table_tennis"))
    estimate = _create_estimate(client, headers, project_id, [_option(ps["badminton"])]).json()
    estimate = client.post(
        f"/estimates/{estimate['id']}/options", json=_option(ps["table_tennis"], cost=500000), headers=headers
    ).json()
    option_ids = [o["id"] for o in estimate["options"]]
    for option_id in option_ids:
        _approve(client, headers, estimate["id"], option_id)

    res = client.post(
        f"/projects/{project_id}/quotations", json={"estimate_id": estimate["id"], "included_option_ids": option_ids}, headers=headers
    )
    assert res.status_code == 201, res.text
    quotation = res.json()
    expected_floor = (850000 * 15.0 + 500000 * 18.0) / (850000 + 500000)  # school: client floor 18, badminton override 15
    assert quotation["cost_total"] == 1350000.0
    assert round(quotation["floor_margin_percent"], 2) == round(expected_floor, 2)


def test_two_approved_packages_of_one_sport_cannot_both_go_into_a_quotation(client, director_user):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Alternatives School", ("badminton", "table_tennis"))
    estimate = _create_estimate(
        client, headers, project_id,
        [_option(ps["badminton"]), _option(ps["badminton"], "premium", 1100000), _option(ps["table_tennis"], cost=500000)],
    ).json()
    standard, premium, tt = estimate["options"]
    for option in (standard, premium, tt):
        _approve(client, headers, estimate["id"], option["id"])

    both = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [standard["id"], premium["id"], tt["id"]]},
        headers=headers,
    )
    assert both.status_code == 400
    assert both.json()["detail"] == "Choose one package for Badminton: Standard and Premium are both included"

    one = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [premium["id"], tt["id"]]},
        headers=headers,
    )
    assert one.status_code == 201, one.text
    assert one.json()["cost_total"] == 1600000.0  # 11,00,000 + 5,00,000: Standard is not double-counted


def test_the_same_option_listed_twice_is_refused(client, director_user):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Repeated Option School", ("badminton",))
    estimate = _create_estimate(client, headers, project_id, [_option(ps["badminton"])]).json()
    option_id = estimate["options"][0]["id"]
    _approve(client, headers, estimate["id"], option_id)
    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id, option_id]},
        headers=headers,
    )
    assert res.status_code == 400 and "more than once" in res.json()["detail"]


def test_a_single_sport_quotation_is_unchanged(client, director_user):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Single Sport School", ("badminton",))
    estimate = _create_estimate(client, headers, project_id, [_option(ps["badminton"])]).json()
    option_id = estimate["options"][0]["id"]
    _approve(client, headers, estimate["id"], option_id)
    res = client.post(
        f"/projects/{project_id}/quotations", json={"estimate_id": estimate["id"], "included_option_ids": [option_id]}, headers=headers
    )
    assert res.status_code == 201 and res.json()["cost_total"] == pytest.approx(850000.0)


def test_revising_a_quotation_keeps_one_package_per_sport_and_reports_what_it_includes(client, director_user):
    headers = _director(client, director_user)
    project_id, ps = _project(client, headers, "Revise School", ("badminton", "table_tennis"))
    estimate = _create_estimate(
        client, headers, project_id,
        [_option(ps["badminton"]), _option(ps["badminton"], "premium", 1100000), _option(ps["table_tennis"], cost=500000)],
    ).json()
    standard, premium, tt = estimate["options"]
    for option in (standard, premium, tt):
        _approve(client, headers, estimate["id"], option["id"])
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [standard["id"], tt["id"]]},
        headers=headers,
    ).json()
    assert sorted(quotation["included_option_ids"]) == sorted([standard["id"], tt["id"]])
    assert client.post(f"/quotations/{quotation['id']}/release", headers=headers).status_code == 200

    body = {"discount_type": None, "discount_value": 0, "refresh_pricing": False}
    both = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={**body, "included_option_ids": [standard["id"], premium["id"], tt["id"]]},
        headers=headers,
    )
    assert both.status_code == 400 and "Choose one package for Badminton" in both.json()["detail"]

    same = client.post(
        f"/quotations/{quotation['id']}/revise", json={**body, "included_option_ids": [standard["id"], tt["id"]]}, headers=headers
    )
    assert same.status_code == 200, same.text
