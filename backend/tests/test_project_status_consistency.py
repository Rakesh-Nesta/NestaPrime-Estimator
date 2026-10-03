"""The Dashboard 'Open projects' tile and GET /projects must classify a project identically (one rule, app/core/project_status.py).

Before the fix, GET /projects called a project "lost"/"won" if ANY quotation was, so a project with an older Lost quotation
and a newer, live Draft one (a re-bid -- Amendment 26) was Open on the Dashboard but "lost" in the list and absent from the
list's Open filter. Calibration/test projects were also excluded from the Dashboard but counted in the list.
"""
from tests.test_dashboard import (
    _create_client_record,
    _create_project,
    _director_headers,
    _released_quotation,
    _satisfy_project_readiness,  # noqa: F401  (kept importable for sibling tests)
)


def _mark_lost(client, headers, quotation_id):
    res = client.post(f"/quotations/{quotation_id}/mark-lost", json={"reason": "test setup"}, headers=headers)
    assert res.status_code == 200, res.text


def _mark_won(client, headers, quotation_id):
    client.post(f"/quotations/{quotation_id}/send", headers=headers)
    res = client.post(f"/quotations/{quotation_id}/mark-won", json={"waive_evidence_reason": "test setup"}, headers=headers)
    assert res.status_code == 200, res.text


def _newer_draft_quotation(client, headers, project_id):
    """A brand-new Estimate + Draft Quotation on the same project (the re-bid Amendment 26 allows)."""
    project_sport_id = client.get(f"/projects/{project_id}/sports", headers=headers).json()[0]["id"]
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=headers,
    ).json()
    assert client.post(f"/estimates/{estimate['id']}/send", headers=headers).status_code == 200
    estimate = client.get(f"/estimates/{estimate['id']}", headers=headers).json()
    option_id = estimate["options"][0]["id"]
    res = client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _row(client, headers, project_id, **params):
    rows = client.get("/projects", params=params, headers=headers).json()
    return next((r for r in rows if r["id"] == project_id), None)


def _dashboard_open(client, headers):
    return client.get("/dashboard", headers=headers).json()["summary"]["open_projects_count"]


def _list_open(client, headers, **params):
    return len(client.get("/projects", params={"status": "open", **params}, headers=headers).json())


def test_older_lost_plus_newer_draft_is_open_everywhere(client, director_user):
    headers = _director_headers(client, director_user)
    quotation, project_id = _released_quotation(client, headers)
    _mark_lost(client, headers, quotation["id"])
    # Sole quotation Lost -> closed/lost in BOTH places.
    assert _row(client, headers, project_id)["status"] == "lost"
    assert _dashboard_open(client, headers) == 0 and _list_open(client, headers) == 0

    _newer_draft_quotation(client, headers, project_id)

    assert _dashboard_open(client, headers) == 1
    assert _row(client, headers, project_id)["status"] == "open"
    assert _row(client, headers, project_id, status="open") is not None
    assert _row(client, headers, project_id, status="lost") is None
    assert _row(client, headers, project_id, status="won") is None
    assert _list_open(client, headers) == _dashboard_open(client, headers)


def test_every_quotation_lost_stays_lost_and_won_stays_won(client, director_user):
    headers = _director_headers(client, director_user)
    lost_q, lost_pid = _released_quotation(client, headers)
    _mark_lost(client, headers, lost_q["id"])
    won_q, won_pid = _released_quotation(client, headers)
    _mark_won(client, headers, won_q["id"])

    assert _row(client, headers, lost_pid)["status"] == "lost"
    assert _row(client, headers, won_pid)["status"] == "won"
    assert _row(client, headers, lost_pid, status="lost") is not None
    assert _row(client, headers, won_pid, status="won") is not None
    assert _dashboard_open(client, headers) == 0 == _list_open(client, headers)


def test_won_quotation_with_a_newer_live_quotation_is_open_like_the_dashboard(client, director_user):
    """Amendment 28 Part A defines 'closed' as EVERY quotation Won/Lost, so a Won project that also has a live newer
    quotation is Open on the Dashboard. The list now says the same instead of 'won'."""
    headers = _director_headers(client, director_user)
    quotation, project_id = _released_quotation(client, headers)
    _mark_won(client, headers, quotation["id"])
    assert _row(client, headers, project_id)["status"] == "won"

    _newer_draft_quotation(client, headers, project_id)

    assert _dashboard_open(client, headers) == 1
    assert _row(client, headers, project_id)["status"] == "open"
    assert _list_open(client, headers) == 1


def test_project_with_no_quotations_is_open_in_both(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    assert _row(client, headers, project_id)["status"] == "open"
    assert _dashboard_open(client, headers) == 1 == _list_open(client, headers)


def _create_calibration_project(client, headers):
    res = client.post(
        "/projects",
        json={
            "client_id": _create_client_record(client, headers, name="Calibration Client"), "city": "Mumbai",
            "site_condition": "level", "soil_type": "normal", "building_status": "open_air", "site_access": "good",
            "power_available": "yes", "water_available": True, "package": "standard", "is_calibration": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_calibration_projects_are_kept_visible_and_flagged_but_can_be_excluded_from_counts(client, director_user):
    headers = _director_headers(client, director_user)
    real_pid = _create_project(client, headers, _create_client_record(client, headers))
    calibration_pid = _create_calibration_project(client, headers)

    # Dashboard never counts the calibration project (Amendment 28 Part B).
    assert _dashboard_open(client, headers) == 1
    # Default list: calibration record is PRESERVED and visible, flagged, so nothing silently disappears.
    everything = client.get("/projects", headers=headers).json()
    assert {r["id"] for r in everything} == {real_pid, calibration_pid}
    assert next(r for r in everything if r["id"] == calibration_pid)["is_calibration"] is True
    assert next(r for r in everything if r["id"] == real_pid)["is_calibration"] is False
    # Excluding calibration makes the list's Open count equal the Dashboard tile.
    excluded = client.get("/projects", params={"status": "open", "include_calibration": "false"}, headers=headers).json()
    assert [r["id"] for r in excluded] == [real_pid]
    assert len(excluded) == _dashboard_open(client, headers)
    # The flag itself and the record are untouched by listing.
    assert client.get(f"/projects/{calibration_pid}", headers=headers).json()["is_calibration"] is True


def test_calibration_filter_applies_to_every_status_bucket(client, director_user):
    headers = _director_headers(client, director_user)
    quotation, project_id = _released_quotation(client, headers)
    _mark_lost(client, headers, quotation["id"])
    _create_calibration_project(client, headers)

    for status in ("open", "won", "lost"):
        with_cal = client.get("/projects", params={"status": status}, headers=headers).json()
        without = client.get("/projects", params={"status": status, "include_calibration": "false"}, headers=headers).json()
        assert all(not r["is_calibration"] for r in without)
        assert {r["id"] for r in without} <= {r["id"] for r in with_cal}
    assert _row(client, headers, project_id, status="lost", include_calibration="false") is not None
