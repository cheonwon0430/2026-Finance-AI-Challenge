"""
추출한 원문으로 요약을 만들고 출처를 연결한다.

**묶기는 코드가 한다.** LLM 에게 "알아서 같은 사건끼리 묶어라"고 맡기지 않는다.
duplicate_group 은 rerank 가 이미 내린 판단이고 여기서는 그걸 집행하기만 한다.
LLM 이 하는 일은 묶인 덩어리마다 글을 쓰는 것뿐이다.

    rerank      기사끼리 같은 사건인지 판단        -> duplicate_group
    코드        그 값으로 그룹을 만든다            -> [그룹 1] [그룹 2] ...
    LLM        그룹마다 요약을 하나씩 쓴다         -> {"group": 1, "title", "summary"}
    코드        그룹에 출처를 붙인다               -> primary + related

출처 URL 은 LLM 을 거치지 않는다. 코드가 검색 결과에서 그대로 옮긴다.

rerank.py / quality.py 와 같은 계층 규칙을 따른다 - 네트워크를 타지 않고, LLM 호출은
nodes 가 한다.

    [1] 설정
    [2] 묶기          duplicate_group -> 그룹
    [3] 요청 만들기
    [4] 응답 읽기
    [5] 검증 · 출처 연결
"""
import json
import logging
import re
from typing import TypedDict

from app.ai.news.llm_client import LLMError
from app.ai.news.signals import source_of
from app.ai.news.state import ExtractedItem, RankedItem, Source, SummaryItem

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
# 기사 하나에서 LLM 에 넣을 원문 상한. Tavily 가 주는 본문은 페이지 전체라 사이트 메뉴가
# 함께 딸려온다(기존 파이프라인 실측 최대 25,045자). 평소에는 안 걸리지만 비정상적으로 큰
# 페이지 하나가 요청을 통째로 망가뜨리는 걸 막는 안전밸브다.
MAX_BODY_CHARS = 30_000
TRUNCATION_MARK = "\n\n…(원문이 길어 이후 생략됨)"

# 요약 본문에 URL 이 섞여 나오면 지운다. 원문에서 베낀 것이든 지어낸 것이든, 출처는
# sources 로만 표시해야 코드가 검증할 수 있다.
_URL_IN_TEXT = re.compile(r"\(?\s*(?:https?://|www\.)\S+\)?", re.IGNORECASE)

SCHEMA_NAME = "news_summaries"

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "summaries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "group": {"type": "integer"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["group", "title", "summary"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summaries"],
    "additionalProperties": False,
}

logger = logging.getLogger(__name__)


class Group(TypedDict):
    number: int                     # LLM 과 주고받는 그룹 번호. 1부터
    duplicate_group: int            # rerank 가 준 값. 0 이면 단독 건
    items: list[ExtractedItem]      # 이 그룹에서 원문을 읽은 기사들


class Draft(TypedDict):
    group: int
    title: str
    summary: str


class Dropped(TypedDict):
    group: int
    reason: str


# ---------------------------------------------------------------------------
# [2] 묶기
# ---------------------------------------------------------------------------
def build_groups(extracted: list[ExtractedItem], ranked: list[RankedItem]) -> list[Group]:
    """추출 성공분을 duplicate_group 으로 묶는다. 실패한 것은 묶을 내용이 없어 제외한다.

    duplicate_group == 0 인 기사는 **각자 하나의 그룹**이 된다. 0 을 그대로 키로 쓰면
    서로 무관한 기사가 전부 한 요약으로 뭉쳐 버린다 - 여기가 실수하기 쉬운 지점이다.

    순서는 ranked_results 의 순위를 따른다. 위에 있는 기사가 먼저 나온다.
    """
    group_of = {item["article_id"]: item.get("duplicate_group", 0) for item in ranked}
    rank_of = {item["article_id"]: item.get("rank", 0) for item in ranked}

    buckets: dict[tuple[str, int], Group] = {}

    for item in sorted(extracted, key=lambda entry: rank_of.get(entry["article_id"], 0)):
        if not item["ok"]:
            continue

        duplicate_group = group_of.get(item["article_id"], 0)
        key = ("dup", duplicate_group) if duplicate_group > 0 else ("solo", item["article_id"])

        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {
                "number": len(buckets) + 1,
                "duplicate_group": duplicate_group,
                "items": [item],
            }
            continue

        bucket["items"].append(item)

    return list(buckets.values())


