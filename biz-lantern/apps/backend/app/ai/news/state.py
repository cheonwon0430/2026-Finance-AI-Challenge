"""
뉴스 워크플로가 단계 사이에 들고 다니는 State.

    START -> search -> merge -> rerank -> quality_check -> END

Node 하나는 자기가 채우는 조각만 돌려준다. total=False 로 둔 건 그 때문이다.

status 와 search_quality 를 나눠 둔 이유가 하나 있다. **품질 판단과 워크플로 성패는
다른 사건이다.** 품질 판단 LLM 이 죽었는데 insufficient 라고 적으면 "판단해 보니 부족하다"
와 구별할 수 없다. status="error" 면 search_quality 는 믿을 값이 아니라는 뜻이고,
무엇이 터졌는지는 errors 에 쌓인다.
"""
from typing import Literal, TypedDict

import httpx

from app.ai.news.rerank import Dropped
from app.ai.news.search import NewsItem, QueryOutcome

# 다음 단계(Extract·요약)로 넘어갈지를 가르는 판단
Quality = Literal["sufficient", "insufficient"]

# 워크플로 자체가 어떻게 끝났나. search_quality 와 섞지 않는다
#   ok                네 단계를 다 지났고 넘길 기사가 있다
#   no_candidates     검색은 됐는데 쓸 후보가 없었다
#   no_relevant_news  후보는 있었으나 넘길 만한 기사가 없다
#   error             중간에 무엇인가 실패했다. errors 를 봐야 한다
#
# no_relevant_news 는 search_quality 가 sufficient 든 insufficient 든 선정 기사가 0건이면
# 붙는다. 다음 단계로 넘길 것이 없다는 사실은 어느 쪽이든 같고, 왜 그렇게 판단했는지는
# search_quality / search_quality_reason 에 그대로 남는다.
Status = Literal["ok", "no_candidates", "no_relevant_news", "error"]

DEFAULT_TOP_N = 5


class RankedItem(NewsItem):
    article_id: int         # merged_results 에서의 자리(1부터). LLM 과 주고받는 유일한 식별자
    rank: int               # 최종 순위. 코드가 score_rerank 로 다시 매긴 값
    score_rerank: float     # LLM 이 준 0~1 점수. NewsItem.score(tavily)와 다른 값이다
    reason: str
    duplicate_group: int    # 같은 사건끼리 같은 번호. 0 이면 묶인 그룹 없음


class Source(TypedDict):
    """요약 하나에 달리는 출처. URL 은 코드가 검색 결과에서 그대로 옮긴 값이다.

    role 이 둘로 나뉘는 이유가 있다. quality_check 는 같은 duplicate_group 에서 대표
    1건만 고르므로(아이씨비: g1 8건 -> 1건), 나머지 형제 기사는 원문을 읽지 않는다.

        primary  selected 에 뽑혀 원문을 추출했고 요약의 근거가 된 기사
        related  같은 사건을 다뤘지만 추출하지 않은 기사. **근거가 아니다**

    읽지 않은 문서를 읽은 것처럼 쓰지 않으려고 화면에서도 구분해 찍는다.
    """
    article_id: int
    title: str | None
    url: str                # 검색이 준 원본 문자열. 만들어내거나 바꾸지 않는다
    site: str               # source_of(url)
    # "2026-08-08". 없으면 None, 못 읽으면 원본 그대로. NewsItem.published_date 와 이름이
    # 다른 건 의미가 다르기 때문이다 - 저쪽은 Tavily 원본, 이쪽은 화면·API 가 그대로 쓸 값이다
    published_on: str | None
    role: Literal["primary", "related"]


class ExtractedItem(TypedDict):
    """원문 추출 결과 하나. 실패해도 자리는 남긴다 - 무엇이 왜 빠졌는지 봐야 한다."""
    article_id: int
    url: str
    title: str | None
    site: str
    ok: bool
    content: str            # 실패면 빈 문자열
    chars: int
    error: str | None


class SummaryItem(TypedDict):
    """요약 하나. 같은 duplicate_group 은 하나로 묶여 여기 한 항목이 된다."""
    summary_id: int
    title: str
    summary: str
    article_ids: list[int]  # 근거가 된 기사. primary 만 들어간다
    duplicate_group: int    # 0 이면 묶이지 않은 단독 건
    sources: list[Source]


class NewsState(TypedDict, total=False):
    # --- 입력 ---------------------------------------------------------
    company: str
    aliases: tuple[str, ...]
    top_n: int
    topic: str
    time_range: str | None
    max_results: int
    search_depth: str
    client: httpx.AsyncClient    # Tavily·LLM 이 커넥션 풀을 공유한다

    # --- search -------------------------------------------------------
    search_results: list[QueryOutcome]              # Query 별 성패·건수
    raw_results: list[tuple[str, list[dict]]]       # (카테고리, Tavily results) 원본

    # --- merge --------------------------------------------------------
    merged_results: list[NewsItem]                  # 후보. 여기 순서가 article_id 를 정한다

    # --- rerank -------------------------------------------------------
    ranked_results: list[RankedItem]                # 후보 전체, 순위순. 후보는 사라지지 않는다
    unranked_ids: list[int]                         # LLM 이 빠뜨려 코드가 뒤에 붙인 것
    dropped_rankings: list[Dropped]                 # 코드가 걸러낸 응답 항목

    # --- quality_check ------------------------------------------------
    search_quality: Quality
    search_quality_reason: str
    selected_article_ids: list[int]                 # 다음 단계(Extract) 대상

    # --- extract ------------------------------------------------------
    extracted_items: list[ExtractedItem]    # 성공·실패 모두. 실패는 ok=False 로 남는다

    # --- summarize ----------------------------------------------------
    summaries: list[SummaryItem]
    sources: list[Source]                   # 전체 평탄화. API 가 쓰기 쉽게 한 벌 더 둔다

    # --- 공통 ----------------------------------------------------------
    status: Status
    errors: list[str]


def selected_items(state: NewsState) -> list[RankedItem]:
    """selected_article_ids 를 실제 기사로 되돌린다. 순위 순서를 지킨다.

    다음 단계(Extract)가 넘겨받을 목록이 여기 하나로 정해진다.
    """
    chosen = set(state.get("selected_article_ids") or [])

    return [item for item in state.get("ranked_results") or [] if item["article_id"] in chosen]
