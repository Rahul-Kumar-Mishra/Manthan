from uuid import uuid4

from helpers import PASSWORD, login, register_patient, staff_account

from app.main import app


def test_every_staff_operation_lives_under_admin() -> None:
    paths = app.openapi()["paths"]
    for path in paths:
        if any(word in path for word in ("/access", "/staff", "/inventory", "/restock", "/refund")):
            assert path.startswith("/api/v1/admin/"), path
    # The old mixed-audience routes are gone.
    for old in (
        "/api/v1/appointments",
        "/api/v1/pharmacy/inventory",
        "/api/v1/leaves",
        "/api/v1/auth/users",
    ):
        assert old not in paths


async def test_audiences_cannot_cross_over(admin_client) -> None:
    client = admin_client
    md = client.headers["Authorization"]

    patient = await register_patient(client, "layout.patient@example.com")
    client.headers["Authorization"] = patient
    assert (await client.get("/api/v1/admin/medicines")).status_code == 403
    assert (await client.get("/api/v1/admin/access/me")).status_code == 403
    assert (await client.get("/api/v1/doctor/appointments")).status_code == 403
    assert (await client.get("/api/v1/my/appointments")).status_code == 200
    assert (await client.get("/api/v1/pharmacy/inventory")).status_code == 404

    # Staff use /admin; customer routes refuse them.
    client.headers["Authorization"] = md
    assert (await client.get("/api/v1/my/appointments")).status_code == 403
    assert (await client.get("/api/v1/cart")).status_code == 403

    # An admin account with no modules can see its (empty) access but nothing else.
    _, plain = await staff_account(client, md, "plain.admin@example.com")
    client.headers["Authorization"] = plain
    assert (await client.get("/api/v1/admin/access/me")).json()["modules"] == []
    assert (await client.get("/api/v1/admin/doctors")).status_code == 200  # directory is readable
    assert (await client.post("/api/v1/admin/doctors", json={})).status_code == 403
    assert (await client.delete(f"/api/v1/admin/hospitals/{uuid4()}")).status_code == 403
    assert (await client.get("/api/v1/admin/medicine-orders")).status_code == 403

    # Doctors stay in /doctor.
    client.headers["Authorization"] = md
    account = await client.post(
        "/api/v1/admin/staff/accounts",
        json={"email": "layout.doctor@example.com", "password": PASSWORD, "role": "doctor"},
    )
    assert account.status_code == 201
    client.headers["Authorization"] = await login(client, "layout.doctor@example.com")
    assert (await client.get("/api/v1/admin/appointments")).status_code == 403
    assert (await client.get("/api/v1/doctor/leaves")).status_code == 404  # no profile linked yet


async def test_catalogue_is_shared_but_stock_is_admin_only(admin_client) -> None:
    client = admin_client
    created = await client.post(
        "/api/v1/admin/medicines",
        json={"name": "Layout Med", "form": "tablet", "price_paise": 100, "stock_quantity": 7},
    )
    assert created.json()["stock_quantity"] == 7
    client.headers["Authorization"] = await register_patient(client, "catalogue@example.com")
    item = (await client.get(f"/api/v1/medicines/{created.json()['id']}")).json()
    assert item["in_stock"] is True and "stock_quantity" not in item