def collect_sources(
    group: Group,
    ranked: list[RankedItem],
    selected_ids: set[int],
) -> list[Source]:
    """그룹 하나에 붙일 출처를 만든다. primary 먼저, 그다음 related.

    primary  이 그룹에서 원문을 읽은 기사
    related  같은 duplicate_group 이지만 선정되지 않아 원문을 읽지 않은 기사

    related 는 검색 결과에 이미 있는 url·제목을 옮겨 붙일 뿐이다. 요약의 근거가 아니다.
    duplicate_group 이 0 인 단독 건에는 related 가 붙지 않는다.
    """
    sources: list[Source] = []
    seen: set[int] = set()

    for item in group["items"]:
        sources.append({
            "article_id": item["article_id"],
            "title": item["title"],
            "url": item["url"],
            "site": item["site"],
            "role": "primary",
        })
        seen.add(item["article_id"])

    duplicate_group = group["duplicate_group"]
    if duplicate_group <= 0:
        return sources

    for entry in ranked:
        article_id = entry["article_id"]

        if entry.get("duplicate_group", 0) != duplicate_group:
            continue
        if article_id in seen or article_id in selected_ids:
            continue

        url = entry["url"]
        sources.append({
            "article_id": article_id,
            "title": entry["title"],
            "url": url,
            "site": source_of(url),
            "role": "related",
        })
        seen.add(article_id)

    return sources


# ---------------------------------------------------------------------------
# [3] 요청 만들기
# ---------------------------------------------------------------------------
def build_instructions(company: str) -> str:
    """요약 지시. 형식은 SUMMARY_SCHEMA 가 강제하므로 '무엇을 쓸지'만 말한다."""
    return f"""
아래는 '{company}'에 관한 자료 원문이다. [그룹 N] 으로 묶여 있다.

**그룹마다 요약을 하나씩 쓴다.** 한 그룹 안의 자료들은 같은 사건이나 같은 내용을 다루므로
절대 나누지 않는다. 그룹이 다르면 별개의 요약으로 쓴다.

요약에 담을 것:
- 무엇이 발생했는가, 이 기업이 무엇을 했는가
- 어떤 제품·서비스·사업과 관련되는가
- 주요 고객·파트너·대상은 누구인가
- 사업적으로 어떤 의미가 있는가

지켜야 할 것:
- 원문에 실제로 있는 내용만 쓴다. 없는 내용을 추론하거나 만들어내지 않는다.
- 숫자, 날짜, 회사명, 서비스명은 원문에 나온 그대로 쓴다.
- 기사 서론, 수식어, "~라고 밝혔다" 같은 상투구는 걷어낸다. 사실만 남긴다.
- **사건이 없는 자료도 들어온다.** 회사 소개나 제품 소개 페이지라면 억지로 사건처럼
  쓰지 말고, 그 제품·서비스가 무엇이고 무엇을 할 수 있는지 명확히 설명한다.
- 원문에는 사이트 메뉴나 광고가 섞여 있다. 본문만 보고 판단한다.
- 한국어로 쓴다.

title 은 그 내용을 한 줄로 압축한 제목이다. summary 는 2~5문장으로 쓴다.
"""


def build_digest(groups: list[Group], *, max_body_chars: int = MAX_BODY_CHARS) -> tuple[str, list[str]]:
    """그룹들을 LLM 이 읽을 텍스트로. **URL 은 넣지 않는다.**

    반환값은 (본문 블록, 잘린 기사 제목 목록). 잘림은 조용히 지나가지 않게 남긴다.
    """
    blocks = []
    truncated: list[str] = []

    for group in groups:
        lines = [f"[그룹 {group['number']}]"]

        for item in group["items"]:
            title = (item["title"] or "").strip() or "(제목 없음)"
            body = item["content"]

            if len(body) > max_body_chars:
                body = body[:max_body_chars] + TRUNCATION_MARK
                truncated.append(title)

            lines.append(f"--- 자료: {title}\n{body}")

        blocks.append("\n\n".join(lines))

    return "\n\n" + ("\n\n" + "=" * 60 + "\n\n").join(blocks), truncated


