from datetime import UTC, datetime, timedelta

from helpers import register_patient


async def test_patient_books_lab_test_and_lab_staff_progress_it(admin_client) -> None:
    client = admin_client
    md = client.headers["Authorization"]
    test = await client.post(
        "/api/v1/admin/lab-tests",
        json={
            "code": "cbc",
            "name": "Complete Blood Count",
            "price_paise": 45000,
            "home_collection": True,
        },
    )
    assert test.status_code == 201 and test.json()["code"] == "CBC"
    no_home = await client.post(
        "/api/v1/admin/lab-tests", json={"code": "MRI", "name": "MRI Brain", "price_paise": 650000}
    )

    patient = await register_patient(client, "lab.patient@example.com")
    client.headers["Authorization"] = patient
    when = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    home_refused = await client.post(
        "/api/v1/book/lab-test",
        json={
            "lab_test_id": no_home.json()["id"],
            "scheduled_at": when,
            "collection_type": "home",
            "address": "12 MG Road, Bengaluru",
            "contact_phone": "9876543210",
        },
    )
    assert home_refused.status_code == 409
    booking = await client.post(
        "/api/v1/book/lab-test",
        json={
            "lab_test_id": test.json()["id"],
            "scheduled_at": when,
            "collection_type": "home",
            "address": "12 MG Road, Bengaluru",
            "contact_phone": "9876543210",
        },
    )
    assert booking.status_code == 201
    assert booking.json()["price_paise"] == 45000
    assert len((await client.get("/api/v1/my/lab-tests")).json()) == 1
    assert (await client.get("/api/v1/admin/lab-bookings")).status_code == 403

    client.headers["Authorization"] = md
    collected = await client.post(
        f"/api/v1/admin/lab-bookings/{booking.json()['id']}/status",
        json={"status": "sample_collected"},
    )
    assert collected.json()["status"] == "sample_collected"
    client.headers["Authorization"] = patient
    assert (
        await client.post(f"/api/v1/my/lab-tests/{booking.json()['id']}/cancel")
    ).status_code == 409


async def test_on_call_consultation_requires_online_payment(admin_client) -> None:
    client = admin_client
    md = client.headers["Authorization"]
    hospital = await client.post("/api/v1/admin/hospitals", json={"name": "Consult Hospital"})
    branch = await client.post(
        f"/api/v1/admin/hospitals/{hospital.json()['id']}/branches", json={"name": "Tele"}
    )
    offline = await client.post(
        "/api/v1/admin/doctors",
        json={"branch_id": branch.json()["id"], "full_name": "Dr Offline", "specialization": "ENT"},
    )
    missing_fee = await client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": branch.json()["id"],
            "full_name": "Dr NoFee",
            "specialization": "ENT",
            "available_online": True,
        },
    )
    assert missing_fee.status_code == 422
    online = await client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": branch.json()["id"],
            "full_name": "Dr Online",
            "specialization": "General Medicine",
            "experience_years": 12,
            "qualifications": "MBBS, MD",
            "consultation_fee_paise": 50000,
            "online_fee_paise": 40000,
            "available_online": True,
        },
    )
    assert online.json()["experience_years"] == 12

    patient = await register_patient(client, "consult.patient@example.com", phone="9876500000")
    client.headers["Authorization"] = patient
    start = datetime.now(UTC) + timedelta(days=1)
    slot = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(minutes=15)).isoformat()}
    refused = await client.post(
        "/api/v1/book/appointment",
        json={**slot, "doctor_id": offline.json()["id"], "mode": "online"},
    )
    assert refused.status_code == 409
    booked = await client.post(
        "/api/v1/book/appointment",
        json={**slot, "doctor_id": online.json()["id"], "mode": "online"},
    )
    assert booked.status_code == 201, booked.text
    appointment = booked.json()
    assert appointment["payment_status"] == "pending"
    assert appointment["fee_paise"] == 40000
    assert appointment["contact_phone"] == "9876500000"

    declined = await client.post(
        f"/api/v1/my/payments/{appointment['payment_id']}/pay",
        json={"method": "card", "card_number": "4000000000000002"},
    )
    assert declined.json()["status"] == "failed"
    paid = await client.post(
        f"/api/v1/my/payments/{appointment['payment_id']}/pay",
        json={"method": "netbanking", "bank": "HDFC"},
    )
    assert paid.json()["status"] == "paid"
    mine = (await client.get("/api/v1/my/appointments")).json()
    assert mine[0]["payment_status"] == "paid"

    # In-clinic visits don't need online payment.
    later = start + timedelta(hours=2)
    in_person = await client.post(
        "/api/v1/book/appointment",
        json={
            "doctor_id": online.json()["id"],
            "starts_at": later.isoformat(),
            "ends_at": (later + timedelta(minutes=15)).isoformat(),
        },
    )
    assert in_person.json()["payment_status"] == "not_required"
    assert in_person.json()["fee_paise"] == 50000

    # Cancelling the paid on-call visit refunds it.
    cancelled = await client.post(f"/api/v1/my/appointments/{appointment['id']}/cancel")
    assert cancelled.json()["payment_status"] == "refunded"
    client.headers["Authorization"] = md
    payments = (await client.get("/api/v1/admin/payments", params={"status": "refunded"})).json()
    assert [p["reference_id"] for p in payments] == [appointment["id"]]


async def test_staff_directory_offboarding_disables_access(admin_client) -> None:
    client = admin_client
    md = client.headers["Authorization"]
    account = await client.post(
        "/api/v1/admin/staff/accounts",
        json={
            "email": "nurse@example.com",
            "password": "integration-password-123",
            "role": "admin",
        },
    )
    await client.post(
        "/api/v1/admin/access/grants", json={"user_id": account.json()["id"], "module": "lab"}
    )
    member = await client.post(
        "/api/v1/admin/staff",
        json={
            "full_name": "Anita Nurse",
            "designation": "Staff Nurse",
            "department": "Nursing",
            "user_id": account.json()["id"],
            "joined_on": "2024-02-01",
        },
    )
    assert member.status_code == 201
    left = await client.post(f"/api/v1/admin/staff/{member.json()['id']}/offboard", json={})
    assert left.json()["status"] == "left"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "nurse@example.com", "password": "integration-password-123"},
    )
    assert login.status_code == 401
    staff = (await client.get("/api/v1/admin/access/staff")).json()
    nurse = next(row for row in staff if row["email"] == "nurse@example.com")
    assert nurse["grants"] == []
    assert md
