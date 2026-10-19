from helpers import grant, login, register_patient, staff_account


async def test_module_access_is_delegated_down_a_hierarchy(admin_client) -> None:
    client = admin_client
    md = client.headers["Authorization"]
    me = await client.get("/api/v1/admin/access/me")
    assert me.json()["is_md"] is True
    assert set(me.json()["modules"]) >= {"doctors", "pharmacy", "staff"}

    manager_id, manager = await staff_account(client, md, "manager@example.com")
    clerk_id, clerk = await staff_account(client, md, "clerk@example.com")
    other_id, other = await staff_account(client, md, "other@example.com")

    # A fresh staff account holds nothing and is refused everywhere.
    client.headers["Authorization"] = manager
    assert (await client.get("/api/v1/admin/access/me")).json()["modules"] == []
    assert (await client.get("/api/v1/admin/medicines")).status_code == 403
    assert (await grant(client, manager, clerk_id, "pharmacy")).status_code == 403

    # MD -> manager (pharmacy, staff); manager -> clerk (pharmacy only).
    assert (await grant(client, md, manager_id, "pharmacy")).status_code == 201
    assert (await grant(client, md, manager_id, "staff")).status_code == 201
    clerk_grant = await grant(client, manager, clerk_id, "pharmacy")
    assert clerk_grant.status_code == 201
    assert clerk_grant.json()["granted_by"] == manager_id
    assert (await grant(client, manager, clerk_id, "pharmacy")).status_code == 409
    # The manager cannot give away a module they don't hold.
    assert (await grant(client, manager, clerk_id, "doctors")).status_code == 403

    client.headers["Authorization"] = clerk
    assert (await client.get("/api/v1/admin/medicines")).status_code == 200
    assert (await client.get("/api/v1/admin/staff")).status_code == 403

    # A peer with the same module can't revoke a grant outside their branch.
    assert (await grant(client, md, other_id, "pharmacy")).status_code == 201
    client.headers["Authorization"] = other
    assert (
        await client.delete(f"/api/v1/admin/access/grants/{clerk_grant.json()['id']}")
    ).status_code == 403

    # Revoking the manager's pharmacy grant cascades to the clerk they delegated to.
    client.headers["Authorization"] = md
    staff = {row["email"]: row for row in (await client.get("/api/v1/admin/access/staff")).json()}
    manager_pharmacy = next(
        g for g in staff["manager@example.com"]["grants"] if g["module"] == "pharmacy"
    )
    revoked = await client.delete(f"/api/v1/admin/access/grants/{manager_pharmacy['id']}")
    assert revoked.json()["revoked"] == 2
    client.headers["Authorization"] = clerk
    assert (await client.get("/api/v1/admin/medicines")).status_code == 403
    client.headers["Authorization"] = manager
    assert (await client.get("/api/v1/admin/access/me")).json()["modules"] == ["staff"]

    # Patients can't receive staff modules.
    patient = await register_patient(client, "access.patient@example.com")
    client.headers["Authorization"] = patient
    patient_id = (await client.get("/api/v1/auth/me")).json()["id"]
    assert (await grant(client, md, patient_id, "pharmacy")).status_code == 409
    assert await login(client, "manager@example.com")
