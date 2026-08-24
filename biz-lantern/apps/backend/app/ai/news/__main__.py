"""
뉴스 워크플로를 돌려 결과를 눈으로 확인하는 CLI.

    python -m app.ai.news 핀샷
    python -m app.ai.news 비바리퍼블리카 --alias 토스 --alias Toss
    python -m app.ai.news 아이씨비 --top-n 5 --time-range year
    python -m app.ai.news 트래블월렛 --search-only     # 검색·병합까지만 (Query 품질 점검용)

search -> merge -> rerank -> quality_check 까지 돌고 끝난다. 원문 Extract 와 요약은
다음 단계이므로 여기서는 선정된 기사 목록까지만 보여준다.
"""
import argparse
import asyncio
import sys

from app.ai.news.graph import run_news_workflow
from app.ai.news.search import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_SEARCH_DEPTH,
    DEFAULT_TIME_RANGE,
    DEFAULT_TOPIC,
    MIN_SCORE,
    NewsItem,
    NewsSearchResult,
    search_company_news,
)
from app.ai.news.signals import business_signals, mentions_company
from app.ai.news.state import DEFAULT_TOP_N, NewsState, selected_items

LINE = "-" * 62


def _mark(item: NewsItem) -> str:
    """P / B / PB. 어느 Query 가 데려왔는지 한눈에 보려는 것."""
    categories = item["categories"]

    return ("P" if "product" in categories else " ") + ("B" if "business" in categories else " ")


def _print_queries(outcomes: list) -> None:
    for outcome in outcomes:
        head = f"  [{outcome['category']:<8}] {outcome['query']}"
        if outcome["error"]:
            print(f"{head}\n      실패: {outcome['error']}")
        else:
            print(f"{head}  {outcome['count']}건")


def _print_metrics(company: str, items: list) -> None:
    """건수만 보면 안 보이는 것을 숫자로 만든다."""
    if not items:
        return

    mentioned = sum(1 for item in items if mentions_company(item, company))
    with_signal = sum(1 for item in items if business_signals(item))

    print(f"  회사명 언급 {mentioned}/{len(items)} ({mentioned / len(items) * 100:.0f}%)"
          f"  |  사업화 신호어 포함 {with_signal}건")


# ---------------------------------------------------------------------------
# 워크플로 결과
# ---------------------------------------------------------------------------
def print_workflow(state: NewsState) -> None:
    company = state["company"]
    ranked = state.get("ranked_results") or []
    top_n = state["top_n"]

    print(f"\n=== {company} ===\n")

    _print_queries(state.get("search_results") or [])
    print(f"\n  검색 후보: {len(state.get('merged_results') or [])}건")

    if state.get("errors"):
        for detail in state["errors"]:
            print(f"  ! {detail}")

    if not ranked:
        print(f"\n  검색 품질: {state.get('search_quality', 'insufficient').upper()}")
        print(f"  이유: {state.get('search_quality_reason') or '결과 없음'}")

        return

    print("\n  LLM Reranking:  (검색#: 병합 목록에서의 자리, g: 동일 사건 그룹)\n")
    for item in ranked:
        if item["rank"] == top_n + 1:
            print(f"  {LINE} Top {top_n} 경계")

        hit = "O" if mentions_company(item, company) else "X"
        group = f"g{item['duplicate_group']}" if item["duplicate_group"] else "  "
        date = (item["published_date"] or "")[:10] or "          "

        print(f"  {item['rank']:>2} {item['score_rerank']:.2f} {group} {_mark(item)}"
              f" 검색#{item['article_id']:<2} {date} 회사명{hit}  {item['title'] or '(제목 없음)'}")
        if item["reason"]:
            print(f"        {item['reason']}")

    if state.get("unranked_ids"):
        print(f"\n  LLM 이 빠뜨려 뒤에 붙인 후보: {state['unranked_ids']}")
    if state.get("dropped_rankings"):
        print(f"  응답에서 걸러낸 항목: {state['dropped_rankings']}")

    _print_quality(state, company)


def _print_quality(state: NewsState, company: str) -> None:
    quality = state.get("search_quality", "insufficient")

    print(f"\n  검색 품질: {quality.upper()}")
    print(f"  이유: {state.get('search_quality_reason') or '(사유 없음)'}")

    chosen = selected_items(state)

    if not chosen:
        # sufficient 인데 넘길 기사가 없을 수 있다. 억지로 상위 몇 건을 채우지 않기 때문이다.
        status = state.get("status", "ok").upper()
        print(f"  상태: {status} - 다음 단계로 넘길 기사가 없습니다.")

        return

    print(f"\n  선정 기사: {len(chosen)}건")
    for item in chosen:
        date = (item["published_date"] or "")[:10] or "          "
        print(f"    #{item['article_id']:<2} {item['score_rerank']:.2f} {date}"
              f"  {item['title'] or '(제목 없음)'}")

    _print_metrics(company, chosen)
    _print_extract(state)
    _print_summaries(state)