# ---------------------------------------------------------------------------
# [4] 응답 읽기
# ---------------------------------------------------------------------------
def parse_summaries(response: dict) -> list[Draft]:
    """Chat Completions 응답에서 요약을 꺼낸다.

    거부·형식 오류를 조용히 빈 요약으로 만들지 않는다. 빈 요약과 실패는 다른 사건이다.
    """
    choices = response.get("choices") or []
    if not choices:
        raise LLMError(f"응답에 choices 가 없음: {json.dumps(response, ensure_ascii=False)[:200]}")

    message = choices[0].get("message") or {}

    refusal = message.get("refusal")
    if refusal:
        raise LLMError(f"모델이 요청을 거부함: {refusal}")

    content = (message.get("content") or "").strip()
    if not content:
        raise LLMError("응답 본문이 비어 있음")

    try:
        parsed = json.loads(content)
    except ValueError as error:
        raise LLMError(f"JSON 파싱 실패: {error} / 본문: {content[:200]}") from error

    summaries = parsed.get("summaries") if isinstance(parsed, dict) else None
    if not isinstance(summaries, list):
        raise LLMError(f"summaries 배열이 없음: {content[:200]}")

    drafts: list[Draft] = []
    for item in summaries:
        if not isinstance(item, dict):
            continue

        # 번호가 문자열로 오는 게이트웨이가 있어 int 로 맞춰 본다
        try:
            number = int(item["group"])
        except (KeyError, TypeError, ValueError):
            continue

        drafts.append({
            "group": number,
            "title": str(item.get("title") or "").strip(),
            "summary": str(item.get("summary") or "").strip(),
        })

    return drafts


# ---------------------------------------------------------------------------
# [5] 검증 · 출처 연결
# ---------------------------------------------------------------------------
def _strip_urls(text: str) -> str:
    """요약 본문에서 URL 을 지운다. 출처는 sources 로만 표시한다."""
    return re.sub(r"\s{2,}", " ", _URL_IN_TEXT.sub("", text)).strip()


def resolve(
    groups: list[Group],
    drafts: list[Draft],
    ranked: list[RankedItem],
    selected_ids: set[int],
) -> tuple[list[SummaryItem], list[Dropped]]:
    """그룹 번호를 요약으로 되돌리고 출처를 붙인다. 여기가 마지막 방어선이다.

    반환값은 (요약 목록, 버린 것과 사유).

    LLM 은 group 번호와 글만 돌려준다. article_ids 와 sources 는 코드가 만든다 -
    URL 이 LLM 을 거치지 않으므로 지어낼 통로가 없다.
    """
    by_number = {group["number"]: group for group in groups}
    dropped: list[Dropped] = []
    seen: set[int] = set()

    summaries: list[SummaryItem] = []

    for draft in drafts:
        number = draft["group"]
        group = by_number.get(number)

        if group is None:
            dropped.append({"group": number, "reason": f"없는 그룹 번호 (1~{len(groups)})"})
            continue

        if number in seen:
            dropped.append({"group": number, "reason": "중복 응답"})
            continue

        summary = _strip_urls(draft["summary"])
        if not summary:
            dropped.append({"group": number, "reason": "요약 본문이 비어 있음"})
            continue

        seen.add(number)
        summaries.append({
            "summary_id": len(summaries) + 1,
            "title": _strip_urls(draft["title"]) or (group["items"][0]["title"] or "(제목 없음)"),
            "summary": summary,
            "article_ids": [item["article_id"] for item in group["items"]],
            "duplicate_group": group["duplicate_group"],
            "sources": collect_sources(group, ranked, selected_ids),
        })

    # LLM 이 통째로 빠뜨린 그룹. 조용히 사라지게 두지 않는다
    for group in groups:
        if group["number"] not in seen:
            dropped.append({"group": group["number"], "reason": "LLM 응답에 없음"})

    if dropped:
        logger.warning("요약에서 %d건을 걸러냄: %s", len(dropped), dropped)

    return summaries, dropped


def flatten_sources(summaries: list[SummaryItem]) -> list[Source]:
    """요약별 출처를 한 벌로 편다. API 가 전체 출처 목록을 쓰기 쉽게 하려는 것."""
    flat: list[Source] = []
    seen: set[int] = set()

    for summary in summaries:
        for source in summary["sources"]:
            if source["article_id"] in seen:
                continue

            seen.add(source["article_id"])
            flat.append(source)

    return flat
