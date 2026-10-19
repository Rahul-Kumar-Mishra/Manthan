from app.core.security import create_access_token, hash_password, verify_password


def test_password_hash_and_verify() -> None:
    hashed = hash_password("a-long-test-password")

    assert hashed != "a-long-test-password"
    assert verify_password("a-long-test-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_is_created() -> None:
    assert create_access_token("user-123")
