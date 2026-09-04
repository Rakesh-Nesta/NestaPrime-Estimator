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


def test_indoor_smooth_sport_recommends_pcc_base(client, director_user):
    """D.2: Badminton / TT / squash / gym in Existing or PEB -> PCC 4-6 in,
    alternative RCC 6 in."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id, building_status="new_peb_building")
    badminton_id = _sport_id(client, headers, "badminton")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": badminton_id, "building_status": "new_peb_building"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    base = res.json()["recommended_base"]
    assert base["recommended"] == "PCC 4-6 in"
    assert base["alternative"] == "RCC 6 in"


def test_turf_field_base_recommendation_depends_on_soil(client, director_user):
    """D.2: Box cricket / football turf, Open -- Normal soil = WBM,
    Rocky = RCC direct, Black cotton = sand + WBM + geotextile."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    football_id = _sport_id(client, headers, "football_11")

    for soil, expected_recommended in [
        ("normal", "WBM 8-10 in (+ PCC 4 in box)"),
        ("rocky", "RCC 6 in direct"),
        ("black_cotton", "Sand layer 6 in + WBM 10 in + geotextile"),
    ]:
        project_id = _create_project(client, headers, client_id, soil_type=soil)
        res = client.post(
            f"/projects/{project_id}/sports",
            json={"sport_id": football_id, "building_status": "open_air"},
            headers=headers,
        )
        assert res.json()["recommended_base"]["recommended"] == expected_recommended, soil


def test_swimming_pool_recommends_rcc_shell_regardless_of_context(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id, soil_type="sandy")
    pool_id = _sport_id(client, headers, "swimming_pool_25m")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": pool_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.json()["recommended_base"]["recommended"] == "RCC 8-12 in shell"


def test_sport_not_covered_by_d2_matrix_returns_no_base_recommendation(client, director_user):
    """Volleyball has no row in D.2's example matrix — must not fabricate one."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    volleyball_id = _sport_id(client, headers, "volleyball_indoor")

    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": volleyball_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.json()["recommended_base"] is None


def test_project_site_prep_triggers_match_soil_and_site_condition(client, director_user):
    """D.4/B.2: rocky soil -> rock breaking, black cotton -> sand+CNS,
    water-logged site -> dewatering; none of these leak into unrelated cases."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)

    rocky_id = _create_project(client, headers, client_id, soil_type="rocky")
    res = client.get(f"/projects/{rocky_id}", headers=headers)
    body = res.json()
    assert body["rock_breaking_required"] is True
    assert body["dewatering_required"] is False
    assert body["sand_cns_layer_required"] is False

    black_cotton_id = _create_project(client, headers, client_id, soil_type="black_cotton")
    body = client.get(f"/projects/{black_cotton_id}", headers=headers).json()
    assert body["sand_cns_layer_required"] is True
    assert body["rock_breaking_required"] is False

    waterlogged_id = _create_project(client, headers, client_id, site_condition="water_logged")
    body = client.get(f"/projects/{waterlogged_id}", headers=headers).json()
    assert body["dewatering_required"] is True
    assert body["rock_breaking_required"] is False
    assert body["sand_cns_layer_required"] is False


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
