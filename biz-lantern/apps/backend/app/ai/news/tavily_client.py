"""
Tavily Search 호출. 이 단계에서는 검색만 쓰므로 Extract 는 만들지 않는다.

app/domain/news 의 sync 판과 두 가지가 다르다.

    1. async 다. 두 Query 를 동시에 던지는 게 이 모듈의 목적이라 비동기여야 의미가 있다.
    2. 파싱한 dict 를 그대로 돌려준다. 저 쪽이 JSON 문자열을 돌려준 건 응답 원본을 파일로
       남기기 위해서였는데, 여기서는 파일을 만들지 않는다.

AsyncClient 를 인자로 받는다. 두 요청이 커넥션 풀을 공유해야 병렬이 제값을 한다.
"""
import asyncio
import logging

import httpx

from app.common.config import settings

SEARCH_URL = "https://api.tavily.com/search"
EXTRACT_URL = "https://api.tavily.com/extract"

MAX_SEARCH_RESULTS = 20   # Tavily 의 max_results 상한
MAX_EXTRACT_URLS = 20     # Extract 는 한 요청에 최대 20개. 쪼개는 건 호출하는 쪽 책임이다

TIMEOUT = 30
EXTRACT_TIMEOUT = 120     # 원문을 실제로 받아오느라 검색보다 훨씬 느리다

# 일시적 실패로 보고 다시 시도할 상태코드. 429 rate limit / 432 plan / 433 paygo 와 5xx.
# 400(잘못된 요청)·401(인증) 은 다시 보내도 같은 결과라 즉시 올린다.
RETRY_STATUS = frozenset({429, 432, 433})
RETRY_DELAYS = (2, 5, 10)   # 시도 사이 대기(초). 길이 + 1 이 총 시도 횟수다
MAX_RETRY_AFTER = 60        # 서버가 Retry-After 로 몇 분을 부르면 기다리느니 실패로 넘긴다

logger = logging.getLogger(__name__)


class TavilySearchError(RuntimeError):
    """Tavily 검색 실패.

    httpx 예외 여러 종류와 HTTP 오류 응답을 한 종류로 모은다. 호출하는 쪽이 잡아야 할
    예외가 흩어지면 '한쪽 Query 만 실패' 를 안전하게 넘기기 어렵다.
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


def _headers() -> dict[str, str]:
    """인증 헤더. 키는 URL 이 아니라 헤더로만 나가므로 로그·에러에 실릴 일이 없다."""
    key = (settings.tavily_api_key or "").strip()
    if not key:
        raise TavilySearchError("TAVILY_API_KEY 가 없습니다. backend/.env 에 추가하세요.")

    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _error_detail(response: httpx.Response) -> str:
    """오류 응답에서 Tavily 가 준 사유를 뽑아낸다. JSON 이 아니면 본문 앞부분을 그대로."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]

    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("error") or detail)[:200]

    return str(detail if detail is not None else body)[:200]


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


async def _request_once(
    client: httpx.AsyncClient,
    payload: dict,
    *,
    url: str = SEARCH_URL,
    timeout: int = TIMEOUT,
) -> dict:
    """POST 1회. 성공하면 파싱한 dict, 실패하면 TavilySearchError."""
    try:
        response = await client.post(
            url,
            json=payload,
            headers=_headers(),
            timeout=timeout,
        )
    except httpx.TimeoutException as error:
        raise TavilySearchError(
            f"요청 시간 초과({timeout}s): {type(error).__name__}", retryable=True
        ) from error
    except httpx.TransportError as error:
        # 연결 실패·DNS·프로토콜 오류. 네트워크가 흔들린 것일 수 있으니 재시도 대상으로 본다
        raise TavilySearchError(
            f"연결 실패: {type(error).__name__}: {error}", retryable=True
        ) from error

    if response.is_success:
        try:
            return response.json()
        except ValueError:
            raise TavilySearchError(
                f"JSON 이 아닌 응답: {response.text[:200]}",
                status=response.status_code,
            ) from None

    status = response.status_code

    raise TavilySearchError(
        f"HTTP {status}: {_error_detail(response)}",
        status=status,
        retryable=status in RETRY_STATUS or status >= 500,
        retry_after=_retry_after(response),
    )


async def search(
    client: httpx.AsyncClient,
    query: str,
    *,
    topic: str = "news",
    time_range: str | None = "month",
    max_results: int = 10,
    search_depth: str = "basic",
) -> dict:
    """뉴스 검색(POST /search). 파싱한 응답을 그대로 돌려준다.

    time_range 는 day / week / month / year. None 이면 보내지 않아 전체 기간이 된다.
    본문(raw_content)은 요청하지 않는다. 이 단계는 '무엇이 있는지'만 본다.

    일시적 실패(타임아웃·rate limit·5xx)만 정해진 횟수까지 다시 시도한다. 오류를 삼키지
    않는다 - 어디까지가 치명적인지는 호출하는 쪽이 정한다.
    """
    if not query.strip():
        raise ValueError("검색어가 비어 있습니다.")
    if not 0 < max_results <= MAX_SEARCH_RESULTS:
        raise ValueError(f"max_results 는 1~{MAX_SEARCH_RESULTS} 여야 합니다. (요청 {max_results})")

    payload = {
        "query": query,
        "topic": topic,
        "time_range": time_range,
        "max_results": max_results,
        "search_depth": search_depth,
    }
    # 값을 주지 않은 선택 파라미터는 아예 보내지 않는다
    payload = {key: value for key, value in payload.items() if value is not None}

    return await _post(client, payload)


async def _post(
    client: httpx.AsyncClient,
    payload: dict,
    *,
    url: str = SEARCH_URL,
    timeout: int = TIMEOUT,
) -> dict:
    """일시적 실패(타임아웃·rate limit·5xx)만 정해진 횟수까지 다시 시도한다."""
    for delay in RETRY_DELAYS:
        try:
            return await _request_once(client, payload, url=url, timeout=timeout)
        except TavilySearchError as error:
            if not error.retryable:
                raise

            wait = error.retry_after or delay
            logger.warning("Tavily 재시도 (%.0f초 대기): %s", wait, error)
            await asyncio.sleep(wait)

    # 마지막 시도. 여기서 실패하면 그대로 올라간다
    return await _request_once(client, payload, url=url, timeout=timeout)


async def extract(
    client: httpx.AsyncClient,
    urls: list[str],
    *,
    extract_depth: str = "basic",
    output_format: str = "markdown",
) -> dict:
    """본문 추출(POST /extract). 파싱한 응답을 그대로 돌려준다.

    한 요청에 최대 MAX_EXTRACT_URLS 개. **실패한 URL 은 예외가 아니라 응답의
    failed_results[] 로 온다** - 호출하는 쪽이 그것도 함께 봐야 한다. 200 이 왔다고
    전부 성공한 게 아니다.

    검색(search)과 달리 원문을 실제로 받아오므로 타임아웃을 길게 잡는다.
    """
    if not urls:
        raise ValueError("추출할 URL 이 없습니다.")
    if len(urls) > MAX_EXTRACT_URLS:
        raise ValueError(
            f"한 번에 최대 {MAX_EXTRACT_URLS}개까지만 추출할 수 있습니다. (요청 {len(urls)}개)"
        )

    payload = {
        "urls": urls,
        "extract_depth": extract_depth,
        "format": output_format,
    }

    return await _post(client, payload, url=EXTRACT_URL, timeout=EXTRACT_TIMEOUT)
