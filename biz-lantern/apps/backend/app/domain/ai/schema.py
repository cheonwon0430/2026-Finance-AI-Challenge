"""
/chat 엔드포인트의 요청·응답 DTO.

`app/ai/news/state.py` 의 TypedDict 를 pydantic 으로 옮긴 것이다. **필드 이름을 그대로
유지한다** - State 와 응답을 눈으로 대조할 수 있어야 어디서 값이 빠졌는지 추적이 된다.

기본값은 여기서 다시 정의하지 않고 워크플로의 DEFAULT_* 를 그대로 import 해 쓴다.
숫자를 두 군데 적어 두면 한쪽만 고치는 날이 온다.

    [1] 요청
    [2] 응답
"""
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.news.search import DEFAULT_MAX_RESULTS, DEFAULT_TIME_RANGE
from app.ai.news.state import DEFAULT_TOP_N

# Tavily 의 max_results 상한과 맞춘다. 그 위는 어차피 거절당한다
MAX_RESULTS_LIMIT = 20


# ---------------------------------------------------------------------------
# [1] 요청
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    """기업명 하나로 뉴스 요약을 요청한다.

    topic 과 search_depth 는 일부러 열지 않았다. 검색 튜닝 손잡이라 화면이 정할 값이
    아니다. CLI 는 --topic / --search-depth 로 열어 두지만 API 는 기본값에 맡긴다.
    """

    company: str = Field(min_length=1, description="검색할 기업명")
    top_n: int = Field(
        DEFAULT_TOP_N,
        ge=1,
        le=MAX_RESULTS_LIMIT,
        description="원문을 읽고 요약할 최대 건수. 그대로 Extract 비용이 된다",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="기업 별칭. 회사명이 실제로 언급됐는지 대조할 때 쓴다 (예: 토스, Toss)",
    )
    time_range: Literal["day", "week", "month", "year", "all"] = Field(
        DEFAULT_TIME_RANGE,
        description="검색 기간. all 이면 기간 제한 없이 검색한다",
    )
    max_results: int = Field(
        DEFAULT_MAX_RESULTS,
        ge=1,
        le=MAX_RESULTS_LIMIT,
        description="Query 하나당 검색 결과 수",
    )


# ---------------------------------------------------------------------------
# [2] 응답
# ---------------------------------------------------------------------------
class SourceResponse(BaseModel):
    """요약 하나에 달리는 출처. state.Source 와 같은 모양이다.

    role 이 둘로 나뉜다. primary 는 원문을 읽고 요약의 근거가 된 기사이고, related 는
    같은 사건을 다뤘지만 읽지는 않은 기사다. **읽지 않은 문서를 읽은 것처럼 쓰지 않으려고**
    화면에서도 구분할 수 있게 그대로 내보낸다.
    """

    article_id: int
    title: str | None
    url: str                        # 검색이 준 원본 문자열
    site: str                       # 출처 도메인
    published_on: str | None        # "2026-08-08". 없으면 null
    role: Literal["primary", "related"]


class SummaryResponse(BaseModel):
    summary_id: int
    title: str
    summary: str
    article_ids: list[int]          # 근거가 된 기사. primary 만 들어간다
    duplicate_group: int            # 0 이면 묶이지 않은 단독 건
    sources: list[SourceResponse]


class ChatResponse(BaseModel):
    """화면이 쓸 것만 담는다. NewsState 22개 키 중 여섯이다.

    status 를 반드시 함께 보낸다. summaries 가 비는 경우가 no_candidates /
    no_relevant_news / error 로 셋인데, status 가 없으면 화면에서 전부 똑같은 빈 배열로
    보여 "뉴스가 없다" 와 "요청이 실패했다" 를 구별할 수 없다.
    """

    company: str
    status: Literal["ok", "no_candidates", "no_relevant_news", "error"]
    search_quality: Literal["sufficient", "insufficient"] | None = None
    search_quality_reason: str | None = None
    summaries: list[SummaryResponse]
    sources: list[SourceResponse]    # 전체 평탄화. 출처 목록을 따로 그릴 때 쓴다
    errors: list[str]
