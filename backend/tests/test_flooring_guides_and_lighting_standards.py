"""Blueprint Ledger gap #9: FlooringGuide, LightingLuxStandard and
SportPoleCount replace what used to be hardcoded dicts in sports.py
(_FLOORING_TABLE, _LUX_TABLE, _POLE_COUNT), and the fixture defaults
(_FIXTURE_LUMENS/_FIXTURE_SPEC) move to Director-editable Master
Settings. These tests confirm both directions: the CRUD/role gates on
the new tables, and that _recommend_flooring/_recommend_lighting
actually read live from them (a Director edit changes the
recommendation without a code change -- the whole point of the gap)."""

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-fg@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-fg@test.local")


def _pm_headers(client, db_session):
    user = User(
        name="Test PM", email="pm-fg@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm-fg@test.local")


def _sport_id(client, headers, sport_key):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Flooring Guide Test School", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ---------------------------------------------------------------------------
# FlooringGuide
# ---------------------------------------------------------------------------


def test_flooring_guides_list_has_the_seeded_28(client, director_user):
    headers = _director_headers(client, director_user)
    guides = client.get("/flooring-guides", headers=headers).json()
    assert len(guides) == 28


def test_sales_can_read_but_not_write_flooring_guides(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    assert client.get("/flooring-guides", headers=sales_headers).status_code == 200
    badminton_id = _sport_id(client, sales_headers, "badminton")
    res = client.put(
        f"/flooring-guides/{badminton_id}",
        json={"primary_spec": "x", "rationale": "y"},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_pm_can_read_but_not_write_flooring_guides(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    assert client.get("/flooring-guides", headers=pm_headers).status_code == 200
    badminton_id = _sport_id(client, pm_headers, "badminton")
    res = client.put(
        f"/flooring-guides/{badminton_id}",
        json={"primary_spec": "x", "rationale": "y"},
        headers=pm_headers,
    )
    assert res.status_code == 403


def test_director_can_update_a_flooring_guide_and_it_is_unique_per_sport(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")

    res = client.put(
        f"/flooring-guides/{badminton_id}",
        json={
            "primary_spec": "Updated primary spec", "secondary_spec": "Updated secondary",
            "budget_spec": None, "rationale": "Updated rationale",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["primary_spec"] == "Updated primary spec"
    assert body["sport_id"] == badminton_id
    assert body["updated_by_id"] is not None

    guides = client.get(f"/flooring-guides?sport_id={badminton_id}", headers=headers).json()
    assert len(guides) == 1  # PUT overwrites the existing row, never creates a second one


def test_flooring_guide_upsert_404s_for_unknown_sport(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.put(
        "/flooring-guides/00000000-0000-0000-0000-000000000000",
        json={"primary_spec": "x", "rationale": "y"},
        headers=headers,
    )
    assert res.status_code == 404


def test_editing_a_flooring_guide_changes_the_live_recommendation(client, director_user):
    """The whole point of gap #9: a Director edit changes what
    /projects/{id}/sports returns, with no code change."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    badminton_id = _sport_id(client, headers, "badminton")

    add_res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": badminton_id, "building_status": "open_air"},
        headers=headers,
    )
    assert add_res.status_code == 201, add_res.text
    before = add_res.json()["recommended_flooring"]["primary"]
    assert "Wooden sprung" in before

    client.put(
        f"/flooring-guides/{badminton_id}",
        json={"primary_spec": "Brand new director-set spec", "rationale": "Director override"},
        headers=headers,
    )

    rows = client.get(f"/projects/{project_id}/sports", headers=headers).json()
    after = next(r for r in rows if r["id"] == add_res.json()["id"])["recommended_flooring"]["primary"]
    assert after == "Brand new director-set spec"


# ---------------------------------------------------------------------------
# LightingLuxStandard
# ---------------------------------------------------------------------------


def test_lighting_lux_standards_list_has_the_seeded_four(client, director_user):
    headers = _director_headers(client, director_user)
    rows = client.get("/lighting-standards/lux", headers=headers).json()
    assert {r["category"] for r in rows} == {"court", "football_cricket", "pool", "gym"}


def test_sales_cannot_write_lighting_lux_standards(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    res = client.put("/lighting-standards/lux/court", json={"lux_practice": 999}, headers=sales_headers)
    assert res.status_code == 403


def test_director_can_update_a_lux_standard_and_it_changes_the_live_recommendation(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    box_cricket_id = _sport_id(client, headers, "box_cricket")  # "football_cricket" category

    add_res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": box_cricket_id, "building_status": "open_air"},
        headers=headers,
    )
    before_lux = add_res.json()["recommended_lighting"]["lux_level"]
    assert before_lux == 500  # seeded match figure

    update_res = client.put(
        "/lighting-standards/lux/football_cricket",
        json={"lux_practice": 200, "lux_match": 650, "lux_tournament": 750},
        headers=headers,
    )
    assert update_res.status_code == 200, update_res.text

    rows = client.get(f"/projects/{project_id}/sports", headers=headers).json()
    after = next(r for r in rows if r["id"] == add_res.json()["id"])
    assert after["recommended_lighting"]["lux_level"] == 650


# ---------------------------------------------------------------------------
# SportPoleCount
# ---------------------------------------------------------------------------


def test_sport_pole_counts_list_has_the_seeded_seven(client, director_user):
    headers = _director_headers(client, director_user)
    rows = client.get("/lighting-standards/pole-counts", headers=headers).json()
    assert len(rows) == 7


def test_director_can_set_and_delete_a_pole_count_and_it_affects_the_live_recommendation(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    tennis_id = _sport_id(client, headers, "tennis")

    add_res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": tennis_id, "building_status": "open_air"},
        headers=headers,
    )
    project_sport_id = add_res.json()["id"]
    before = add_res.json()["recommended_lighting"]
    assert before["pole_count"] == 4  # seeded value

    raise_res = client.put(
        f"/lighting-standards/pole-counts/{tennis_id}", json={"pole_count": 10}, headers=headers
    )
    assert raise_res.status_code == 200, raise_res.text
    rows = client.get(f"/projects/{project_id}/sports", headers=headers).json()
    raised = next(r for r in rows if r["id"] == project_sport_id)["recommended_lighting"]
    assert raised["pole_count"] == 10
    assert raised["fixtures"] >= 10

    del_res = client.delete(f"/lighting-standards/pole-counts/{tennis_id}", headers=headers)
    assert del_res.status_code == 204
    rows = client.get(f"/projects/{project_id}/sports", headers=headers).json()
    after_delete = next(r for r in rows if r["id"] == project_sport_id)["recommended_lighting"]
    assert after_delete["pole_count"] is None


def test_deleting_an_unknown_pole_count_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.delete(
        "/lighting-standards/pole-counts/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Fixture defaults (Master Settings, not a table -- see sports.py's own
# DEFAULT_FIXTURE_LUMENS_DEFAULT/DEFAULT_FIXTURE_SPEC_TEXT_DEFAULT docstring)
# ---------------------------------------------------------------------------


def test_default_fixture_spec_is_director_editable_via_settings(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    box_cricket_id = _sport_id(client, headers, "box_cricket")

    add_res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": box_cricket_id, "building_status": "open_air"},
        headers=headers,
    )
    before = add_res.json()["recommended_lighting"]["fixture_spec"]
    assert "26,000 lm" in before

    setting_res = client.post(
        "/settings",
        json={"key": "default_fixture_spec_text", "value": "Custom LED fixture, 40,000 lm"},
        headers=headers,
    )
    assert setting_res.status_code == 201, setting_res.text

    rows = client.get(f"/projects/{project_id}/sports", headers=headers).json()
    after = next(r for r in rows if r["id"] == add_res.json()["id"])["recommended_lighting"]["fixture_spec"]
    assert after == "Custom LED fixture, 40,000 lm"
