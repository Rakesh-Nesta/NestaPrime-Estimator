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


def test_lineages_authorization_follows_reassignment(client, director_user, db_session):
    """Direct cross-owner refusal test for GET /attachments/{doc_type}/{doc_id}/lineages --
    exercises BOTH the endpoint's own inline ownership.require_visible_document call AND the
    global enforce_own_records middleware's doc_id branch (app/core/ownership.py), which resolves
    doc_id against its sibling doc_type path param. Added because test_own_records.py's generic
    two-sales walk cannot build a doc_id/doc_type pair itself and has to skip these routes --
    this test is what actually proves the reassignment-refusal behaviour for them, same as the
    download/supersede tests above do for their own routes."""
    from tests.test_quotations_admin import _add_project_sport, _create_client_record, _create_project, _role_headers

    director = _director_headers(client, director_user)
    assert client.put("/ownership/switch", json={"on": True}, headers=director).status_code == 200

    sales_a = _role_headers(client, db_session, UserRole.SALES, "sales-a-lineages-reassign@test.local")
    sales_b = _role_headers(client, db_session, UserRole.SALES, "sales-b-lineages-reassign@test.local")
    a_id = client.get("/auth/me", headers=sales_a).json()["id"]
    b_id = client.get("/auth/me", headers=sales_b).json()["id"]

    client_id = _create_client_record(client, director, "Lineages Reassignment Client")
    project_id = _create_project(client, director, client_id)
    project_sport_id = _add_project_sport(client, director, project_id, "box_cricket")
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=director
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=director)
    estimate_id = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director,
    ).json()["id"]
    client.patch(f"/ownership/client/{client_id}", json={"owner_id": a_id, "cascade": True}, headers=director)

    up = _upload(client, sales_a, "estimate", estimate_id, "product_image")
    assert up.status_code == 201, up.text

    res = client.get(f"/attachments/estimate/{estimate_id}/lineages", headers=sales_a)
    assert res.status_code == 200, res.text  # A still owns it

    client.patch(f"/ownership/client/{client_id}", json={"owner_id": b_id, "cascade": True}, headers=director)

    res = client.get(f"/attachments/estimate/{estimate_id}/lineages", headers=sales_a)
    assert res.status_code == 404, res.text  # Amendment 60's concealed NOT_FOUND, not 403

    res = client.get(f"/attachments/estimate/{estimate_id}/lineages", headers=sales_b)
    assert res.status_code == 200, res.text  # B, the new owner, can see it


