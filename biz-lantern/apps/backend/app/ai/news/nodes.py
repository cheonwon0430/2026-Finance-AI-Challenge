"""
워크플로 Node. 하나가 단계 하나를 맡고, 자기가 채우는 State 조각만 돌려준다.

    search        Tavily 두 갈래 Query 를 병렬로 던진다
    merge         후보 하나의 목록으로 합친다. 명백한 중복만 지운다
    rerank        LLM 이 순위를 매긴다. 후보는 사라지지 않는다
    quality_check LLM 이 목록 전체의 쓸모를 판단한다
    extract       선정된 기사의 원문을 가져온다
    summarize     원문으로 요약을 만들고 출처를 붙인다

**실패를 어디까지 치명적으로 볼지는 Node 마다 다르다.**

    search        전부 실패하면 예외를 올린다. 뒤 단계가 성립하지 않는다
    merge         실패할 것이 없다. 후보 0건은 오류가 아니다
    rerank        실패해도 계속 간다. 검색 순서를 유지하고 errors 에 남긴다
    quality_check 실패해도 계속 간다. status="error" 로 판단이 없음을 알린다
    extract       기사 하나 실패는 그 기사만. 전부 실패해야 error 다
    summarize     실패해도 예외를 올리지 않는다. 원문은 이미 손에 있다

프롬프트와 검증은 rerank.py / quality.py 에 있다. 여기는 그 둘을 LLM 호출과 이어 붙이고
State 를 채우는 일만 한다.
"""
import logging

from app.ai.news import llm_client, quality, rerank, summarize, tavily_client
from app.ai.news.search import merge_results, run_searches
from app.ai.news.signals import source_of
from app.ai.news.state import ExtractedItem, NewsState, RankedItem, selected_items
from app.ai.news.urls import canonical_key

logger = logging.getLogger(__name__)


def _reason(error: BaseException) -> str:
    """예외를 State 에 실을 한 줄로. 타입을 남겨야 무엇이 터졌는지 알 수 있다."""
    return f"{type(error).__name__}: {(str(error).splitlines() or [''])[0]}"


def _errors(state: NewsState, detail: str) -> list[str]:
    return [*(state.get("errors") or []), detail]


async def search_node(state: NewsState) -> NewsState:
    """[1/4] Tavily 검색. product/business 두 Query 를 병렬로 던진다.

    검색 로직도 Query 도 이 단계에서 바꾸지 않는다. run_searches 가 하던 그대로다.
    """
    outcomes, tagged = await run_searches(
        state["client"],
        state["company"],
        topic=state["topic"],
        time_range=state["time_range"],
        max_results=state["max_results"],
        search_depth=state["search_depth"],
    )

    return {"search_results": outcomes, "raw_results": tagged}


async def merge_node(state: NewsState) -> NewsState:
    """[2/4] 후보 병합. **점수로 자르지 않는다.**

    canonical URL 이 같은 것만 하나로 친다 (www / utm_* / 끝 슬래시 / 앵커 차이). 같은
    사건을 다룬 서로 다른 기사는 URL 이 달라 그대로 남고, 묶는 판단은 rerank 가 한다.

    양쪽 Query 에 다 잡힌 기사는 버리지 않고 categories 를 합친다.
    """
    items, _ = merge_results(state["raw_results"], min_score=0.0)

    if not items:
        return {"merged_results": [], "status": "no_candidates"}

    return {"merged_results": items}


async def rerank_node(state: NewsState) -> NewsState:
    """[3/4] LLM 재정렬. 후보를 지우지 않고 순서만 바꾼다.

    실패해도 예외를 올리지 않는다. 후보는 이미 손에 있고, 순위를 못 매겼다고 아무것도
    못 돌려주는 것보다 검색 순서대로라도 넘기는 편이 낫다. 사유는 errors 에 남는다.
    """
    items = state.get("merged_results") or []
    if not items:
        return {"ranked_results": [], "unranked_ids": [], "dropped_rankings": []}

    company = state["company"]
    aliases = state["aliases"]

    try:
        response = await llm_client.complete_json(
            state["client"],
            rerank.build_instructions(company, state["top_n"], aliases),
            rerank.build_digest(items),
            rerank.RERANK_SCHEMA,
            rerank.SCHEMA_NAME,
        )
        rankings = rerank.parse_rerank(response)
    except Exception as error:  # noqa: BLE001 - rerank 실패로 검색 결과를 버리지 않는다
        detail = f"rerank: {_reason(error)}"
        logger.warning("rerank 실패 (company=%s): %s", company, detail)

        return {
            "ranked_results": rerank.fallback(items),
            "unranked_ids": [],
            "dropped_rankings": [],
            "errors": _errors(state, detail),
        }

    ranked, unranked, dropped = rerank.resolve(items, rankings)

    return {
        "ranked_results": ranked,
        "unranked_ids": unranked,
        "dropped_rankings": dropped,
    }