def _print_extract(state: NewsState) -> None:
    """원문 추출 결과. 실패한 것도 사유와 함께 보여준다."""
    extracted = state.get("extracted_items") or []
    if not extracted:
        return

    ok = [item for item in extracted if item["ok"]]
    failed = [item for item in extracted if not item["ok"]]

    print(f"\n  원문 추출: {len(ok)}건 성공 / {len(failed)}건 실패")
    for item in failed:
        print(f"    실패 #{item['article_id']} {item['site']} - {item['error']}")


def _wrap(text: str, width: int = 84) -> list[str]:
    """터미널에서 읽히게 접는다. 단어 경계에서만 자른다."""
    lines: list[str] = []
    current = ""

    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
            continue

        current = f"{current} {word}" if current else word

    if current:
        lines.append(current)

    return lines or [""]


def _print_summaries(state: NewsState) -> None:
    """최종 출력. 출처는 주요(원문 추출)와 관련(같은 사건, 미추출)을 구분해 찍는다."""
    summaries = state.get("summaries") or []
    if not summaries:
        return

    for item in summaries:
        print(f"\n  {item['summary_id']}. {item['title']}")
        for line in _wrap(item["summary"]):
            print(f"     {line}")

        print("\n     출처:")
        for source in item["sources"]:
            mark = " (같은 사건)" if source["role"] == "related" else ""
            print(f"     - {source['site']}{mark}")
            print(f"       {source['url']}")


# ---------------------------------------------------------------------------
# 검색만 (Query 품질 점검용)
# ---------------------------------------------------------------------------
def print_search_only(result: NewsSearchResult) -> None:
    company = result["company"]
    items = result["items"]

    print(f"\n=== {company} (search only) ===\n")

    _print_queries(result["queries"])

    if result["dropped_low_score"]:
        print(f"\n  점수 미달로 제외 {result['dropped_low_score']}건 (--min-score 0 이면 전부 본다)")

    if not items:
        print("\n  결과 없음")

        return

    print(f"\n  병합 {len(items)}건 (P=제품/서비스, B=사업화, PB=양쪽)\n")
    for order, item in enumerate(items, start=1):
        hit = "O" if mentions_company(item, company) else "X"
        score = f"{item['score']:.2f}" if isinstance(item["score"], (int, float)) else "  - "
        date = (item["published_date"] or "")[:10] or "          "

        print(f"  {order:>2} {_mark(item)} {score} {date} 회사명{hit}"
              f"  {item['title'] or '(제목 없음)'}")
        signals = business_signals(item)
        if signals:
            print(f"        신호어: {' '.join(signals)}")

    print()
    _print_metrics(company, items)


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기업명으로 뉴스를 검색해 재정렬하고 검색 품질을 판단한다"
    )
    parser.add_argument("company", nargs="+", help="검색할 기업명 (여러 개 가능)")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help="다음 단계로 넘길 최대 건수")
    parser.add_argument(
        "--alias",
        action="append",
        default=[],
        help="기업 별칭. 여러 번 줄 수 있다 (예: --alias 토스 --alias Toss)",
    )
    parser.add_argument(
        "--time-range",
        default=DEFAULT_TIME_RANGE,
        choices=("day", "week", "month", "year", "all"),
        help="검색 기간. all 이면 기간 제한 없이 검색한다",
    )
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS, help="Query 당 최대 건수")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, choices=("news", "general"))
    parser.add_argument("--search-depth", default=DEFAULT_SEARCH_DEPTH, choices=("basic", "advanced"))
    parser.add_argument(
        "--search-only",
        action="store_true",
        help="검색·병합까지만 돌린다. Query 품질을 볼 때 쓴다",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=MIN_SCORE,
        help=f"--search-only 일 때의 Tavily 점수 하한 (기본 {MIN_SCORE}). 워크플로는 자르지 않는다",
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    time_range = None if args.time_range == "all" else args.time_range

    async def run() -> int:
        failed = 0

        for company in args.company:
            try:
                if args.search_only:
                    print_search_only(await search_company_news(
                        company,
                        topic=args.topic,
                        time_range=time_range,
                        max_results=args.max_results,
                        search_depth=args.search_depth,
                        min_score=args.min_score,
                    ))
                else:
                    print_workflow(await run_news_workflow(
                        company,
                        top_n=args.top_n,
                        aliases=tuple(args.alias),
                        topic=args.topic,
                        time_range=time_range,
                        max_results=args.max_results,
                        search_depth=args.search_depth,
                    ))
            except Exception as error:  # noqa: BLE001 - CLI 최상단. 사람이 읽을 한 줄로 바꾼다
                print(f"\n=== {company} ===\n  실패: {type(error).__name__}: {error}", file=sys.stderr)
                failed += 1

        return 1 if failed else 0

    return asyncio.run(run())


# uv run python -m app.ai.news 핀샷
if __name__ == "__main__":
    sys.exit(main())
