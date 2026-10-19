from datetime import UTC, datetime, timedelta

import httpx


async def _token(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


async def _setup(admin_client: httpx.AsyncClient) -> dict[str, str]:
    """Create a branch, a doctor with a login, and a registered patient."""
    admin_token = admin_client.headers["Authorization"]
    hospital = await admin_client.post(
        "/api/v1/admin/hospitals", json={"name": "Leave Test Hospital"}
    )
    branch = await admin_client.post(
        f"/api/v1/admin/hospitals/{hospital.json()['id']}/branches", json={"name": "Leave Branch"}
    )
    account = await admin_client.post(
        "/api/v1/admin/staff/accounts",
        json={
            "email": "leave.doctor@example.com",
            "password": "leave-doctor-password-123",
            "role": "doctor",
        },
    )
    assert account.status_code == 201
    doctor = await admin_client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": branch.json()["id"],
            "full_name": "Leave Test Doctor",
            "specialization": "General Practice",
            "user_id": account.json()["id"],
        },
    )
    assert doctor.status_code == 201
    registration = await admin_client.post(
        "/api/v1/auth/register",
        json={
            "email": "leave.patient@example.com",
            "password": "leave-patient-password-123",
            "full_name": "Leave Patient",
            "date_of_birth": "1990-02-02",
        },
    )
    assert registration.status_code == 201
    return {
        "admin": admin_token,
        "doctor": "Bearer "
        + await _token(admin_client, "leave.doctor@example.com", "leave-doctor-password-123"),
        "patient": "Bearer " + registration.json()["access_token"],
        "doctor_id": doctor.json()["id"],
    }


