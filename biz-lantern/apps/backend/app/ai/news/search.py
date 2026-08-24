"""
기업명 하나로 뉴스를 검색한다. 이 단계는 검색까지만이고 파일을 만들지 않는다.

    기업명 -> Query 2개 병렬 검색 -> URL 검증 -> 중복 병합 -> 카테고리 태그

두 Query 를 동시에 던져 제품/서비스와 사업화를 따로 긁고, 겹치는 기사는 버리지 않고
categories 를 합친다. 양쪽에 다 잡혔다는 건 신호가 강하다는 뜻이라 다음 단계(Ranking)가
쓸 정보다.

url·제목·날짜·score·스니펫은 전부 Tavily 응답에 있는 값만 쓴다. 없으면 None 으로 남기고
만들어내지 않는다.
"""
import asyncio
import logging
from typing import TypedDict

import httpx

from app.ai.news import tavily_client
from app.ai.news.queries import build_queries
from app.ai.news.tavily_client import TavilySearchError
from app.ai.news.urls import canonical_key, is_extractable_url

# month 는 비상장 중소기업에 너무 좁다. 4개사 실측에서 무명 기업은 한 달 치 기사가
# 한두 건뿐이라 사실상 검색이 성립하지 않았다. year 를 기본으로 둔다.
DEFAULT_TIME_RANGE = "year"
DEFAULT_MAX_RESULTS = 10
DEFAULT_SEARCH_DEPTH = "basic"
DEFAULT_TOPIC = "news"

# Tavily 관련도 점수 하한. 이걸 두는 이유는 응답이 재현되지 않기 때문이다 - 같은 기업·같은
# Query 를 세 번 돌렸더니 회사명 언급률이 38% / 93% / 45% 로 흔들렸다. 관련 기사가 모자라면
# Tavily 가 무관한 기사로 빈자리를 채우는데, 그 채움 결과는 점수가 일관되게 낮았다
# (쓰레기 0.01~0.05 / 정상 0.13~0.82). 그래서 점수로 자르면 흔들림을 상당 부분 걷어낼 수 있다.
#
# 4개사 73건으로 잰 값 (회사명이 실제로 등장하는가를 정답으로 봄):
#
#     하한선   남은건수   정밀도   정답유지율
#      0.00       73      84%      100%
#      0.05       65      94%      100%
#      0.08       62      98%      100%   <- 채택. 오답 12건 중 11건을 걷어내고 정답은 안 잃는다
#      0.10       61      98%       98%
#      0.20       56     100%       92%
#
# 0.0 을 주면 이 필터는 꺼진다. 몇 건이 잘렸는지는 결과의 dropped_low_score 에 남는다.
MIN_SCORE = 0.08

logger = logging.getLogger(__name__)


class NewsItem(TypedDict):
    url: str                    # Tavily 가 준 원본 문자열. 가공하지 않는다
    title: str | None
    published_date: str | None
    score: float | None
    content: str | None         # Tavily 가 준 스니펫
    categories: list[str]       # 이 기사를 데려온 Query 들. ["product"] / ["business"] / 둘 다


class QueryOutcome(TypedDict):
    category: str
    query: str                  # 실제로 Tavily 에 보낸 문자열
    count: int                  # 응답에 들어 있던 원본 건수
    error: str | None           # 이 Query 만 실패했을 때의 사유


class NewsSearchResult(TypedDict):
    company: str
    items: list[NewsItem]
    queries: list[QueryOutcome]
    dropped_low_score: int      # 점수 하한선에 걸려 빠진 건수. 조용히 사라지지 않게 남긴다


def _reason(error: BaseException) -> str:
    """예외를 결과에 실을 한 줄로. 타입을 남겨야 무엇이 터졌는지 알 수 있다."""
    return f"{type(error).__name__}: {(str(error).splitlines() or [''])[0]}"


