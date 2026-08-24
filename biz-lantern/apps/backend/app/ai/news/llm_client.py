"""
OpenAI 호환 Chat Completions 호출. 응답 형식을 JSON 으로 강제해서 받아온다.

주소·키·모델을 전부 설정에서 받는다. 자체 게이트웨이를 쓰기 때문에 엔드포인트도 모델명도
코드에 박지 않는다 (`OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL`).

tavily_client.py 와 같은 모양으로 맞춰 뒀다 - async 고, AsyncClient 를 인자로 받고,
재시도 정책이 같은 자리에 있다. 파이프라인이 두 클라이언트를 같은 방식으로 다룰 수 있어야 한다.
"""
import asyncio
import logging

import httpx

from app.common.config import settings

CHAT_PATH = "/chat/completions"

TIMEOUT = 120           # 후보 20건을 한 번에 재정렬하므로 선별보다 오래 걸린다
DEFAULT_MAX_TOKENS = 4096

# 일시적 실패로 보고 다시 시도할 상태코드. 429 rate limit 과 5xx.
# 400(잘못된 요청) / 401(인증) / 403(지역 제한) 은 다시 보내도 같은 결과라 즉시 올린다.
RETRY_STATUS = frozenset({429})
RETRY_DELAYS = (2, 5, 10)   # 시도 사이 대기(초). 길이 + 1 이 총 시도 횟수다
MAX_RETRY_AFTER = 60        # 서버가 Retry-After 로 몇 분을 부르면 기다리느니 실패로 넘긴다

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """LLM 호출 실패.

    httpx 예외 여러 종류와 HTTP 오류 응답, 그리고 모델 거부를 한 종류로 모은다.
    tavily_client.TavilySearchError 와 같은 모양이라 파이프라인이 같은 방식으로 다룰 수 있다.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retryable: bool = False,
        retry_after: float = 0.0,
    ):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after


def _require(name: str, value: str | None) -> str:
    """설정값 하나를 확인한다. 무엇이 비었는지 이름으로 짚어준다."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise LLMError(f"{name} 이(가) 없습니다. backend/.env 에 추가하세요.")

    return cleaned


def ensure_configured() -> None:
    """설정이 다 있는지 호출 전에 확인한다.

    rerank 가 설정 때문에 실패할 거라면 Tavily 검색을 태우기 전에 알아야 한다.
    """
    _require("OPENAI_BASE_URL", settings.openai_base_url)
    _require("OPENAI_API_KEY", settings.openai_api_key)
    _require("OPENAI_MODEL", settings.openai_model)


def _endpoint() -> str:
    """base_url 뒤에 /chat/completions 를 붙인다. 끝 슬래시가 있어도 없어도 같게 만든다."""
    return _require("OPENAI_BASE_URL", settings.openai_base_url).rstrip("/") + CHAT_PATH


def _headers() -> dict[str, str]:
    """인증 헤더. 키는 URL 이 아니라 헤더로만 나가므로 로그·에러에 실릴 일이 없다."""
    return {
        "Authorization": f"Bearer {_require('OPENAI_API_KEY', settings.openai_api_key)}",
        "Content-Type": "application/json",
    }


def _error_detail(response: httpx.Response) -> str:
    """오류 응답에서 서버가 준 사유를 뽑아낸다. JSON 이 아니면 본문 앞부분을 그대로."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]

    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:200]

    return str(error if error is not None else body)[:200]


def _retry_after(response: httpx.Response) -> float:
    """Retry-After 헤더를 초로 읽는다. 없거나 해석 불가면 0(=기본 대기 사용)."""
    raw = response.headers.get("Retry-After")
    if not raw:
        return 0.0

    try:
        return min(float(raw), MAX_RETRY_AFTER)
    except ValueError:
        # HTTP-date 형식도 규격상 허용되지만 그때는 기본 백오프로 처리한다
        return 0.0


async def _request_once(client: httpx.AsyncClient, payload: dict) -> dict:
    """POST 1회. 성공하면 파싱한 dict, 실패하면 LLMError."""
    try:
        response = await client.post(
            _endpoint(),
            json=payload,
            headers=_headers(),
            timeout=TIMEOUT,
        )
    except httpx.TimeoutException as error:
        raise LLMError(
            f"요청 시간 초과({TIMEOUT}s): {type(error).__name__}", retryable=True
        ) from error
    except httpx.TransportError as error:
        # 연결 실패·DNS·프로토콜 오류. 네트워크가 흔들린 것일 수 있으니 재시도 대상으로 본다
        raise LLMError(f"연결 실패: {type(error).__name__}: {error}", retryable=True) from error

    if response.is_success:
        try:
            return response.json()
        except ValueError:
            raise LLMError(
                f"JSON 이 아닌 응답: {response.text[:200]}",
                status=response.status_code,
            ) from None

    status = response.status_code

    raise LLMError(
        f"HTTP {status}: {_error_detail(response)}",
        status=status,
        retryable=status in RETRY_STATUS or status >= 500,
        retry_after=_retry_after(response),
    )


async def _post(client: httpx.AsyncClient, payload: dict) -> dict:
    """일시적 실패(타임아웃·rate limit·5xx)만 정해진 횟수까지 다시 시도한다.

    오류를 삼키지 않는다. 어디까지가 치명적인지는 파이프라인이 정한다.
    """
    for delay in RETRY_DELAYS:
        try:
            return await _request_once(client, payload)
        except LLMError as error:
            if not error.retryable:
                raise

            wait = error.retry_after or delay
            logger.warning("LLM 재시도 (%.0f초 대기): %s", wait, error)
            await asyncio.sleep(wait)

    # 마지막 시도. 여기서 실패하면 그대로 올라간다
    return await _request_once(client, payload)


def _payload(instructions: str, user_content: str, max_tokens: int) -> dict:
    return {
        "model": _require("OPENAI_MODEL", settings.openai_model),
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_content},
        ],
        # max_tokens 가 아니라 max_completion_tokens 다. 문서에는 둘 다 유효하다고 돼 있지만
        # 최신 모델은 옛 이름을 거부한다("Unsupported parameter: 'max_tokens'").
        "max_completion_tokens": max_tokens,
    }


async def complete_json(
    client: httpx.AsyncClient,
    instructions: str,
    user_content: str,
    schema: dict,
    schema_name: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """응답 형식을 JSON 으로 강제해서 호출한다. 파싱한 응답 원본을 그대로 돌려준다.

    먼저 json_schema(strict)로 시도하고, 게이트웨이가 그걸 모르면(400) json_object 로
    한 번 더 시도한다. 어느 쪽으로 받든 내용 검증은 호출하는 쪽이 다시 하므로 안전성은 같다.
    """
    payload = _payload(instructions, user_content, max_tokens)
    payload["response_format"] = {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "strict": True, "schema": schema},
    }

    try:
        return await _post(client, payload)
    except LLMError as error:
        if error.status != 400:
            raise

        # 게이트웨이가 json_schema 를 모르는 경우다. 조용히 넘어가지 않고 남긴다.
        logger.warning("json_schema 거부(400) - json_object 로 재시도한다: %s", error)

    payload["response_format"] = {"type": "json_object"}

    return await _post(client, payload)
