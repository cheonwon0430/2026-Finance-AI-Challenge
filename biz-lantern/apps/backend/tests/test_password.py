from app.infrastructure.security.password import (
    hash_password,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    password = "test-password"

    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)