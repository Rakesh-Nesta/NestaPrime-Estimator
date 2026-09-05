def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_margin_policies_lists_all_seven_client_types_with_targets(client, director_user):
    headers = _login(client, director_user)
    res = client.get("/margin-policies", headers=headers)
    assert res.status_code == 200
    policies = {p["client_type"]: p for p in res.json()}
    assert len(policies) == 7

    # K.2: target = floor + (competitive_segment ? 3 : 5)
    assert policies["school"]["floor_margin_percent"] == 18.0
    assert policies["school"]["target_margin_percent"] == 21.0  # competitive: +3
    assert policies["housing_society"]["floor_margin_percent"] == 20.0
    assert policies["housing_society"]["target_margin_percent"] == 25.0  # not: +5
    assert policies["government"]["floor_margin_percent"] == 12.0
    assert policies["government"]["target_margin_percent"] == 15.0  # competitive: +3


def test_quote_matches_k2_worked_example_exactly(client, director_user):
    """K.2: 'cost Rs 8,50,000, selling Rs 10,00,000 -> markup 17.6%, margin
    15.0%.' Government's target margin is exactly 15% (floor 12 + 3), so
    cost 850000 / (1 - 0.15) lands on exactly 1,000,000 with zero discount --
    reproducing the blueprint's own numbers precisely."""
    headers = _login(client, director_user)
    res = client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 850000, "client_type": "government"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["target_margin_percent"] == 15.0
    assert round(body["selling_price_ex_gst"], 2) == 1000000.00
    assert round(body["margin_percent"], 1) == 15.0
    assert round(body["markup_percent"], 1) == 17.6
    assert body["below_floor"] is False


def test_gst_is_flat_eighteen_percent_on_subtotal(client, director_user):
    """K.1 step 11 / K.4: flat 18% GST, one line, on the subtotal after
    discount -- quotation_total = selling_after_discount * 1.18."""
    headers = _login(client, director_user)
    res = client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 850000, "client_type": "government"},
        headers=headers,
    )
    body = res.json()
    assert body["gst_rate_percent"] == 18.0
    assert round(body["gst_amount"], 2) == round(body["selling_after_discount"] * 0.18, 2)
    assert round(body["quotation_total"], 2) == round(body["selling_after_discount"] * 1.18, 2)


def test_percent_discount_reduces_selling_price_and_recheck_margin(client, director_user):
    """K.1 step 9-10: a discount is applied ex-GST, then margin is
    re-checked against the floor."""
    headers = _login(client, director_user)
    res = client.post(
        "/pricing/quote",
        json={
            "cost_incl_contingency": 850000,
            "client_type": "government",
            "discount_type": "percent",
            "discount_value": 10,
        },
        headers=headers,
    )
    body = res.json()
    assert round(body["discount_amount"], 2) == round(1000000 * 0.10, 2)
    assert round(body["selling_after_discount"], 2) == round(1000000 * 0.90, 2)
    # Margin after a 10% discount off a 15%-margin base price must be lower
    # than the undiscounted 15% and should trip the floor (12%) or not,
    # exactly per the recomputed formula -- just assert internal consistency.
    expected_margin = (body["selling_after_discount"] - 850000) / body["selling_after_discount"] * 100
    assert round(body["margin_percent"], 4) == round(expected_margin, 4)


def test_amount_discount_pushes_below_floor_and_flags_it(client, director_user):
    """K.1 step 10: below floor -> Director approval (surfaced as
    below_floor=True here; the approval workflow itself is a Part M
    document-state concern, not built yet)."""
    headers = _login(client, director_user)
    res = client.post(
        "/pricing/quote",
        json={
            "cost_incl_contingency": 850000,
            "client_type": "government",
            "discount_type": "amount",
            "discount_value": 200000,  # selling drops to 800000, below cost's own floor math
        },
        headers=headers,
    )
    body = res.json()
    assert body["selling_after_discount"] == 800000.0
    assert body["margin_percent"] < body["floor_margin_percent"]
    assert body["below_floor"] is True


def test_discount_to_zero_or_below_is_rejected(client, director_user):
    headers = _login(client, director_user)
    res = client.post(
        "/pricing/quote",
        json={
            "cost_incl_contingency": 850000,
            "client_type": "government",
            "discount_type": "amount",
            "discount_value": 2000000,
        },
        headers=headers,
    )
    assert res.status_code == 400


def test_pricing_requires_auth(client):
    res = client.post("/pricing/quote", json={"cost_incl_contingency": 100, "client_type": "school"})
    assert res.status_code == 401


def test_sales_cannot_access_pricing_or_margin_policies(client, db_session):
    """K.3: Sales never receives cost price, contingency, markup % or
    margin % -- enforced at the API."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    sales_user = User(
        name="Test Sales",
        email="sales@test.local",
        hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(sales_user)
    db_session.commit()

    login_res = client.post(
        "/auth/login", data={"username": "sales@test.local", "password": "TestPass!1"}
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    assert client.get("/margin-policies", headers=headers).status_code == 403
    assert client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 100, "client_type": "school"},
        headers=headers,
    ).status_code == 403