def merge_results(
    tagged: list[tuple[str, list[dict]]],
    *,
    min_score: float = MIN_SCORE,
) -> tuple[list[NewsItem], int]:
    """(카테고리, Tavily results) 들을 하나의 목록으로 합친다.

    무효 URL 과 점수 미달을 걸러내고 canonical_key 로 중복을 판정한다. 이미 본 기사면
    버리지 않고 categories 에 카테고리만 더한다 - 두 Query 에 다 잡혔다는 건 신호가
    강하다는 뜻이라 다음 단계가 쓸 정보다. 순서는 넘어온 순서(= product 먼저)를 보존한다.

    반환값은 (기사 목록, 점수 미달로 뺀 건수).
    """
    items: list[NewsItem] = []
    by_key: dict[str, NewsItem] = {}
    dropped = 0

    for category, results in tagged:
        for entry in results:
            if not isinstance(entry, dict):
                continue

            url = (entry.get("url") or "").strip()
            if not is_extractable_url(url):
                continue

            score = entry.get("score")
            # 점수가 없으면 판단할 근거가 없으므로 자르지 않는다. 있는 값만 가지고 거른다.
            if min_score > 0 and isinstance(score, (int, float)) and score < min_score:
                dropped += 1
                continue

            key = canonical_key(url)

            seen = by_key.get(key)
            if seen is not None:
                if category not in seen["categories"]:
                    seen["categories"].append(category)
                # 같은 기사를 양쪽에서 잡았으면 더 높은 점수를 남긴다
                if isinstance(score, (int, float)) and (
                    not isinstance(seen["score"], (int, float)) or score > seen["score"]
                ):
                    seen["score"] = score
                continue

            item: NewsItem = {
                "url": url,
                "title": entry.get("title"),
                "published_date": entry.get("published_date"),
                "score": score,
                "content": entry.get("content"),
                "categories": [category],
            }
            by_key[key] = item
            items.append(item)

    return items, dropped


async def search_company_news(
    company: str,
    *,
    topic: str = DEFAULT_TOPIC,
    time_range: str | None = DEFAULT_TIME_RANGE,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = DEFAULT_SEARCH_DEPTH,
    min_score: float = MIN_SCORE,
    client: httpx.AsyncClient | None = None,
) -> NewsSearchResult:
    """기업명 하나로 두 갈래 Query 를 병렬 검색해 합친 결과를 돌려준다.

    한쪽 Query 가 실패해도 나머지는 살린다 - 사유는 queries[].error 에 남는다.
    둘 다 실패했을 때만 예외를 올린다. 빈 결과로 덮을 문제가 아니기 때문이다.

    client 를 주면 그걸 쓰고, 주지 않으면 여기서 만들어 쓰고 닫는다.
    """
    if client is not None:
        return await _run(
            client, company, topic, time_range, max_results, search_depth, min_score
        )

    async with httpx.AsyncClient() as owned:
        return await _run(
            owned, company, topic, time_range, max_results, search_depth, min_score
        )


async def _run(
    client: httpx.AsyncClient,
    company: str,
    topic: str,
    time_range: str | None,
    max_results: int,
    search_depth: str,
    min_score: float,
) -> NewsSearchResult:
    outcomes, tagged = await run_searches(
        client,
        company,
        topic=topic,
        time_range=time_range,
        max_results=max_results,
        search_depth=search_depth,
    )
    items, dropped = merge_results(tagged, min_score=min_score)

    return {
        "company": company,
        "items": items,
        "queries": outcomes,
        "dropped_low_score": dropped,
    }


async def run_searches(
    client: httpx.AsyncClient,
    company: str,
    *,
    topic: str = DEFAULT_TOPIC,
    time_range: str | None = DEFAULT_TIME_RANGE,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = DEFAULT_SEARCH_DEPTH,
) -> tuple[list[QueryOutcome], list[tuple[str, list[dict]]]]:
    """두 갈래 Query 를 병렬로 던지고 **병합하지 않은 채** 돌려준다.

    반환값은 (Query 별 성패, [(카테고리, Tavily results)]). 병합은 다음 단계의 몫이라
    여기서 하지 않는다 - 워크플로에서 search 와 merge 가 다른 Node 이기 때문이다.

    한쪽 Query 가 실패해도 나머지는 살린다. 둘 다 실패했을 때만 예외를 올린다.
    """
    queries = build_queries(company)

    responses = await asyncio.gather(
        *(
            tavily_client.search(
                client,
                query,
                topic=topic,
                time_range=time_range,
                max_results=max_results,
                search_depth=search_depth,
            )
            for _, query in queries
        ),
        # 한쪽이 깨져도 나머지 결과를 받아야 하므로 예외를 값으로 받는다
        return_exceptions=True,
    )

    outcomes: list[QueryOutcome] = []
    tagged: list[tuple[str, list[dict]]] = []

    for (category, query), response in zip(queries, responses, strict=True):
        if isinstance(response, BaseException):
            detail = _reason(response)
            logger.warning("검색 실패 (category=%s query=%s): %s", category, query, detail)
            outcomes.append({"category": category, "query": query, "count": 0, "error": detail})
            continue

        results = [entry for entry in (response.get("results") or []) if isinstance(entry, dict)]
        outcomes.append({"category": category, "query": query, "count": len(results), "error": None})
        tagged.append((category, results))

    if not tagged:
        first = next(outcome["error"] for outcome in outcomes if outcome["error"])
        raise TavilySearchError(f"검색이 모두 실패함: {first}")

    return outcomes, tagged
