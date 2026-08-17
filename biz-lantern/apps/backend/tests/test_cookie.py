from fastapi import Response

from app.infrastructure.security.cookie import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    get_session_token,
    set_session_cookie,
)


def test_set_session_cookie() -> None:
    response = Response()

    set_session_cookie(response, "test-token")

    cookie = response.headers["set-cookie"]

    assert f"{SESSION_COOKIE_NAME}=test-token" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie


def test_get_session_token() -> None:
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (b"cookie", b"session_token=test-token"),
        ],
    }

    request = Request(scope)

    assert get_session_token(request) == "test-token"


def test_clear_session_cookie() -> None:
    response = Response()

    clear_session_cookie(response)

    cookie = response.headers["set-cookie"]

    assert "session_token=" in cookie
    assert "Max-Age=0" in cookie