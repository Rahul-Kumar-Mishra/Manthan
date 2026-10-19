async def test_hospital_and_branch_crud(admin_client) -> None:
    hospital_response = await admin_client.post(
        "/api/v1/admin/hospitals",
        json={"name": "North Clinic", "address": "10 Example Street"},
    )
    assert hospital_response.status_code == 201
    hospital = hospital_response.json()

    branch_response = await admin_client.post(
        f"/api/v1/admin/hospitals/{hospital['id']}/branches",
        json={"name": "Main Branch"},
    )
    assert branch_response.status_code == 201
    branch = branch_response.json()
    assert branch["hospital_id"] == hospital["id"]

    listed = await admin_client.get(f"/api/v1/admin/hospitals/{hospital['id']}/branches")
    assert [item["id"] for item in listed.json()] == [branch["id"]]

    duplicate = await admin_client.post(
        "/api/v1/admin/hospitals",
        json={"name": "North Clinic"},
    )
    assert duplicate.status_code == 409


async def test_hospital_mutations_require_admin(client) -> None:
    response = await client.post("/api/v1/admin/hospitals", json={"name": "Unauthorized"})

    assert response.status_code == 401


async def test_hospital_delete_rejects_dependent_doctors(admin_client) -> None:
    hospital = await admin_client.post(
        "/api/v1/admin/hospitals", json={"name": "Hospital With Doctor"}
    )
    branch = await admin_client.post(
        f"/api/v1/admin/hospitals/{hospital.json()['id']}/branches",
        json={"name": "Protected Branch"},
    )
    await admin_client.post(
        "/api/v1/admin/doctors",
        json={
            "branch_id": branch.json()["id"],
            "full_name": "Dependent Doctor",
            "specialization": "Family Medicine",
        },
    )

    response = await admin_client.delete(f"/api/v1/admin/hospitals/{hospital.json()['id']}")

    assert response.status_code == 409
