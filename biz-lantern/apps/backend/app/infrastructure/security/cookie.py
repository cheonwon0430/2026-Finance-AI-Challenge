from fastapi import Request, Response


SESSION_COOKIE_NAME = "session_token"


def set_session_cookie(
    response: Response,
    token: str,
) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,  # JavaScript 코드로 Cookie를 읽을 수 없음. XSS에 의해 Session Token이 직접 탈취되는 위험을 줄이는 목적
        secure=False,   # local: False / prod: True, 환경변수 관리 대상
        samesite="lax",  # Cross-Site 요청에서 Cookie가 제한적으로 전송
        max_age=60 * 60 * 24 * 7, # 7일
        path="/",
    )


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE_NAME)


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )