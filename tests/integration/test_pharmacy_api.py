from helpers import register_patient


async def _medicine(client, **overrides) -> dict:
    body = {
        "name": "Paracetamol",
        "form": "tablet",
        "strength": "500 mg",
        "pack_size": "Strip of 10",
        "price_paise": 3500,
        "stock_quantity": 3,
        "reorder_level": 5,
        **overrides,
    }
    response = await client.post("/api/v1/admin/medicines", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def test_customers_see_availability_not_stock_and_can_order(admin_client) -> None:
    client = admin_client
    md = client.headers["Authorization"]
    paracetamol = await _medicine(client)
    empty = await _medicine(client, name="Cetirizine", strength="10 mg", stock_quantity=0)
    assert paracetamol["stock_quantity"] == 3 and paracetamol["low_stock"] is True

    patient = await register_patient(client, "pharmacy.patient@example.com")
    client.headers["Authorization"] = patient
    catalog = {m["name"]: m for m in (await client.get("/api/v1/medicines")).json()}
    assert catalog["Paracetamol"]["in_stock"] is True
    assert catalog["Cetirizine"]["in_stock"] is False
    assert "stock_quantity" not in catalog["Paracetamol"]
    assert (await client.get("/api/v1/admin/medicines")).status_code == 403

    out_of_stock = await client.put(f"/api/v1/cart/items/{empty['id']}", json={"quantity": 1})
    assert out_of_stock.status_code == 409
    too_many = await client.put(f"/api/v1/cart/items/{paracetamol['id']}", json={"quantity": 4})
    assert too_many.status_code == 409
    assert "3" not in too_many.json()["detail"]  # never leak the count
    cart = await client.put(f"/api/v1/cart/items/{paracetamol['id']}", json={"quantity": 2})
    assert cart.json()["total_paise"] == 7000
    assert "stock_quantity" not in cart.json()["items"][0]["medicine"]

    order = await client.post(
        "/api/v1/book/medicines",
        json={"delivery_address": "12 MG Road, Bengaluru 560001", "contact_phone": "9876543210"},
    )
    assert order.status_code == 201, order.text
    order = order.json()
    assert order["status"] == "pending_payment" and order["total_paise"] == 7000
    assert (await client.get("/api/v1/cart")).json()["items"] == []

    failed = await client.post(
        f"/api/v1/my/payments/{order['payment_id']}/pay",
        json={"method": "upi", "upi_id": "me@fail"},
    )
    assert failed.json()["status"] == "failed"
    paid = await client.post(
        f"/api/v1/my/payments/{order['payment_id']}/pay",
        json={"method": "upi", "upi_id": "me@okbank"},
    )
    assert paid.json()["status"] == "paid"
    assert (await client.get(f"/api/v1/my/orders/{order['id']}")).json()["status"] == "paid"

    # Stock was reserved at checkout; the pharmacist restocks and ships.
    client.headers["Authorization"] = md
    item = (await client.get(f"/api/v1/admin/medicines/{paracetamol['id']}")).json()
    assert item["stock_quantity"] == 1
    restocked = await client.post(
        f"/api/v1/admin/medicines/{paracetamol['id']}/restock",
        json={"quantity": 50, "batch_number": "B-1029", "expiry_date": "2028-01-31"},
    )
    assert restocked.json()["stock_quantity"] == 51
    movements = (await client.get(f"/api/v1/admin/medicines/{paracetamol['id']}/movements")).json()
    assert [m["reason"] for m in movements][:2] == ["restock", "sale"]
    assert (
        await client.post(
            f"/api/v1/admin/medicine-orders/{order['id']}/status", json={"status": "delivered"}
        )
    ).status_code == 409
    packed = await client.post(
        f"/api/v1/admin/medicine-orders/{order['id']}/status", json={"status": "packed"}
    )
    assert packed.json()["status"] == "packed"

    # A second order cancelled by the customer returns its stock and refunds the payment.
    client.headers["Authorization"] = patient
    await client.put(f"/api/v1/cart/items/{paracetamol['id']}", json={"quantity": 5})
    second = (
        await client.post(
            "/api/v1/book/medicines",
            json={
                "delivery_address": "12 MG Road, Bengaluru 560001",
                "contact_phone": "9876543210",
            },
        )
    ).json()
    await client.post(
        f"/api/v1/my/payments/{second['payment_id']}/pay",
        json={"method": "card", "card_number": "4111 1111 1111 1111"},
    )
    cancelled = await client.post(f"/api/v1/my/orders/{second['id']}/cancel")
    assert cancelled.json()["status"] == "cancelled"
    payment = (await client.get(f"/api/v1/my/payments/{second['payment_id']}")).json()
    assert payment["status"] == "refunded"
    assert (await client.post(f"/api/v1/my/orders/{order['id']}/cancel")).status_code == 409

    client.headers["Authorization"] = md
    item = (await client.get(f"/api/v1/admin/medicines/{paracetamol['id']}")).json()
    assert item["stock_quantity"] == 51