async def quality_check_node(state: NewsState) -> NewsState:
    """[4/4] 검색 품질 판단. 이 목록으로 기업의 최신 동향을 파악할 수 있는가.

    고정 threshold 를 쓰지 않는다. 기업마다 후보 분포가 달라 "몇 점 이상 몇 건" 같은
    규칙은 번번이 어긋난다.

    판단이 실패하면 status="error" 를 세운다. insufficient 로 적으면 '판단해 보니
    부족하다' 와 구별할 수 없기 때문이다.
    """
    ranked = state.get("ranked_results") or []

    if not ranked:
        # 물어볼 것이 없다. LLM 을 부르지 않는다.
        return {
            "search_quality": "insufficient",
            "search_quality_reason": "검색 후보가 없습니다.",
            "selected_article_ids": [],
            "status": state.get("status") or "no_candidates",
        }

    company = state["company"]
    aliases = state["aliases"]
    top_n = state["top_n"]

    try:
        response = await llm_client.complete_json(
            state["client"],
            quality.build_instructions(company, top_n, aliases),
            quality.build_digest(ranked),
            quality.QUALITY_SCHEMA,
            quality.SCHEMA_NAME,
        )
        judgement = quality.parse_quality(response)
    except Exception as error:  # noqa: BLE001 - 판단 실패로 앞 단계 결과를 버리지 않는다
        detail = f"quality_check: {_reason(error)}"
        logger.warning("품질 판단 실패 (company=%s): %s", company, detail)

        return {
            "search_quality": "insufficient",
            "search_quality_reason": f"품질을 판단하지 못했습니다 ({detail}).",
            "selected_article_ids": [],
            "status": "error",
            "errors": _errors(state, detail),
        }

    resolved = quality.resolve(ranked, judgement, top_n)
    selected = resolved["selected_article_ids"]

    if state.get("errors"):
        # 앞 단계에서 이미 무엇인가 실패했다. 그 상태를 덮지 않는다.
        status = "error"
    elif selected:
        status = "ok"
    else:
        # 판단은 받았는데 넘길 기사가 없다. sufficient 든 insufficient 든 마찬가지다 -
        # 억지로 상위 몇 건을 채워 넘기지 않는다.
        status = "no_relevant_news"

    return {
        "search_quality": resolved["search_quality"],
        "search_quality_reason": resolved["reason"],
        "selected_article_ids": selected,
        "status": status,
    }


async def extract_node(state: NewsState) -> NewsState:
    """[5/6] 선정된 기사의 원문을 가져온다. **selected 만** 추출한다.

    같은 duplicate_group 의 비선정 기사는 읽지 않는다. 그것들은 요약의 근거가 아니라
    '같은 사건을 다룬 다른 보도'로 출처에만 붙는다.

    실패 등급이 셋이다.

        URL 하나 실패    그 항목만 ok=False. errors 는 건드리지 않는다
                        (뉴스는 부분 실패가 정상이다. 한 건 못 읽었다고 워크플로 전체를
                         error 로 만들면 status 가 쓸모없어진다)
        배치 전체 실패    그 배치 항목 전부 ok=False + errors 기록
        성공 0건         errors 기록 + status="error". summarize 는 부를 게 없다
    """
    chosen = selected_items(state)

    if not chosen:
        return {"extracted_items": []}

    company = state["company"]
    errors = list(state.get("errors") or [])
    extracted: list[ExtractedItem] = []

    for batch in _batched(chosen, tavily_client.MAX_EXTRACT_URLS):
        urls = [item["url"] for item in batch]

        try:
            response = await tavily_client.extract(state["client"], urls)
        except Exception as error:  # noqa: BLE001 - 배치 하나가 깨져도 다음 배치는 계속한다
            detail = f"extract: {_reason(error)}"
            logger.warning("원문 추출 배치 실패 (company=%s, %d건): %s", company, len(urls), detail)
            errors.append(detail)
            extracted.extend(_failed(item, detail) for item in batch)
            continue

        extracted.extend(_match(batch, response))

    if not any(item["ok"] for item in extracted):
        detail = "extract: 원문을 한 건도 가져오지 못했습니다."
        logger.warning("%s (company=%s)", detail, company)

        return {
            "extracted_items": extracted,
            "errors": [*errors, detail],
            "status": "error",
        }

    result: NewsState = {"extracted_items": extracted}
    if errors != list(state.get("errors") or []):
        result["errors"] = errors
        result["status"] = "error"

    return result


