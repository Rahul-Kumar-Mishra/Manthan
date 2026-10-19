async def test_patient_crud_and_date_validation(admin_client) -> None:
    response = await admin_client.post(
        "/api/v1/admin/patients",
        json={"full_name": "Sample Patient", "date_of_birth": "1990-04-12"},
    )
    assert response.status_code == 201
    patient = response.json()

    updated = await admin_client.patch(
        f"/api/v1/admin/patients/{patient['id']}", json={"phone": "+1-555-0100"}
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+1-555-0100"

    listed = await admin_client.get("/api/v1/admin/patients")
    assert [item["id"] for item in listed.json()] == [patient["id"]]

    invalid = await admin_client.post(
        "/api/v1/admin/patients",
        json={"full_name": "Future Patient", "date_of_birth": "2999-01-01"},
    )
    assert invalid.status_code == 422

    deleted = await admin_client.delete(f"/api/v1/admin/patients/{patient['id']}")
    assert deleted.status_code == 204
    missing = await admin_client.get(f"/api/v1/admin/patients/{patient['id']}")
    assert missing.status_code == 404
