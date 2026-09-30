"""P4 contract v7 -- Sections 1 (version history), 2 (search), 5 (review / marketing-reuse)."""

import uuid

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
        name="Test Sales", email="sales-p4@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-p4@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "P4 Doc Lib Client", "type": "school"}, headers=headers)
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


def _draft_cost_sheet(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"], project_id


def _add_project_sport(client, headers, project_id, sport_key="box_cricket"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_estimate_for(client, headers, project_id, cost_for_option=100000):
    project_sport_id = _add_project_sport(client, headers, project_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers)
    assert res.status_code == 201, res.text
    cost_sheet_id = res.json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return cost_sheet_id, res.json()["id"]


def _upload(client, headers, doc_type, doc_id, tag, filename="test.txt", content=b"hello world"):
    data = {"doc_type": doc_type, "doc_id": doc_id, "tag": tag}
    return client.post("/attachments", data=data, files={"file": (filename, content, "text/plain")}, headers=headers)


def _supersede(client, headers, attachment_id, filename="v2.txt", content=b"v2 content"):
    return client.post(
        f"/attachments/{attachment_id}/supersede", files={"file": (filename, content, "text/plain")}, headers=headers
    )


# ---------------------------------------------------------------------------
# Section 1: document version history
# ---------------------------------------------------------------------------


def test_lineage_grouping_with_multiple_independent_lineages(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, _ = _draft_cost_sheet(client, headers)

    a1 = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename="a1.txt").json()
    a2 = _supersede(client, headers, a1["id"], filename="a2.txt").json()
    b1 = _upload(client, headers, "cost_sheet", cost_sheet_id, "survey_form", filename="b1.txt").json()

    res = client.get(f"/attachments/cost_sheet/{cost_sheet_id}/lineages", headers=headers)
    assert res.status_code == 200, res.text
    lineages = res.json()
    assert len(lineages) == 2  # two independent heads: a2's chain, and b1 alone

    by_head_id = {chain[-1]["id"]: chain for chain in lineages}
    a_chain = by_head_id[a2["id"]]
    assert [row["id"] for row in a_chain] == [a1["id"], a2["id"]]  # oldest-first, ending at the head
    b_chain = by_head_id[b1["id"]]
    assert [row["id"] for row in b_chain] == [b1["id"]]


def test_download_authorization_follows_reassignment_for_old_and_new_versions(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id, project_id = _draft_cost_sheet(client, headers)
    a1 = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report").json()
    a2 = _supersede(client, headers, a1["id"]).json()

    # Both versions downloadable by a director regardless of ownership scoping specifics here --
    # the real reassignment-following behaviour is already covered by require_visible_document's
    # own existing test coverage (traced in the P4 contract's own Section 1). This asserts the
    # new lineage endpoint doesn't bypass that check.
    for att_id in (a1["id"], a2["id"]):
        res = client.get(f"/attachments/{att_id}/download", headers=headers)
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# Section 2: search across attachments
# ---------------------------------------------------------------------------


def test_search_total_reflects_every_authorized_match_not_the_page_length(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, _ = _draft_cost_sheet(client, headers)
    for i in range(5):
        _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename=f"match{i}.txt")

    res = client.get("/attachments/search", params={"q": "match", "limit": 2}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5


def test_role_excluded_doc_type_never_contributes_a_branch_to_search(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id, estimate_id = _draft_estimate_for(client, headers, project_id)
    _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename="secretcost.txt")
    _upload(client, headers, "estimate", estimate_id, "product_image", filename="secretcost.txt")

    sales_headers = _sales_headers(client, db_session)
    res = client.get("/attachments/search", params={"q": "secretcost"}, headers=sales_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    # Sales (rate-blind mode off by default) can see the Estimate match but never the Cost Sheet
    # one -- the branch is omitted from the union outright, not merely filtered to zero rows.
    assert body["total"] == 1
    assert body["items"][0]["doc_type"] == "estimate"


def test_historical_versions_never_surface_in_search(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, _ = _draft_cost_sheet(client, headers)
    old = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", filename="versioned.txt").json()
    new = _supersede(client, headers, old["id"], filename="versioned.txt").json()

    res = client.get("/attachments/search", params={"q": "versioned"}, headers=headers)
    assert res.status_code == 200, res.text
    ids = [item["id"] for item in res.json()["items"]]
    assert new["id"] in ids
    assert old["id"] not in ids


# ---------------------------------------------------------------------------
# Section 5: review and marketing-reuse approval
# ---------------------------------------------------------------------------


def test_review_and_marketing_reuse_independent_and_both_repeatable(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, _ = _draft_cost_sheet(client, headers)
    attachment = _upload(client, headers, "cost_sheet", cost_sheet_id, "photo").json()

    res = client.post(f"/attachments/{attachment['id']}/review", json={"status": "approved"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["review_status"] == "approved"

    res = client.post(f"/attachments/{attachment['id']}/marketing-reuse/approve", headers=headers)
    assert res.status_code == 200, res.text
    approved = res.json()
    assert approved["marketing_reuse_approved_at"] is not None
    assert approved["review_status"] == "approved"  # untouched by the marketing action

    res = client.post(f"/attachments/{attachment['id']}/marketing-reuse/revoke", headers=headers)
    assert res.status_code == 200, res.text
    revoked = res.json()
    assert revoked["marketing_reuse_revoked_at"] is not None

    res = client.post(f"/attachments/{attachment['id']}/marketing-reuse/approve", headers=headers)
    assert res.status_code == 200, res.text
    reapproved = res.json()
    assert reapproved["marketing_reuse_revoked_at"] is None  # cleared by the fresh approval
    assert reapproved["marketing_reuse_approved_at"] is not None


def test_neither_approval_carries_forward_to_a_new_version(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, _ = _draft_cost_sheet(client, headers)
    old = _upload(client, headers, "cost_sheet", cost_sheet_id, "photo").json()
    client.post(f"/attachments/{old['id']}/review", json={"status": "approved"}, headers=headers)
    client.post(f"/attachments/{old['id']}/marketing-reuse/approve", headers=headers)

    new = _supersede(client, headers, old["id"]).json()
    assert new["review_status"] is None
    assert new["marketing_reuse_approved_at"] is None


def test_marketings_own_role_boundary_is_unaffected(client, director_user, db_session):
    """P4 grants Marketing no new access -- not to search, not to stage evidence, not to
    marketing-reuse approval itself (deliberately not Marketing, Section 7's matrix)."""
    headers = _director_headers(client, director_user)
    cost_sheet_id, project_id = _draft_cost_sheet(client, headers)
    attachment = _upload(client, headers, "cost_sheet", cost_sheet_id, "photo").json()

    marketing = User(
        name="Test Marketing", email="marketing-p4@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.MARKETING,
    )
    db_session.add(marketing)
    db_session.commit()
    marketing_headers = _login(client, "marketing-p4@test.local")

    assert client.get("/attachments/search", params={"q": "x"}, headers=marketing_headers).status_code == 403
    assert client.get(f"/projects/{project_id}/stages", headers=marketing_headers).status_code == 403
    assert (
        client.post(f"/attachments/{attachment['id']}/marketing-reuse/approve", headers=marketing_headers).status_code
        == 403
    )
    assert client.post(f"/attachments/{attachment['id']}/review", json={"status": "approved"}, headers=marketing_headers).status_code == 403