def test_download_authorization_follows_reassignment_for_old_and_new_versions(client, director_user, db_session):
    """Case 2's actual claim: once the parent Client (and its cascaded Project) is reassigned
    away from Sales A to Sales B, A loses download access to BOTH the original (superseded) and
    the current version of an attachment uploaded against that project -- not just the current
    one -- and B gains it. A session id or attachment id alone is never sufficient; the document's
    current ownership is what's checked, same contract as Case 20's upload-session coverage."""
    from tests.test_quotations_admin import _add_project_sport, _create_client_record, _create_project, _role_headers

    director = _director_headers(client, director_user)
    assert client.put("/ownership/switch", json={"on": True}, headers=director).status_code == 200

    sales_a = _role_headers(client, db_session, UserRole.SALES, "sales-a-dl-reassign@test.local")
    sales_b = _role_headers(client, db_session, UserRole.SALES, "sales-b-dl-reassign@test.local")
    a_id = client.get("/auth/me", headers=sales_a).json()["id"]
    b_id = client.get("/auth/me", headers=sales_b).json()["id"]

    # estimate, not cost_sheet -- Sales needs rate-blind mode on to attach to a Cost Sheet (a
    # separate, pre-existing business rule unrelated to ownership), same choice Case 20's own
    # upload-session reassignment test made.
    client_id = _create_client_record(client, director, "Download Reassignment Client")
    project_id = _create_project(client, director, client_id)
    project_sport_id = _add_project_sport(client, director, project_id, "box_cricket")
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=director
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=director)
    estimate_id = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director,
    ).json()["id"]
    give = client.patch(f"/ownership/client/{client_id}", json={"owner_id": a_id, "cascade": True}, headers=director)
    assert give.status_code == 200, give.text  # the project (and estimate) follow the client

    up1 = _upload(client, sales_a, "estimate", estimate_id, "product_image")
    assert up1.status_code == 201, up1.text
    a1 = up1.json()
    sup1 = _supersede(client, sales_a, a1["id"])
    assert sup1.status_code == 201, sup1.text
    a2 = sup1.json()

    # While A still owns it, both versions are downloadable.
    for att_id in (a1["id"], a2["id"]):
        res = client.get(f"/attachments/{att_id}/download", headers=sales_a)
        assert res.status_code == 200, res.text

    reassign = client.patch(f"/ownership/client/{client_id}", json={"owner_id": b_id, "cascade": True}, headers=director)
    assert reassign.status_code == 200, reassign.text

    # A is now refused on BOTH versions -- the old (superseded) one is not exempt just because
    # it's no longer current.
    for att_id in (a1["id"], a2["id"]):
        res = client.get(f"/attachments/{att_id}/download", headers=sales_a)
        assert res.status_code == 404, res.text  # Amendment 60's concealed NOT_FOUND, not 403

    # B, the new owner, can download both.
    for att_id in (a1["id"], a2["id"]):
        res = client.get(f"/attachments/{att_id}/download", headers=sales_b)
        assert res.status_code == 200, res.text


def test_supersede_authorization_follows_reassignment(client, director_user, db_session):
    """Found while closing Case 2: supersede_attachment had no ownership.require_visible_document
    call at all (only the role gate) -- A kept the ability to supersede an attachment on a project
    reassigned away from them. Fixed in app/api/attachments.py; this proves A is refused and B,
    the new owner, can supersede normally."""
    from tests.test_quotations_admin import _add_project_sport, _create_client_record, _create_project, _role_headers

    director = _director_headers(client, director_user)
    assert client.put("/ownership/switch", json={"on": True}, headers=director).status_code == 200

    sales_a = _role_headers(client, db_session, UserRole.SALES, "sales-a-supersede-reassign@test.local")
    sales_b = _role_headers(client, db_session, UserRole.SALES, "sales-b-supersede-reassign@test.local")
    a_id = client.get("/auth/me", headers=sales_a).json()["id"]
    b_id = client.get("/auth/me", headers=sales_b).json()["id"]

    client_id = _create_client_record(client, director, "Supersede Reassignment Client")
    project_id = _create_project(client, director, client_id)
    project_sport_id = _add_project_sport(client, director, project_id, "box_cricket")
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=director
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=director)
    estimate_id = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
        headers=director,
    ).json()["id"]
    client.patch(f"/ownership/client/{client_id}", json={"owner_id": a_id, "cascade": True}, headers=director)

    up1 = _upload(client, sales_a, "estimate", estimate_id, "product_image")
    assert up1.status_code == 201, up1.text
    a1 = up1.json()

    client.patch(f"/ownership/client/{client_id}", json={"owner_id": b_id, "cascade": True}, headers=director)

    res = client.post(
        f"/attachments/{a1['id']}/supersede", files={"file": ("v2.txt", b"v2 content", "text/plain")}, headers=sales_a,
    )
    assert res.status_code == 404, res.text  # A no longer owns the project; concealed NOT_FOUND

    res = client.post(
        f"/attachments/{a1['id']}/supersede", files={"file": ("v2.txt", b"v2 content", "text/plain")}, headers=sales_b,
    )
    assert res.status_code == 201, res.text  # B, the new owner, can supersede normally


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


