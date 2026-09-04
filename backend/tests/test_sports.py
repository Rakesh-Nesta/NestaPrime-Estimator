def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client(client, headers, client_type="school", name="Test School"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
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
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sport_id(client, headers, key):
    res = client.get("/sports", headers=headers)
    return next(s["id"] for s in res.json() if s["key"] == key)


def test_sports_lists_all_thirty_in_c1_c2_order(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/sports", headers=headers)
    assert res.status_code == 200
    sports = res.json()
    assert len(sports) == 30
    assert [s["display_order"] for s in sports] == list(range(1, 31))
    assert sports[0]["key"] == "badminton"
    assert sports[0]["min_clear_height_ft"] == 24.0
    assert sports[0]["category"] == "indoor"


def test_outdoor_sports_have_no_min_clear_height(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/sports", headers=headers)
    football = next(s for s in res.json() if s["key"] == "football_11")
    assert football["category"] == "outdoor"
    assert football["min_clear_height_ft"] is None


def test_add_sport_to_project_happy_path(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    badminton_id = _sport_id(client, headers, "badminton")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": badminton_id, "building_status": "open_air", "number_of_courts": 2},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["number_of_courts"] == 2
    assert body["clear_height_ok"] is True


def test_indoor_sport_blocked_when_existing_building_too_low(client, director_user):
    """B.1a: 'Min structure height: building height >= sport min' for
    Existing building — badminton needs 24 ft, a 20 ft building must be
    rejected."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(
        client,
        headers,
        client_id,
        building_status="existing_building",
        existing_building_clear_height_ft=20,
    )
    badminton_id = _sport_id(client, headers, "badminton")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": badminton_id, "building_status": "existing_building"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "24" in res.json()["detail"]


def test_indoor_sport_allowed_when_existing_building_tall_enough(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(
        client,
        headers,
        client_id,
        building_status="existing_building",
        existing_building_clear_height_ft=30,
    )
    badminton_id = _sport_id(client, headers, "badminton")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": badminton_id, "building_status": "existing_building"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["clear_height_ok"] is True


def test_outdoor_sport_never_blocked_by_clear_height(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(
        client,
        headers,
        client_id,
        building_status="existing_building",
        existing_building_clear_height_ft=5,
    )
    football_id = _sport_id(client, headers, "football_11")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": football_id, "building_status": "existing_building"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["clear_height_ok"] is True


def test_list_and_remove_project_sports(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    badminton_id = _sport_id(client, headers, "badminton")

    add_res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": badminton_id, "building_status": "open_air"},
        headers=headers,
    )
    selection_id = add_res.json()["id"]

    list_res = client.get(f"/projects/{project_id}/sports", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    del_res = client.delete(f"/projects/{project_id}/sports/{selection_id}", headers=headers)
    assert del_res.status_code == 204

    list_res_after = client.get(f"/projects/{project_id}/sports", headers=headers)
    assert list_res_after.json() == []


def test_add_sport_to_unknown_project_is_rejected(client, director_user):
    headers = _login(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")
    res = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/sports",
        json={"sport_id": badminton_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 404


def test_add_unknown_sport_is_rejected(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": "00000000-0000-0000-0000-000000000000", "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 404
