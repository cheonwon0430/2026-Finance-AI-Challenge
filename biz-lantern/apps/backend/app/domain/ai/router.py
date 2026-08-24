"""
뉴스 요약 워크플로 HTTP API.

    POST /api/v1/chat  {"company": "트래블월렛"}

프리픽스는 /chat 하나만 갖는다. /api/v1 은 main.py 의 base_router 가 붙인다.

핸들러를 async def 로 둔다. domain/news/router.py 가 def 를 쓴 것과 반대인데 이유가 있다 -
그쪽은 내부가 전부 sync(httpx.post + time.sleep)라 이벤트 루프를 막지 않으려고 def 로 뒀고,
run_news_workflow 는 async 라 그대로 await 하는 게 맞다.

상태코드를 셋으로 나눈다. **설정 누락과 외부 API 실패는 다른 사건이다.**

    500  우리 쪽 설정이 없다. 외부를 부르기 전에 미리 잡는다
    502  Tavily·LLM 이 끝내 응답하지 않았거나 거부했다
    422  요청 본문이 스키마에 안 맞는다 (FastAPI 가 처리)

    [1] 설정
    [2] 설정 점검
    [3] 핸들러
    [4] 시험용 실행

사용법:
    python -m app.domain.ai.router
    curl -X POST http://127.0.0.1:8100/chat -H "Content-Type: application/json" \
         -d '{"company":"트래블월렛","top_n":3}'
"""
import logging

from fastapi import APIRouter, HTTPException

from app.ai.news.llm_client import LLMError
from app.ai.news.tavily_client import TavilySearchError
from app.common.config import settings
from app.domain.ai.schema import ChatRequest, ChatResponse
from app.domain.ai.service import run_chat

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8100

_REQUIRED_SETTINGS = (
    ("TAVILY_API_KEY", "tavily_api_key"),
    ("OPENAI_BASE_URL", "openai_base_url"),
    ("OPENAI_API_KEY", "openai_api_key"),
    ("OPENAI_MODEL", "openai_model"),
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ---------------------------------------------------------------------------
# [2] 설정 점검
# ---------------------------------------------------------------------------
def missing_settings() -> list[str]:
    """비어 있는 설정 이름들. 외부 호출 전에 미리 잡아 500 으로 구분한다."""
    return [
        env_name
        for env_name, field in _REQUIRED_SETTINGS
        if not (getattr(settings, field, None) or "").strip()
    ]


# ---------------------------------------------------------------------------
# [3] 핸들러
# ---------------------------------------------------------------------------
@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    """기업명 하나로 뉴스를 검색·선별해 요약과 출처를 돌려준다.

    응답의 url 은 전부 검색이 준 값 그대로다 - URL 은 LLM 을 거치지 않으므로 지어낼 통로가
    없다. published_on 은 코드가 ISO 로 바꾼 값이고, 없으면 null 이다.

    요약이 0건이어도 200 이다. "관련 뉴스가 없다" 는 오류가 아니라 정상적인 답이고,
    왜 그런지는 status 와 search_quality_reason 에 담긴다.
    """
    missing = missing_settings()
    if missing:
        # 설정 문제는 우리 쪽 문제지 외부 API 문제가 아니다
        raise HTTPException(status_code=500, detail=f"설정 누락: {', '.join(missing)}")

    try:
        return await run_chat(body)
    except (TavilySearchError, LLMError) as error:
        # 사유를 그대로 넘겨 원인을 볼 수 있게 한다. 두 클라이언트 모두 인증키를 헤더로만
        # 보내므로 메시지에 키가 실릴 일은 없다.
        logger.exception("뉴스 요약 실패: company=%s", body.company)
        raise HTTPException(
            status_code=502, detail=f"{type(error).__name__}: {error}"
        ) from error


# ---------------------------------------------------------------------------
# [4] 시험용 실행 - main.py 를 건드리지 않고 HTTP 로 확인한다
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    app = FastAPI(title="chat 시험용 API")
    app.include_router(router)

    print(f"POST http://{HOST}:{PORT}/chat")
    print(f"문서 http://{HOST}:{PORT}/docs")
    uvicorn.run(app, host=HOST, port=PORT)
