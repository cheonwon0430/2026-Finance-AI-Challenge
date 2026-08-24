"""
/chat 이 부르는 응용 계층. 워크플로 호출과 응답 투영을 맡는다.

라우터는 HTTP 만 알고, 워크플로는 자기 State 만 안다. 그 사이를 번역하는 게 여기다.

    ChatRequest ──▶ run_news_workflow 인자 ──▶ NewsState ──▶ ChatResponse

**NewsState 를 그대로 내보내지 않는다.** 22개 키 중 여섯만 쓴다:

    client            httpx.AsyncClient 라 JSON 이 안 된다. 게다가 run_news_workflow 가
                      async with 로 닫고 반환하므로 돌아온 시점엔 이미 죽은 객체다
    extracted_items   기사 원문 전문이 들어 있다(실측 한 건 4,173자). 화면에 쓸모없는데
                      응답만 불어난다
    merged_results    후보 전체. ranked_results / raw_results 와 함께 디버깅용이다
    입력 파라미터      요청자가 이미 아는 값이다

    [1] 요청 -> 워크플로 인자
    [2] 워크플로 결과 -> 응답
    [3] 진입점
"""
from app.ai.news.graph import run_news_workflow
from app.ai.news.state import NewsState
from app.domain.ai.schema import (
    ChatRequest,
    ChatResponse,
    SourceResponse,
    SummaryResponse,
)


# ---------------------------------------------------------------------------
# [1] 요청 -> 워크플로 인자
# ---------------------------------------------------------------------------
def to_time_range(value: str) -> str | None:
    """'all' 은 None 으로 바꾼다.

    Tavily 는 time_range 를 아예 보내지 않아야 전체 기간이 된다(값이 None 인 파라미터는
    tavily_client.search 가 payload 에서 뺀다). CLI 도 같은 변환을 한다.
    """
    return None if value == "all" else value


# ---------------------------------------------------------------------------
# [2] 워크플로 결과 -> 응답
# ---------------------------------------------------------------------------
def to_response(state: NewsState) -> ChatResponse:
    """NewsState 에서 화면이 쓸 것만 골라낸다. 네트워크를 타지 않는 순수 함수다.

    빠뜨린 키가 무엇이고 왜인지는 이 파일 맨 위 docstring 에 적어 두었다.

    status 는 기본값을 두지 않고 "ok" 로 받는다 - 워크플로가 끝까지 갔다면 반드시 채워
    넣는 값이라, 없다는 건 State 를 잘못 만들었다는 뜻이지 정상적인 빈 값이 아니다.
    """
    return ChatResponse(
        company=state["company"],
        status=state.get("status", "ok"),
        search_quality=state.get("search_quality"),
        search_quality_reason=state.get("search_quality_reason"),
        summaries=[
            SummaryResponse(
                summary_id=item["summary_id"],
                title=item["title"],
                summary=item["summary"],
                article_ids=item["article_ids"],
                duplicate_group=item["duplicate_group"],
                sources=[SourceResponse(**source) for source in item["sources"]],
            )
            for item in state.get("summaries") or []
        ],
        sources=[SourceResponse(**source) for source in state.get("sources") or []],
        errors=state.get("errors") or [],
    )


# ---------------------------------------------------------------------------
# [3] 진입점
# ---------------------------------------------------------------------------
async def run_chat(request: ChatRequest) -> ChatResponse:
    """워크플로를 끝까지 돌리고 응답 모양으로 바꿔 돌려준다.

    client 를 넘기지 않는다. 그러면 run_news_workflow 가 자기 AsyncClient 를 만들어
    Tavily·LLM 노드가 커넥션 풀을 공유하게 하고, 끝나면 닫는다.

    Tavily·LLM 실패는 여기서 잡지 않는다. 어디까지가 치명적인지는 HTTP 상태코드를 정하는
    라우터가 안다.
    """
    state = await run_news_workflow(
        request.company,
        top_n=request.top_n,
        # run_news_workflow 의 타입이 tuple[str, ...] 이다
        aliases=tuple(request.aliases),
        time_range=to_time_range(request.time_range),
        max_results=request.max_results,
    )

    return to_response(state)