def _batched(items: list, size: int):
    """Extract 의 한 요청당 개수 제한에 맞춰 자른다."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _failed(item: RankedItem, error: str) -> ExtractedItem:
    return {
        "article_id": item["article_id"],
        "url": item["url"],
        "title": item["title"],
        "site": source_of(item["url"]),
        "ok": False,
        "content": "",
        "chars": 0,
        "error": error,
    }


def _match(batch: list[RankedItem], response: dict) -> list[ExtractedItem]:
    """Extract 응답을 요청한 기사에 되붙인다.

    Extract 가 리다이렉트된 주소를 돌려줄 수 있어 **정확 일치 -> canonical_key** 순으로
    대조한다. Tavily 는 개별 URL 실패를 failed_results[] 로 따로 알려주므로 그 사유를
    그대로 남긴다. 200 이 왔다고 전부 성공한 게 아니다.
    """
    by_url: dict[str, str] = {}
    by_key: dict[str, str] = {}

    for entry in response.get("results") or []:
        if not isinstance(entry, dict):
            continue

        url = (entry.get("url") or "").strip()
        if not url:
            continue

        content = entry.get("raw_content") or ""
        by_url[url] = content
        by_key.setdefault(canonical_key(url), content)

    reported = {
        (entry.get("url") or "").strip(): str(entry.get("error") or "추출 실패")
        for entry in (response.get("failed_results") or [])
        if isinstance(entry, dict)
    }

    results: list[ExtractedItem] = []

    for item in batch:
        url = item["url"]
        content = by_url.get(url)
        if content is None:
            content = by_key.get(canonical_key(url))

        if content:
            results.append({
                "article_id": item["article_id"],
                "url": url,
                "title": item["title"],
                "site": source_of(url),
                "ok": True,
                "content": content,
                "chars": len(content),
                "error": None,
            })
            continue

        if url in reported:
            reason = reported[url]
        elif content is not None:
            # 응답에는 있는데 본문이 비어 있다. 빈 요약을 만들지 않는다
            reason = "본문이 비어 있음"
        else:
            reason = "추출 결과에 해당 URL 이 없음"

        results.append(_failed(item, reason))

    return results


async def summarize_node(state: NewsState) -> NewsState:
    """[6/6] 추출한 원문으로 요약을 만들고 출처를 연결한다.

    묶기는 코드가 한다 - duplicate_group 은 rerank 가 이미 내린 판단이라 여기서 다시
    묻지 않는다. LLM 은 묶인 덩어리마다 글만 쓴다. 출처 URL 은 LLM 을 거치지 않는다.

    실패해도 예외를 올리지 않는다. 원문은 이미 손에 있고, 요약만 다시 돌리면 된다.
    """
    extracted = state.get("extracted_items") or []
    ranked = state.get("ranked_results") or []
    company = state["company"]

    groups = summarize.build_groups(extracted, ranked)
    if not groups:
        return {"summaries": [], "sources": []}

    digest, truncated = summarize.build_digest(groups)
    if truncated:
        logger.info("원문 %d건이 길어 일부 생략됨: %s", len(truncated), truncated)

    try:
        response = await llm_client.complete_json(
            state["client"],
            summarize.build_instructions(company),
            digest,
            summarize.SUMMARY_SCHEMA,
            summarize.SCHEMA_NAME,
        )
        drafts = summarize.parse_summaries(response)
    except Exception as error:  # noqa: BLE001 - 요약 실패로 앞 단계 결과를 버리지 않는다
        detail = f"summarize: {_reason(error)}"
        logger.warning("요약 실패 (company=%s): %s", company, detail)

        return {
            "summaries": [],
            "sources": [],
            "errors": _errors(state, detail),
            "status": "error",
        }

    selected_ids = set(state.get("selected_article_ids") or [])
    summaries, dropped = summarize.resolve(groups, drafts, ranked, selected_ids)

    result: NewsState = {
        "summaries": summaries,
        "sources": summarize.flatten_sources(summaries),
    }

    if not summaries:
        result["errors"] = _errors(state, f"summarize: 쓸 수 있는 요약이 없음 {dropped}")
        result["status"] = "error"

    return result
