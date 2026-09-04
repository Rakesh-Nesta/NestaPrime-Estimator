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


def _scope_item_id(client, headers, key):
    res = client.get("/scope-items", headers=headers)
    return next(s["id"] for s in res.json() if s["key"] == key)


def test_scope_items_lists_all_thirty_in_six_groups(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/scope-items", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 30
    assert [i["display_order"] for i in items] == list(range(1, 31))
    groups = {i["group"] for i in items}
    assert groups == {"civil", "electrical", "water", "external", "services", "maintenance"}


def test_new_project_has_no_scope_items_by_default(client, director_user):
    """I: 'unchecked = excluded' -- nothing is included until added."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)

    res = client.get(f"/projects/{project_id}/scope-items", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_add_list_and_remove_project_scope_item(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    cctv_id = _scope_item_id(client, headers, "cctv")

    add_res = client.post(
        f"/projects/{project_id}/scope-items",
        json={"scope_item_id": cctv_id},
        headers=headers,
    )
    assert add_res.status_code == 201, add_res.text
    selection_id = add_res.json()["id"]

    list_res = client.get(f"/projects/{project_id}/scope-items", headers=headers)
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["scope_item_id"] == cctv_id

    del_res = client.delete(f"/projects/{project_id}/scope-items/{selection_id}", headers=headers)
    assert del_res.status_code == 204

    list_res_after = client.get(f"/projects/{project_id}/scope-items", headers=headers)
    assert list_res_after.json() == []


def test_scope_item_note_is_stored(client, director_user):
    """Pavilion/gallery + seating count -- the note field carries the extra
    detail the checklist item itself calls out."""
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    pavilion_id = _scope_item_id(client, headers, "pavilion_gallery")

    res = client.post(
        f"/projects/{project_id}/scope-items",
        json={"scope_item_id": pavilion_id, "note": "200 seats"},
        headers=headers,
    )
    assert res.json()["note"] == "200 seats"


def test_adding_same_scope_item_twice_is_rejected(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    cctv_id = _scope_item_id(client, headers, "cctv")

    client.post(f"/projects/{project_id}/scope-items", json={"scope_item_id": cctv_id}, headers=headers)
    res = client.post(f"/projects/{project_id}/scope-items", json={"scope_item_id": cctv_id}, headers=headers)
    assert res.status_code == 400


def test_add_scope_item_to_unknown_project_is_rejected(client, director_user):
    headers = _login(client, director_user)
    cctv_id = _scope_item_id(client, headers, "cctv")
    res = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/scope-items",
        json={"scope_item_id": cctv_id},
        headers=headers,
    )
    assert res.status_code == 404


def test_add_unknown_scope_item_is_rejected(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(
        f"/projects/{project_id}/scope-items",
        json={"scope_item_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert res.status_code == 404


def test_create_scope_item_requires_auth(client):
    res = client.get("/scope-items")
    assert res.status_code == 401
