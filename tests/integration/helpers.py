import httpx

PASSWORD = "integration-password-123"


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return "Bearer " + response.json()["access_token"]


async def staff_account(client: httpx.AsyncClient, md_token: str, email: str) -> tuple[str, str]:
    """Create an admin-role account as the MD; return (user_id, bearer token)."""
    client.headers["Authorization"] = md_token
    created = await client.post(
        "/api/v1/admin/staff/accounts", json={"email": email, "password": PASSWORD, "role": "admin"}
    )
    assert created.status_code == 201, created.text
    return created.json()["id"], await login(client, email)


async def register_patient(client: httpx.AsyncClient, email: str, phone: str | None = None) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Test Patient",
            "date_of_birth": "1991-04-04",
            "phone": phone,
        },
    )
    assert response.status_code == 201, response.text
    return "Bearer " + response.json()["access_token"]


async def grant(client: httpx.AsyncClient, token: str, user_id: str, module: str) -> httpx.Response:
    client.headers["Authorization"] = token
    return await client.post(
        "/api/v1/admin/access/grants", json={"user_id": user_id, "module": module}
    )
