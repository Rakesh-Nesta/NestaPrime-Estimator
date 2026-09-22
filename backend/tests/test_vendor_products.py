"""Amendment 7: vendor_code on Vendor, and Product (a vendor's own catalog
reference -- "products with approximate pricing under each vendor")."""

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
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_vendor(client, headers, name="Steel Traders", **overrides):
    payload = {"name": name, **overrides}
    res = client.post("/vendors", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_product(client, headers, vendor_id, name="MS Angle 40x40x5mm", **overrides):
    payload = {"name": name, "unit": "kg", "approx_price": 62.5, **overrides}
    res = client.post(f"/vendors/{vendor_id}/products", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_vendor_can_be_created_and_updated_with_a_code(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/vendors", json={"name": "Steel Traders", "vendor_code": "V-001"}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["vendor_code"] == "V-001"

    vendor_id = res.json()["id"]
    update_res = client.patch(f"/vendors/{vendor_id}", json={"vendor_code": "V-002"}, headers=headers)
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["vendor_code"] == "V-002"


def test_vendor_code_defaults_to_none(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers)
    res = client.get(f"/vendors/{vendor_id}", headers=headers)
    assert res.json()["vendor_code"] is None


def test_product_created_under_a_vendor_and_listed(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers)
    product = _create_product(client, headers, vendor_id, spec="ISMB grade", category="Structural steel")

    assert product["vendor_id"] == vendor_id
    assert product["approx_price"] == 62.5
    assert product["spec"] == "ISMB grade"

    list_res = client.get(f"/vendors/{vendor_id}/products", headers=headers)
    assert list_res.status_code == 200, list_res.text
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["name"] == "MS Angle 40x40x5mm"


def test_product_under_nonexistent_vendor_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/vendors/00000000-0000-0000-0000-000000000000/products",
        json={"name": "Whatever"},
        headers=headers,
    )
    assert res.status_code == 404


def test_product_can_be_updated_and_deleted(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers)
    product = _create_product(client, headers, vendor_id)
    product_id = product["id"]

    update_res = client.patch(f"/products/{product_id}", json={"approx_price": 70.0}, headers=headers)
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["approx_price"] == 70.0

    delete_res = client.delete(f"/products/{product_id}", headers=headers)
    assert delete_res.status_code == 204

    list_res = client.get(f"/vendors/{vendor_id}/products", headers=headers)
    assert list_res.json() == []


def test_updating_nonexistent_product_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/products/00000000-0000-0000-0000-000000000000", json={"approx_price": 1.0}, headers=headers
    )
    assert res.status_code == 404


def test_sales_cannot_access_vendors_or_products(client, db_session, director_user):
    """M.4: Sales has no reason to see vendor relationships or pricing."""
    director_headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    assert client.get("/vendors", headers=sales_headers).status_code == 403
    assert client.post("/vendors", json={"name": "X"}, headers=sales_headers).status_code == 403
    assert (
        client.post(f"/vendors/{vendor_id}/products", json={"name": "X"}, headers=sales_headers).status_code == 403
    )
    assert client.get(f"/vendors/{vendor_id}/products", headers=sales_headers).status_code == 403


def test_two_vendors_can_each_carry_their_own_product_catalog(client, director_user):
    """Distinct from RateItem (one flat rate, vendor-agnostic) -- two
    vendors can each have their own Product row for a similar item."""
    headers = _director_headers(client, director_user)
    vendor_a = _create_vendor(client, headers, name="Vendor A")
    vendor_b = _create_vendor(client, headers, name="Vendor B")
    _create_product(client, headers, vendor_a, name="Steel", approx_price=60.0)
    _create_product(client, headers, vendor_b, name="Steel", approx_price=65.0)

    a_products = client.get(f"/vendors/{vendor_a}/products", headers=headers).json()
    b_products = client.get(f"/vendors/{vendor_b}/products", headers=headers).json()
    assert a_products[0]["approx_price"] == 60.0
    assert b_products[0]["approx_price"] == 65.0


# ---------------------------------------------------------------------------
# Amendment 34: deactivation + duplicate-vendor guard
# ---------------------------------------------------------------------------


def test_vendor_is_active_defaults_to_true(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers)
    res = client.get(f"/vendors/{vendor_id}", headers=headers)
    assert res.json()["is_active"] is True


def test_vendor_can_be_deactivated_and_reactivated(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers)

    res = client.patch(f"/vendors/{vendor_id}", json={"is_active": False}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is False

    res = client.patch(f"/vendors/{vendor_id}", json={"is_active": True}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is True


def test_deactivated_vendor_excluded_from_default_listing(client, director_user):
    headers = _director_headers(client, director_user)
    active_id = _create_vendor(client, headers, name="Active Vendor")
    inactive_id = _create_vendor(client, headers, name="Retired Vendor")
    client.patch(f"/vendors/{inactive_id}", json={"is_active": False}, headers=headers)

    default_listing = client.get("/vendors", headers=headers).json()
    assert {v["id"] for v in default_listing} == {active_id}

    full_listing = client.get("/vendors", params={"include_inactive": True}, headers=headers).json()
    assert {v["id"] for v in full_listing} == {active_id, inactive_id}

    # A deactivated vendor is still directly retrievable by id -- it's
    # retired, not deleted.
    res = client.get(f"/vendors/{inactive_id}", headers=headers)
    assert res.status_code == 200, res.text


def test_creating_a_vendor_with_a_duplicate_name_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _create_vendor(client, headers, name="Steel Traders")

    res = client.post("/vendors", json={"name": "Steel Traders"}, headers=headers)
    assert res.status_code == 409, res.text


def test_creating_a_vendor_with_a_duplicate_gstin_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _create_vendor(client, headers, name="Vendor One", gstin="27AAAAA0000A1Z5")

    res = client.post(
        "/vendors", json={"name": "Vendor Two", "gstin": "27AAAAA0000A1Z5"}, headers=headers
    )
    assert res.status_code == 409, res.text


def test_two_unregistered_vendors_with_no_gstin_can_coexist(client, director_user):
    """gstin=None means 'unregistered' (Vendor's own docstring) -- not a
    duplicate just for sharing a null GSTIN."""
    headers = _director_headers(client, director_user)
    _create_vendor(client, headers, name="Vendor One")

    res = client.post("/vendors", json={"name": "Vendor Two"}, headers=headers)
    assert res.status_code == 201, res.text
