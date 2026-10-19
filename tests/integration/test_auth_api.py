async def test_root_endpoint(client) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"
    assert response.json()["health"] == "/health/live"


async def test_liveness_endpoint(client) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_patient_registration_login_and_self_service(client) -> None:
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new.patient@example.com",
            "password": "long-enough-test-password",
            "full_name": "New Patient",
            "date_of_birth": "1988-08-08",
        },
    )
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "patient"

    patient_record = await client.get("/api/v1/profile")
    assert patient_record.status_code == 200
    assert patient_record.json()["full_name"] == "New Patient"

    updated_record = await client.patch("/api/v1/profile", json={"phone": "+1-555-0199"})
    assert updated_record.status_code == 200
    assert updated_record.json()["phone"] == "+1-555-0199"

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "new.patient@example.com", "password": "long-enough-test-password"},
    )
    assert login.status_code == 200


async def test_invalid_login_is_unauthorized(client) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "bad-password"},
    )

    assert response.status_code == 401


async def test_staff_creation_cannot_make_unlinked_patient(admin_client) -> None:
    response = await admin_client.post(
        "/api/v1/admin/staff/accounts",
        json={
            "email": "unlinked.patient@example.com",
            "password": "long-enough-test-password",
            "role": "patient",
        },
    )

    assert response.status_code == 422


async def test_customer_and_staff_sign_in_through_separate_doors(admin_client) -> None:
    await admin_client.post(
        "/api/v1/admin/staff/accounts",
        json={
            "email": "door.staff@example.com",
            "password": "door-staff-password-1",
            "role": "admin",
        },
    )
    await admin_client.post(
        "/api/v1/auth/register",
        json={
            "email": "door.patient@example.com",
            "password": "door-patient-password-1",
            "full_name": "Door Patient",
            "date_of_birth": "1990-01-01",
        },
    )
    staff = {"email": "door.staff@example.com", "password": "door-staff-password-1"}
    patient = {"email": "door.patient@example.com", "password": "door-patient-password-1"}
    login = "/api/v1/auth/login"

    assert (await admin_client.post(login, json={**staff, "audience": "staff"})).status_code == 200
    wrong_door = await admin_client.post(login, json={**staff, "audience": "customer"})
    assert wrong_door.status_code == 403
    assert "admin login" in wrong_door.json()["detail"]

    assert (
        await admin_client.post(login, json={**patient, "audience": "customer"})
    ).status_code == 200
    assert (
        await admin_client.post(login, json={**patient, "audience": "staff"})
    ).status_code == 403
    # A wrong password stays a plain 401, without revealing which door the account belongs to.
    bad = await admin_client.post(login, json={**patient, "password": "nope", "audience": "staff"})
    assert bad.status_code == 401
