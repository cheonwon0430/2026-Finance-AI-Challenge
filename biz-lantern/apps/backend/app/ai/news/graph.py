"""
뉴스 검색 워크플로.

    START -> search -> merge -> rerank -> quality_check -> END

조건부 엣지를 두지 않았다. 후보 0건이나 rerank 실패는 Node 안에서 흡수하고 그래프는
직선으로 둔다 - 분기를 넣는 순간 "어느 경로로 갔는지" 를 따로 추적해야 하는데, 지금은
그럴 만큼 경우가 많지 않다.

다음 단계에서 Extract·요약이 붙을 자리는 quality_check 뒤다. 그때 마지막 엣지를

    quality_check -> END

에서

    quality_check --(sufficient)--> extract -> summarize -> END
                  \\--(insufficient)--> END

로 바꾸면 된다. 넘길 기사 목록은 이미 selected_article_ids 로 정해져 있어서
Node 를 더 붙여도 앞 단계를 고칠 일이 없다.
"""
import httpx
from langgraph.graph import END, START, StateGraph

from app.ai.news import llm_client
from app.ai.news.nodes import (
    extract_node,
    merge_node,
    quality_check_node,
    rerank_node,
    search_node,
    summarize_node,
)
from app.ai.news.search import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_SEARCH_DEPTH,
    DEFAULT_TIME_RANGE,
    DEFAULT_TOPIC,
)
from app.ai.news.state import DEFAULT_TOP_N, NewsState

NODE_ORDER = ("search", "merge", "rerank", "quality_check", "extract", "summarize")


def route_after_quality(state: NewsState) -> str:
    """넘길 기사가 있을 때만 원문 추출로 간다.

    no_relevant_news 는 물론이고 no_candidates·error 도 selected_article_ids 가 비어
    있으므로 같은 문으로 끝난다. 읽을 것이 없는데 Extract 크레딧을 쓰지 않는다.
    """
    if state.get("status") == "no_relevant_news" or not state.get("selected_article_ids"):
        return END

    return "extract"


def build_news_graph():
    """워크플로를 조립한다. 그래프 모양만 여기서 정하고 일은 Node 가 한다."""
    graph = StateGraph(NewsState)

    graph.add_node("search", search_node)
    graph.add_node("merge", merge_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("quality_check", quality_check_node)
    graph.add_node("extract", extract_node)
    graph.add_node("summarize", summarize_node)

    graph.add_edge(START, "search")
    graph.add_edge("search", "merge")
    graph.add_edge("merge", "rerank")
    graph.add_edge("rerank", "quality_check")
    graph.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"extract": "extract", END: END},
    )
    graph.add_edge("extract", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()


def initial_state(
    company: str,
    *,
    top_n: int = DEFAULT_TOP_N,
    aliases: tuple[str, ...] = (),
    topic: str = DEFAULT_TOPIC,
    time_range: str | None = DEFAULT_TIME_RANGE,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = DEFAULT_SEARCH_DEPTH,
    client: httpx.AsyncClient,
) -> NewsState:
    """입력만 채운 State. 나머지는 Node 가 단계마다 채운다."""
    if not company.strip():
        raise ValueError("기업명이 비어 있습니다.")
    if top_n < 1:
        raise ValueError(f"top_n 은 1 이상이어야 합니다. (요청 {top_n})")

    return {
        "company": company.strip(),
        "aliases": tuple(aliases),
        "top_n": top_n,
        "topic": topic,
        "time_range": time_range,
        "max_results": max_results,
        "search_depth": search_depth,
        "client": client,
        "status": "ok",
        "errors": [],
    }


async def run_news_workflow(
    company: str,
    *,
    top_n: int = DEFAULT_TOP_N,
    aliases: tuple[str, ...] = (),
    topic: str = DEFAULT_TOPIC,
    time_range: str | None = DEFAULT_TIME_RANGE,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_depth: str = DEFAULT_SEARCH_DEPTH,
    client: httpx.AsyncClient | None = None,
) -> NewsState:
    """기업명 하나로 워크플로를 끝까지 돌리고 최종 State 를 돌려준다.

    검색이 통째로 실패하면 예외가 올라온다 - 빈 결과로 덮을 문제가 아니다. 그 뒤 단계의
    실패는 State 의 status / errors 로 나타난다.

    client 를 주면 그걸 쓰고, 주지 않으면 여기서 만들어 Tavily·LLM 양쪽에 쓰고 닫는다.
    """
    # 설정이 없으면 검색을 태우기 전에 멈춘다. 어차피 rerank 에서 죽을 일이다.
    llm_client.ensure_configured()

    async def run(active: httpx.AsyncClient) -> NewsState:
        return await build_news_graph().ainvoke(
            initial_state(
                company,
                top_n=top_n,
                aliases=aliases,
                topic=topic,
                time_range=time_range,
                max_results=max_results,
                search_depth=search_depth,
                client=active,
            )
        )

    if client is not None:
        return await run(client)

    async with httpx.AsyncClient() as owned:
        return await run(owned)
