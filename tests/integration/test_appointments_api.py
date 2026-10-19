from datetime import UTC, datetime, timedelta


async def test_patient_books_checks_and_cancels_appointment(admin_client) -> None:
    hospital = await admin_client.post(
        "/api/v1/admin/hospitals", json={"name": "Booking Test Hospital"}
    )
    branch = await admin_client.post(
        f"/api/v1/admin/hospitals/{hospital.json()['id']}/branches",
        json={"name": "Booking Test Branch"},
    )
    doctor = await admin_client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": branch.json()["id"],
            "full_name": "Booking Test Doctor",
            "specialization": "General Practice",
        },
    )
    doctor_id = doctor.json()["id"]

    registration = await admin_client.post(
        "/api/v1/auth/register",
        json={
            "email": "booking.patient@example.com",
            "password": "booking-patient-password-123",
            "full_name": "Booking Patient",
            "date_of_birth": "1992-06-12",
        },
    )
    assert registration.status_code == 201
    admin_client.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"

    starts_at = datetime.now(UTC) + timedelta(days=2)
    ends_at = starts_at + timedelta(minutes=30)
    params = {
        "doctor_id": doctor_id,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
    }
    availability = await admin_client.get("/api/v1/book/appointment/availability", params=params)
    assert availability.status_code == 200
    assert availability.json()["available"] is True

    booking = await admin_client.post("/api/v1/book/appointment", json=params)
    assert booking.status_code == 201
    appointment = booking.json()

    unavailable = await admin_client.get("/api/v1/book/appointment/availability", params=params)
    assert unavailable.json()["available"] is False

    overlapping_start = starts_at + timedelta(minutes=15)
    overlap = await admin_client.post(
        "/api/v1/book/appointment",
        json={
            "doctor_id": doctor_id,
            "starts_at": overlapping_start.isoformat(),
            "ends_at": (overlapping_start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert overlap.status_code == 409

    mine = await admin_client.get("/api/v1/my/appointments")
    assert [item["id"] for item in mine.json()] == [appointment["id"]]

    cancelled = await admin_client.post(f"/api/v1/my/appointments/{appointment['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    available_after_cancel = await admin_client.get(
        "/api/v1/book/appointment/availability", params=params
    )
    assert available_after_cancel.json()["available"] is True
