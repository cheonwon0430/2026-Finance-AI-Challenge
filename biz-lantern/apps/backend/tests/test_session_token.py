from app.infrastructure.security.session_token import (
    generate_session_token,
    hash_session_token,
)


def test_session_token_generation() -> None:
    token = generate_session_token()

    assert token
    assert len(token) > 32


def test_session_token_hash() -> None:
    token = generate_session_token()

    hashed = hash_session_token(token)

    assert hashed != token
    assert len(hashed) == 64
    assert hashed == hash_session_token(token)