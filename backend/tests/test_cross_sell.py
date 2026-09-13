"""Amendment 3 (Annexure 2), Section 7: "Complete Your Facility" cross-sell
-- CrossSellAddon catalog + one-tap EstimateOptionAddon snapshots."""

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(
        name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _sport_id(client, headers, key="tennis"):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == key)


def _create_client_record(client, headers, name="Test School"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id,
        "city": "Mumbai",
        "site_condition": "level",
        "soil_type": "normal",
        "building_status": "open_air",
        "site_access": "good",
        "power_available": "yes",
        "water_available": True,
        "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="tennis"):
    sport_id = _sport_id(client, headers, sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers)
    assert create_res.status_code == 201, create_res.text
    verify_res = client.post(f"/cost-sheets/{create_res.json()['id']}/verify", headers=headers)
    assert verify_res.status_code == 200, verify_res.text


def _create_option(client, headers, sport_key="tennis"):
    """Project + verified cost sheet + a single Estimate option, tagged to
    one sport -- everything the addon endpoints need to have something to
    attach to and match against."""
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key)
    _verified_cost_sheet(client, headers, project_id)
    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return project_id, res.json()["options"][0]["id"]


def _create_addon(client, headers, name="Fencing", category="fencing", cost=120.0, margin_percent=20.0,
                   unit="sqft", all_sports=False, activate=True, sport_keys=("tennis",)):
    res = client.post(
        "/cross-sell-addons",
        json={"name": name, "category": category, "cost": cost, "margin_percent": margin_percent,
              "unit": unit, "all_sports": all_sports},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    addon = res.json()
    assert addon["is_active"] is False  # J.1: manual entry starts unverified

    if not all_sports and sport_keys:
        sport_ids = [_sport_id(client, headers, key) for key in sport_keys]
        set_res = client.put(f"/cross-sell-addons/{addon['id']}/sports", json={"sport_ids": sport_ids}, headers=headers)
        assert set_res.status_code == 200, set_res.text

    if activate:
        activate_res = client.patch(f"/cross-sell-addons/{addon['id']}", json={"is_active": True}, headers=headers)
        assert activate_res.status_code == 200, activate_res.text
        addon = activate_res.json()
    return addon


# ---------------------------------------------------------------------------
# Catalog CRUD + role gating
# ---------------------------------------------------------------------------


def test_addon_created_manually_starts_inactive(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, activate=False)
    assert addon["is_active"] is False
    # selling_price is derived from cost+margin whenever both are set,
    # independent of is_active -- is_active only gates the Estimate-step
    # suggestion/add endpoints, not this catalog view.
    assert addon["selling_price"] == 150.0


def test_addon_with_no_cost_has_no_selling_price(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/cross-sell-addons",
        json={"name": "Unpriced", "category": "other", "all_sports": True},
        headers=headers,
    )
    assert res.json()["selling_price"] is None


def test_addon_selling_price_uses_k2_margin_formula(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, cost=120.0, margin_percent=20.0)
    assert round(addon["selling_price"], 2) == 150.0  # 120 / (1 - 0.20)


def test_cannot_activate_addon_without_cost_and_margin(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/cross-sell-addons",
        json={"name": "Lighting", "category": "lighting", "all_sports": True},
        headers=headers,
    )
    addon_id = res.json()["id"]

    activate_res = client.patch(f"/cross-sell-addons/{addon_id}", json={"is_active": True}, headers=headers)
    assert activate_res.status_code == 422


def test_cannot_activate_via_partial_update_missing_margin(client, director_user):
    """Activation validation checks the *effective* cost/margin after the
    patch is applied, not just the fields present in this one call."""
    headers = _director_headers(client, director_user)
    res = client.post(
        "/cross-sell-addons",
        json={"name": "Seating", "category": "seating", "cost": 500.0, "all_sports": True},
        headers=headers,
    )
    addon_id = res.json()["id"]

    activate_res = client.patch(f"/cross-sell-addons/{addon_id}", json={"is_active": True}, headers=headers)
    assert activate_res.status_code == 422


def test_sales_cannot_read_or_write_catalog(client, db_session, director_user):
    director_headers = _director_headers(client, director_user)
    _create_addon(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    assert client.get("/cross-sell-addons", headers=sales_headers).status_code == 403
    assert client.post(
        "/cross-sell-addons", json={"name": "X", "category": "other"}, headers=sales_headers
    ).status_code == 403


def test_pm_can_read_but_not_write_catalog(client, db_session, director_user):
    director_headers = _director_headers(client, director_user)
    _create_addon(client, director_headers)

    pm_headers = _pm_headers(client, db_session)
    assert client.get("/cross-sell-addons", headers=pm_headers).status_code == 200
    assert client.post(
        "/cross-sell-addons", json={"name": "X", "category": "other"}, headers=pm_headers
    ).status_code == 403


def test_setting_addon_sports_rejects_unknown_sport_id(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, activate=False, sport_keys=())
    res = client.put(
        f"/cross-sell-addons/{addon['id']}/sports",
        json={"sport_ids": ["00000000-0000-0000-0000-000000000000"]},
        headers=headers,
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def test_suggestions_match_by_tagged_sport(client, director_user):
    headers = _director_headers(client, director_user)
    _create_addon(client, headers, name="Tennis Fencing", sport_keys=("tennis",))
    _create_addon(client, headers, name="Kabaddi Fencing", sport_keys=("kabaddi",))
    project_id, _ = _create_option(client, headers, sport_key="tennis")

    res = client.get(f"/cross-sell-addons/suggestions/for-project/{project_id}", headers=headers)
    assert res.status_code == 200, res.text
    names = [a["name"] for a in res.json()]
    assert names == ["Tennis Fencing"]


def test_suggestions_include_all_sports_addons_regardless_of_project_sports(client, director_user):
    headers = _director_headers(client, director_user)
    _create_addon(client, headers, name="AMC", category="amc", all_sports=True, sport_keys=())
    project_id, _ = _create_option(client, headers, sport_key="tennis")

    res = client.get(f"/cross-sell-addons/suggestions/for-project/{project_id}", headers=headers)
    assert [a["name"] for a in res.json()] == ["AMC"]


def test_suggestions_exclude_inactive_addons(client, director_user):
    headers = _director_headers(client, director_user)
    _create_addon(client, headers, name="Not Yet Priced", activate=False, sport_keys=("tennis",))
    project_id, _ = _create_option(client, headers, sport_key="tennis")

    res = client.get(f"/cross-sell-addons/suggestions/for-project/{project_id}", headers=headers)
    assert res.json() == []


def test_suggestions_capped_at_five(client, director_user):
    headers = _director_headers(client, director_user)
    for i in range(7):
        _create_addon(client, headers, name=f"Addon {i}", sport_keys=("tennis",))
    project_id, _ = _create_option(client, headers, sport_key="tennis")

    res = client.get(f"/cross-sell-addons/suggestions/for-project/{project_id}", headers=headers)
    assert len(res.json()) == 5


def test_suggestions_strip_cost_and_margin_for_sales(client, db_session, director_user):
    """K.3: cost/margin never visible to Sales, even on a suggestion."""
    director_headers = _director_headers(client, director_user)
    _create_addon(client, director_headers, sport_keys=("tennis",))
    project_id, _ = _create_option(client, director_headers, sport_key="tennis")

    director_res = client.get(f"/cross-sell-addons/suggestions/for-project/{project_id}", headers=director_headers)
    assert director_res.json()[0]["cost"] is not None
    assert director_res.json()[0]["margin_percent"] is not None

    sales_headers = _sales_headers(client, db_session)
    sales_res = client.get(f"/cross-sell-addons/suggestions/for-project/{project_id}", headers=sales_headers)
    assert sales_res.status_code == 200, sales_res.text
    assert sales_res.json()[0]["cost"] is None
    assert sales_res.json()[0]["margin_percent"] is None
    assert sales_res.json()[0]["selling_price"] is not None  # price itself still visible


# ---------------------------------------------------------------------------
# One-tap add / remove
# ---------------------------------------------------------------------------


def test_add_addon_to_option_creates_frozen_snapshot(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, cost=120.0, margin_percent=20.0, unit="sqft", sport_keys=("tennis",))
    _, option_id = _create_option(client, headers, sport_key="tennis")

    res = client.post(f"/estimate-options/{option_id}/addons", json={"addon_id": addon["id"]}, headers=headers)
    assert res.status_code == 201, res.text
    row = res.json()
    assert row["name"] == "Fencing"
    assert row["unit"] == "sqft"
    assert round(row["selling_price"], 2) == 150.0
    assert row["cost"] == 120.0

    list_res = client.get(f"/estimate-options/{option_id}/addons", headers=headers)
    assert len(list_res.json()) == 1


def test_addon_snapshot_survives_later_catalog_price_change(client, director_user):
    """M.2 freezing principle: a document a client has already seen never
    silently changes because someone edited the catalog afterward."""
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, cost=120.0, margin_percent=20.0, sport_keys=("tennis",))
    _, option_id = _create_option(client, headers, sport_key="tennis")
    client.post(f"/estimate-options/{option_id}/addons", json={"addon_id": addon["id"]}, headers=headers)

    client.patch(f"/cross-sell-addons/{addon['id']}", json={"cost": 500.0}, headers=headers)

    row = client.get(f"/estimate-options/{option_id}/addons", headers=headers).json()[0]
    assert row["cost"] == 120.0


def test_cannot_add_inactive_or_unpriced_addon_to_option(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, activate=False, sport_keys=("tennis",))
    _, option_id = _create_option(client, headers, sport_key="tennis")

    res = client.post(f"/estimate-options/{option_id}/addons", json={"addon_id": addon["id"]}, headers=headers)
    assert res.status_code == 400


def test_adding_addon_to_nonexistent_option_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, sport_keys=("tennis",))

    res = client.post(
        f"/estimate-options/00000000-0000-0000-0000-000000000000/addons",
        json={"addon_id": addon["id"]},
        headers=headers,
    )
    assert res.status_code == 404


def test_adding_nonexistent_addon_to_option_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    _, option_id = _create_option(client, headers, sport_key="tennis")

    res = client.post(
        f"/estimate-options/{option_id}/addons",
        json={"addon_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert res.status_code == 404


def test_remove_addon_from_option(client, director_user):
    headers = _director_headers(client, director_user)
    addon = _create_addon(client, headers, sport_keys=("tennis",))
    _, option_id = _create_option(client, headers, sport_key="tennis")
    row = client.post(f"/estimate-options/{option_id}/addons", json={"addon_id": addon["id"]}, headers=headers).json()

    del_res = client.delete(f"/estimate-option-addons/{row['id']}", headers=headers)
    assert del_res.status_code == 204

    list_res = client.get(f"/estimate-options/{option_id}/addons", headers=headers)
    assert list_res.json() == []


def test_removing_nonexistent_option_addon_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.delete("/estimate-option-addons/00000000-0000-0000-0000-000000000000", headers=headers)
    assert res.status_code == 404


def test_option_addons_strip_cost_and_margin_for_sales(client, db_session, director_user):
    director_headers = _director_headers(client, director_user)
    addon = _create_addon(client, director_headers, sport_keys=("tennis",))
    _, option_id = _create_option(client, director_headers, sport_key="tennis")

    sales_headers = _sales_headers(client, db_session)
    add_res = client.post(
        f"/estimate-options/{option_id}/addons", json={"addon_id": addon["id"]}, headers=sales_headers
    )
    assert add_res.status_code == 201, add_res.text
    assert add_res.json()["cost"] is None
    assert add_res.json()["margin_percent"] is None
    assert add_res.json()["selling_price"] is not None

    list_res = client.get(f"/estimate-options/{option_id}/addons", headers=sales_headers)
    assert list_res.json()[0]["cost"] is None