def test_total_excludes_unauthorized_matches_at_the_contracts_own_scale(client, director_user, db_session):
    """Section 8 case 3's own exact scenario: 30 authorized matches and 10 unauthorized ones
    (Amendment 60 scoping on), search with limit=10. Expected: exactly 10 rows returned,
    total=30 -- proving total comes from the fully-authorized, fully-filtered set, not merely
    decoupled from the page length (already covered above) and not merely excluding an entire
    role-excluded doc_type (also already covered above) -- here the unauthorized matches are the
    SAME doc_type, same role, excluded purely by ownership."""
    from tests.test_quotations_admin import _add_project_sport, _create_client_record, _create_project, _role_headers

    director = _director_headers(client, director_user)
    assert client.put("/ownership/switch", json={"on": True}, headers=director).status_code == 200

    sales_a = _role_headers(client, db_session, UserRole.SALES, "sales-a-total-scale@test.local")
    sales_b = _role_headers(client, db_session, UserRole.SALES, "sales-b-total-scale@test.local")
    a_id = client.get("/auth/me", headers=sales_a).json()["id"]
    b_id = client.get("/auth/me", headers=sales_b).json()["id"]

    def _project_owned_by(owner_id, label):
        client_id = _create_client_record(client, director, f"Total-Scale {label} Client")
        project_id = _create_project(client, director, client_id)
        project_sport_id = _add_project_sport(client, director, project_id, "box_cricket")
        cost_sheet_id = client.post(
            f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=director
        ).json()["id"]
        client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=director)
        estimate_id = client.post(
            f"/projects/{project_id}/estimates",
            json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 100000}]},
            headers=director,
        ).json()["id"]
        give = client.patch(f"/ownership/client/{client_id}", json={"owner_id": owner_id, "cascade": True}, headers=director)
        assert give.status_code == 200, give.text
        return estimate_id

    authorized_estimate_id = _project_owned_by(a_id, "Authorized")
    unauthorized_estimate_id = _project_owned_by(b_id, "Unauthorized")

    for i in range(30):
        res = _upload(client, sales_a, "estimate", authorized_estimate_id, "product_image", filename=f"scopetest{i}.jpg")
        assert res.status_code == 201, res.text
    for i in range(10):
        res = _upload(client, sales_b, "estimate", unauthorized_estimate_id, "product_image", filename=f"scopetest-b{i}.jpg")
        assert res.status_code == 201, res.text

    res = client.get("/attachments/search", params={"q": "scopetest", "limit": 10}, headers=sales_a)
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["items"]) == 10
    assert body["total"] == 30  # not 40 -- the 10 unauthorized matches never entered the count


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


def test_price_request_attachments_searchable_globally_for_roles_with_unconditional_access(
    client, director_user, db_session,
):
    """PriceRequest has no project_id and no reliable indirect Project link (P2 correction plan)
    -- that constrains the JOIN, not who may search it. PRICE_REQUEST_ROLES (pm/director/
    procurement) are never ownership-scoped (SCOPED_ROLES is sales-only), so today, via the
    ordinary attachment endpoints, all three already see every price_request attachment
    unconditionally. Search must preserve that, not silently narrow it to zero results."""
    from tests.test_vendor_price_requests import _create_price_request, _create_rate_item, _create_vendor

    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)

    res = _upload(client, headers, "price_request", pr["id"], "vendor_quote", filename="pricequote123.pdf")
    assert res.status_code == 201, res.text

    res = client.get("/attachments/search", params={"q": "pricequote123"}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 1
    assert body["items"][0]["doc_type"] == "price_request"

    # Sales is excluded -- not because of this search feature, but because Sales was never in
    # PRICE_REQUEST_ROLES to begin with (the role gate, unrelated to the project-join question).
    sales_headers = _sales_headers(client, db_session)
    res = client.get("/attachments/search", params={"q": "pricequote123"}, headers=sales_headers)
    assert res.status_code == 200, res.text
    assert res.json()["total"] == 0


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