def _window(days_from_now: int, days: int = 1) -> tuple[datetime, datetime]:
    start = (datetime.now(UTC) + timedelta(days=days_from_now)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start, start + timedelta(days=days)


async def test_doctor_requests_and_admin_approves_leave_which_blocks_booking(
    admin_client: httpx.AsyncClient,
) -> None:
    ctx = await _setup(admin_client)
    client = admin_client
    leave_start, leave_end = _window(5, days=2)
    slot_start = leave_start + timedelta(hours=10)
    slot = {
        "doctor_id": ctx["doctor_id"],
        "starts_at": slot_start.isoformat(),
        "ends_at": (slot_start + timedelta(minutes=30)).isoformat(),
    }

    # Patient books a slot that will later fall inside the leave.
    client.headers["Authorization"] = ctx["patient"]
    booked = await client.post("/api/v1/book/appointment", json=slot)
    assert booked.status_code == 201

    # Doctor files a request; it starts pending and does not yet block booking.
    client.headers["Authorization"] = ctx["doctor"]
    request = await client.post(
        "/api/v1/doctor/leaves",
        json={
            "starts_at": leave_start.isoformat(),
            "ends_at": leave_end.isoformat(),
            "reason": "Medical conference",
        },
    )
    assert request.status_code == 201
    leave = request.json()
    assert leave["status"] == "pending"
    assert leave["doctor_id"] == ctx["doctor_id"]
    assert [item["id"] for item in (await client.get("/api/v1/doctor/leaves")).json()] == [
        leave["id"]
    ]
    overlapping = await client.post(
        "/api/v1/doctor/leaves",
        json={
            "starts_at": (leave_start + timedelta(hours=1)).isoformat(),
            "ends_at": leave_end.isoformat(),
            "reason": "Duplicate",
        },
    )
    assert overlapping.status_code == 409
    assert (await client.post(f"/api/v1/admin/leaves/{leave['id']}/approve")).status_code == 403

    # Admin sees it as pending, approves it, and reviews affected appointments.
    client.headers["Authorization"] = ctx["admin"]
    pending = await client.get("/api/v1/admin/leaves", params={"status": "pending"})
    assert [item["id"] for item in pending.json()] == [leave["id"]]
    approved = await client.post(
        f"/api/v1/admin/leaves/{leave['id']}/approve", json={"note": "Covered by Dr. B"}
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["review_note"] == "Covered by Dr. B"
    assert (await client.post(f"/api/v1/admin/leaves/{leave['id']}/reject")).status_code == 409

    upcoming = await client.get("/api/v1/admin/leaves", params={"scope": "upcoming"})
    assert [item["id"] for item in upcoming.json()] == [leave["id"]]
    assert (await client.get("/api/v1/admin/leaves", params={"scope": "current"})).json() == []

    affected = await client.get(f"/api/v1/admin/leaves/{leave['id']}/appointments")
    assert [item["id"] for item in affected.json()] == [booked.json()["id"]]

    # Approved leave now blocks new bookings and shows up as a blocked window.
    client.headers["Authorization"] = ctx["patient"]
    later = slot_start + timedelta(hours=2)
    later_slot = {
        **slot,
        "starts_at": later.isoformat(),
        "ends_at": (later + timedelta(minutes=30)).isoformat(),
    }
    availability = await client.get("/api/v1/book/appointment/availability", params=later_slot)
    assert availability.json()["available"] is False
    assert availability.json()["reason"] == "Doctor is on leave during this time"
    blocked = await client.post("/api/v1/book/appointment", json=later_slot)
    assert blocked.status_code == 409
    windows = await client.get(f"/api/v1/doctors/{ctx['doctor_id']}/unavailability")
    assert windows.status_code == 200
    assert "reason" not in windows.json()[0]
    assert (await client.get("/api/v1/admin/leaves")).status_code == 403

    # Admin clears the affected appointments with a reason the patient can read.
    client.headers["Authorization"] = ctx["admin"]
    missing_reason = await client.post(
        f"/api/v1/admin/leaves/{leave['id']}/cancel-appointments", json={"reason": ""}
    )
    assert missing_reason.status_code == 422
    cleared = await client.post(
        f"/api/v1/admin/leaves/{leave['id']}/cancel-appointments",
        json={"reason": "Doctor on approved leave"},
    )
    assert cleared.status_code == 200
    assert cleared.json()[0]["status"] == "cancelled"
    assert cleared.json()[0]["cancelled_by_role"] == "admin"

    client.headers["Authorization"] = ctx["patient"]
    mine = (await client.get("/api/v1/my/appointments")).json()
    assert mine[0]["cancellation_reason"] == "Doctor on approved leave"

    # Doctor withdraws the leave; the slot opens up again.
    client.headers["Authorization"] = ctx["doctor"]
    withdrawn = await client.post(f"/api/v1/doctor/leaves/{leave['id']}/cancel")
    assert withdrawn.json()["status"] == "cancelled"
    client.headers["Authorization"] = ctx["patient"]
    reopened = await client.get("/api/v1/book/appointment/availability", params=later_slot)
    assert reopened.json()["available"] is True


async def test_admin_records_leave_directly_and_rejects_requests(
    admin_client: httpx.AsyncClient,
) -> None:
    ctx = await _setup(admin_client)
    client = admin_client
    start, end = _window(3)
    body = {"starts_at": start.isoformat(), "ends_at": end.isoformat(), "reason": "Sick leave"}

    assert (await client.post("/api/v1/admin/leaves", json=body)).status_code == 422
    recorded = await client.post(
        "/api/v1/admin/leaves", json={**body, "doctor_id": ctx["doctor_id"]}
    )
    assert recorded.status_code == 201
    assert recorded.json()["status"] == "approved"
    assert recorded.json()["reviewed_by"] is not None

    client.headers["Authorization"] = ctx["doctor"]
    later_start, later_end = _window(10)
    request = await client.post(
        "/api/v1/doctor/leaves",
        json={
            "starts_at": later_start.isoformat(),
            "ends_at": later_end.isoformat(),
            "reason": "Family event",
        },
    )
    client.headers["Authorization"] = ctx["admin"]
    rejected = await client.post(
        f"/api/v1/admin/leaves/{request.json()['id']}/reject", json={"note": "Short-staffed"}
    )
    assert rejected.json()["status"] == "rejected"
    assert (
        await client.post(f"/api/v1/admin/leaves/{request.json()['id']}/cancel")
    ).status_code == 409

    past = await client.post(
        "/api/v1/admin/leaves",
        json={
            "doctor_id": ctx["doctor_id"],
            "starts_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            "ends_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "reason": "Too late",
        },
    )
    assert past.status_code == 422

    client.headers["Authorization"] = ctx["patient"]
    assert (await client.post("/api/v1/admin/leaves", json=body)).status_code == 403


async def test_admin_cancellation_requires_reason_but_patient_does_not(
    admin_client: httpx.AsyncClient,
) -> None:
    ctx = await _setup(admin_client)
    client = admin_client
    client.headers["Authorization"] = ctx["patient"]
    first, second = [], []
    for bucket, hours in ((first, 10), (second, 12)):
        start = datetime.now(UTC) + timedelta(days=2, hours=hours)
        response = await client.post(
            "/api/v1/book/appointment",
            json={
                "doctor_id": ctx["doctor_id"],
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(minutes=30)).isoformat(),
            },
        )
        bucket.append(response.json()["id"])

    patient_cancel = await client.post(f"/api/v1/my/appointments/{first[0]}/cancel")
    assert patient_cancel.status_code == 200
    assert patient_cancel.json()["cancelled_by_role"] == "patient"
    assert patient_cancel.json()["cancellation_reason"] is None

    client.headers["Authorization"] = ctx["admin"]
    no_reason = await client.post(f"/api/v1/admin/appointments/{second[0]}/cancel")
    assert no_reason.status_code == 422
    with_reason = await client.post(
        f"/api/v1/admin/appointments/{second[0]}/cancel", json={"reason": "Clinic closed for audit"}
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["cancelled_by_role"] == "admin"
    assert with_reason.json()["cancellation_reason"] == "Clinic closed for audit"
