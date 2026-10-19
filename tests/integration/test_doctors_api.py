from datetime import UTC, datetime, timedelta


async def test_doctor_crud_and_filters(admin_client) -> None:
    hospital = await admin_client.post(
        "/api/v1/admin/hospitals", json={"name": "Doctor Test Hospital"}
    )
    branch = await admin_client.post(
        f"/api/v1/admin/hospitals/{hospital.json()['id']}/branches",
        json={"name": "Doctor Test Branch"},
    )
    response = await admin_client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": branch.json()["id"],
            "full_name": "Sample Doctor",
            "specialization": "Cardiology",
            "email": "doctor@example.com",
        },
    )
    assert response.status_code == 201
    doctor = response.json()

    filtered = await admin_client.get("/api/v1/admin/doctors?specialization=cardio")
    assert [item["id"] for item in filtered.json()] == [doctor["id"]]

    updated = await admin_client.patch(
        f"/api/v1/admin/doctors/{doctor['id']}", json={"is_active": False}
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    deleted = await admin_client.delete(f"/api/v1/admin/doctors/{doctor['id']}")
    assert deleted.status_code == 204


async def test_doctor_requires_existing_branch(admin_client) -> None:
    import uuid

    response = await admin_client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": str(uuid.uuid4()),
            "full_name": "Sample Doctor",
            "specialization": "Cardiology",
        },
    )
    assert response.status_code == 404


async def test_doctor_access_is_limited_to_assigned_patients(admin_client) -> None:
    doctor_account = await admin_client.post(
        "/api/v1/admin/staff/accounts",
        json={
            "email": "assigned.doctor@example.com",
            "password": "assigned-doctor-password-123",
            "role": "doctor",
        },
    )
    hospital = await admin_client.post(
        "/api/v1/admin/hospitals", json={"name": "Assigned Patient Hospital"}
    )
    branch = await admin_client.post(
        f"/api/v1/admin/hospitals/{hospital.json()['id']}/branches",
        json={"name": "Assigned Patient Branch"},
    )
    doctor = await admin_client.post(
        "/api/v1/admin/doctors",
        json={
            "user_id": doctor_account.json()["id"],
            "branch_id": branch.json()["id"],
            "full_name": "Assigned Doctor",
            "specialization": "Family Medicine",
        },
    )
    assert doctor.status_code == 201

    unrelated = await admin_client.post(
        "/api/v1/admin/patients",
        json={"full_name": "Unrelated Patient", "date_of_birth": "1980-01-01"},
    )
    registration = await admin_client.post(
        "/api/v1/auth/register",
        json={
            "email": "assigned.patient@example.com",
            "password": "assigned-patient-password-123",
            "full_name": "Assigned Patient",
            "date_of_birth": "1990-01-01",
        },
    )
    admin_client.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"
    patient = await admin_client.get("/api/v1/profile")

    starts_at = datetime.now(UTC) + timedelta(days=5)
    appointment = await admin_client.post(
        "/api/v1/book/appointment",
        json={
            "doctor_id": doctor.json()["id"],
            "starts_at": starts_at.isoformat(),
            "ends_at": (starts_at + timedelta(minutes=30)).isoformat(),
        },
    )
    assert appointment.status_code == 201

    login = await admin_client.post(
        "/api/v1/auth/login",
        json={
            "email": "assigned.doctor@example.com",
            "password": "assigned-doctor-password-123",
        },
    )
    admin_client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

    my_profile = await admin_client.get("/api/v1/doctor/profile")
    assert my_profile.status_code == 200
    my_appointments = await admin_client.get("/api/v1/doctor/appointments")
    assert [item["id"] for item in my_appointments.json()] == [appointment.json()["id"]]
    assigned_patient = await admin_client.get(f"/api/v1/doctor/patients/{patient.json()['id']}")
    assert assigned_patient.status_code == 200
    hidden_patient = await admin_client.get(f"/api/v1/doctor/patients/{unrelated.json()['id']}")
    assert hidden_patient.status_code == 404
    cannot_edit = await admin_client.patch(
        f"/api/v1/admin/patients/{patient.json()['id']}", json={"phone": "+1-555-0188"}
    )
    assert cannot_edit.status_code == 403
