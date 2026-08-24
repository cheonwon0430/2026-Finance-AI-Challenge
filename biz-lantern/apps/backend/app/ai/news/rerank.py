"""
후보 기사를 LLM 이 재정렬한다. 자르는 게 아니라 순서를 매기는 단계다.

핵심 설계는 app/domain/news/selection.py 가 검증한 방식 그대로다.
**LLM 에게 URL 을 보여주지 않는다.**

    후보        {url, title, content, score, ...}   <- url 은 코드만 들고 있는다
    LLM 입력    [1] 제목 | 스니펫 | 메타            (번호 + 판단 재료. url 없음)
    LLM 출력    {"ranked": [{"article_id": 1, ...}]}
    코드        items[article_id - 1] 을 꺼낸다      <- 원본 객체 그대로

LLM 출력에 URL 문자열이 존재하지 않으므로 지어낼 대상 자체가 없다. 그 위에 범위·중복·개수를
코드가 다시 검증한다.

**tavily score 는 LLM 에게 주지 않는다.** 참고 정보로 주더라도 모델이 그 숫자에 끌려간다.
Tavily 의 판단은 "질의어와 얼마나 닮았나"이지 "이 기업에 대해 알 값이 있나"가 아니다.

이 파일은 네트워크를 타지 않는다. LLM 호출은 pipeline 이 하고 여기는 그 응답(dict)만 다룬다.

계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 설정
    [2] 요청 만들기   판정 기준(instructions) + 후보 요약(digest) + 응답 스키마
    [3] 응답 읽기     거부 감지 -> JSON 파싱
    [4] 검증          번호를 후보로 되돌린다. 여기가 마지막 방어선이다.
"""
import json
import logging
from typing import TypedDict

from app.ai.news.llm_client import LLMError
from app.ai.news.signals import business_signals, source_of

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
# 후보 하나당 LLM 에 보여줄 스니펫 길이. 제목만으로는 판단이 어렵고, 전문을 넣을 필요도 없다.
DIGEST_CHARS = 300

SCHEMA_NAME = "news_rerank"

# strict 모드 규격: 모든 object 에 additionalProperties:false, 모든 필드 required.
# 번호 범위와 점수 범위는 스키마로 막지 않는다 - 게이트웨이·모델마다 지원하는 키워드가 다르고,
# 어차피 resolve() 가 코드로 다시 거른다.
RERANK_SCHEMA = {
    "type": "object",
    "properties": {
        "ranked": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "article_id": {"type": "integer"},
                    "rank": {"type": "integer"},
                    "score": {"type": "number"},
                    "reason": {"type": "string"},
                    "duplicate_group": {"type": "integer"},
                },
                "required": ["article_id", "rank", "score", "reason", "duplicate_group"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ranked"],
    "additionalProperties": False,
}

logger = logging.getLogger(__name__)


class Ranking(TypedDict):
    article_id: int
    rank: int
    score: float
    reason: str
    duplicate_group: int   # 0 이면 묶인 그룹 없음


class Dropped(TypedDict):
    article_id: int
    reason: str


# ---------------------------------------------------------------------------
# [2] 요청 만들기
# ---------------------------------------------------------------------------
def build_instructions(company: str, top_n: int, aliases: tuple[str, ...] = ()) -> str:
    """판정 기준.

    형식은 RERANK_SCHEMA(strict json_schema)가 이미 강제하므로 프롬프트는
    '무엇을 보고 판단할지'만 말한다.

    마지막 두 지시가 특히 중요하다.
    - "모든 후보에 점수를 매긴다": 후보가 빈약한 기업에서도 상대 순위가 나와야 한다.
      빼 버리면 고를 폭이 없어진다.
    - "지우지 말고 순위에만 반영한다": 같은 사건 기사가 정보를 조금씩 다르게 담고 있어
      이 단계에서 버리기엔 이르다.
    """
    also = f"\n이 기업은 {', '.join(aliases)} 로도 불린다." if aliases else ""

    return f"""
'{company}'에 대한 웹 검색 결과 목록이다.{also}

각 후보가 이 기업의 제품·서비스·사업을 이해하는 데 얼마나 쓸모 있는지 판단해
0~1 점수를 매기고 순위를 정하라.

판단 기준:
- company_relevance: 제목과 내용에 나오는 기업이 '{company}' 와 실제로 같은 회사인가.
  기업명이 문자열로 들어 있다는 것만으로 관련 있다고 보지 않는다. 이름이 일부만 겹치는
  다른 회사는 다른 회사다 (예: '센트리' 와 '엑스센트리', '토스' 와 '토스카나').

- information_value: 이 기업의 제품·서비스·사업을 이해하는 데 쓸모 있는 정보인가.
  제품·서비스 소개, 기능과 기술, 서비스 운영 방식, 신규 출시, 사업 전략,
  계약·협약·도입, 고객사, 투자, 사업자 선정, 주요 사업 활동이 모두 해당한다.
  **언론 기사가 아니어도 된다.** 회사 공식 홈페이지·제품 소개·블로그라도 그 기업이
  무엇을 만들고 어떻게 서비스하는지 알려 준다면 유용한 정보로 본다.
  자사 문서라는 이유만으로 감점하지 않는다.
  반대로 목록·색인·메인 페이지처럼 이 기업에 대한 내용이 실질적으로 없는 문서는
  형식과 무관하게 낮게 본다.

- business_event: 실제 사업적 사건이나 변화(계약·출시·선정·투자 등)가 담겨 있으면
  더 높게 본다. 다만 사건이 없다고 해서 제품·서비스 정보 자체를 낮게 보지는 않는다.

- ambiguity: 이름만 같거나 비슷한 다른 기업·인물·제품·기관일 가능성

- duplication: 다른 후보와 같은 사건이나 같은 내용을 다루는가

위 요소를 종합해 score 를 정한다. 어느 하나로 결정하지 않는다.

같은 사건을 다루는 기사들에는 duplicate_group 에 같은 번호(1, 2, 3...)를 준다.
어디에도 묶이지 않으면 0 을 준다. 같은 사건이라고 해서 빼지 말고, 그중 가장 내용이
충실한 것을 위에, 나머지를 아래에 두는 식으로 순위에만 반영한다.

**모든 후보에 대해 항목을 하나씩 반환한다.** 관련성이 낮아 보이는 후보도 빼지 말고
낮은 score 를 주어 포함한다. 상위 {top_n}건이 다음 단계로 넘어간다.

reason 에는 그 점수를 준 이유를 한국어 한 문장으로 쓴다.
"""


def _search_type(item: dict) -> str:
    """어느 Query 가 이 기사를 데려왔는지. 양쪽 다면 둘 다 적는다."""
    return "+".join(item.get("categories") or []) or "unknown"


def build_digest(items: list[dict], *, digest_chars: int = DIGEST_CHARS) -> str:
    """후보 목록을 LLM 이 읽을 텍스트로.

    **URL 도, tavily score 도, 회사명 등장 여부도, 날짜도 넣지 않는다.**

    회사명 등장 여부(mentions_company)는 띄어쓰기만 무시한 부분 문자열 비교라 '센트리' 를
    '엑스센트리' 기사에서 찾아냈고, 코드가 미리 내린 그 틀린 답을 LLM 이 그대로 따라갔다.

    published_date 도 같은 이유로 뺐다. Tavily 는 정적 회사소개 페이지(finshot.com/about-us)에
    'Mon, 01 Jun 2026', 나무위키 문서에 'Thu, 20 Aug 2026' 을 실어 보낸다. 크롤링·갱신 시점이지
    발행일이 아니다. "날짜가 최신이니 최신 정보다" 로 이어지는 걸 막으려면 안 보여주는 게 확실하다.

    남는 것은 코드가 **관찰한 사실**뿐이다 - 제목·본문·출처 도메인·어느 Query 가 데려왔는지·
    본문에 실제로 등장한 낱말. 판단은 하나도 넣지 않는다.

    번호는 1부터다. resolve() 가 같은 규칙으로 되돌린다.
    """
    blocks = []

    for number, item in enumerate(items, start=1):
        title = (item.get("title") or "").strip() or "(제목 없음)"
        snippet = " ".join((item.get("content") or "").split())[:digest_chars]
        source = source_of(item.get("url") or "") or "(출처 없음)"
        signals = ", ".join(business_signals(item)) or "없음"

        lines = [
            f"[{number}] {title}",
            f"    출처: {source} | 검색: {_search_type(item)}",
            f"    사업화 신호: {signals}",
        ]
        if snippet:
            lines.append(f"    {snippet}")

        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# [3] 응답 읽기
# ---------------------------------------------------------------------------
def _as_int(value, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_rerank(response: dict) -> list[Ranking]:
    """Chat Completions 응답에서 순위 결과를 꺼낸다.

    거부·형식 오류를 조용히 빈 결과로 만들지 않는다. 빈 결과와 실패는 다른 사건이고,
    여기서 삼키면 파이프라인이 '순위를 못 매겼다'는 사실을 알 방법이 없다.
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

    ranked = parsed.get("ranked") if isinstance(parsed, dict) else None
    if not isinstance(ranked, list):
        raise LLMError(f"ranked 배열이 없음: {content[:200]}")

    rankings: list[Ranking] = []
    for item in ranked:
        if not isinstance(item, dict):
            continue

        # 번호가 문자열로 오는 게이트웨이가 있어 int 로 맞춰 본다. 실패하면 그 항목만 버린다.
        try:
            article_id = int(item["article_id"])
        except (KeyError, TypeError, ValueError):
            continue

        rankings.append({
            "article_id": article_id,
            "rank": _as_int(item.get("rank"), default=0),
            "score": _as_float(item.get("score"), default=0.0),
            "reason": str(item.get("reason") or ""),
            "duplicate_group": _as_int(item.get("duplicate_group"), default=0),
        })

    return rankings


# ---------------------------------------------------------------------------
# [4] 검증 - 마지막 방어선
# ---------------------------------------------------------------------------
def resolve(
    items: list[dict],
    rankings: list[Ranking],
) -> tuple[list[dict], list[int], list[Dropped]]:
    """번호를 후보로 되돌리고 순위를 확정한다.

    반환값은 (순위순 전체 목록, LLM 이 빠뜨린 article_id, 코드가 걸러낸 응답 항목).

    이 단계의 규칙은 하나다 - **후보는 사라지지 않는다.** LLM 이 빠뜨렸든 범위 밖 번호를
    줬든, 결과에는 원래 후보가 전부 들어 있어야 한다. 빠뜨린 것은 맨 뒤에 붙인다.

    LLM 이 준 rank 는 쓰지 않고 score 로 다시 매긴다. 모델이 rank 와 score 를 어긋나게
    돌려주는 일이 있어서, 둘 중 검증 가능한 쪽 하나만 믿는 편이 낫다.
    """
    by_id: dict[int, Ranking] = {}
    dropped: list[Dropped] = []

    for ranking in rankings:
        article_id = ranking["article_id"]

        if not 1 <= article_id <= len(items):
            dropped.append({
                "article_id": article_id,
                "reason": f"후보 범위(1~{len(items)}) 밖",
            })
            continue

        if article_id in by_id:
            dropped.append({"article_id": article_id, "reason": "중복 선택"})
            continue

        by_id[article_id] = ranking

    ordered: list[tuple[float, int, int, dict]] = []
    unranked: list[int] = []

    for order, item in enumerate(items):
        article_id = order + 1
        ranking = by_id.get(article_id)

        if ranking is None:
            unranked.append(article_id)
            entry = {
                **item,
                "article_id": article_id,
                "score_rerank": 0.0,
                "reason": "LLM 응답에 없음",
                "duplicate_group": 0,
            }
            # 점수가 같을 때 LLM 이 실제로 본 기사를 위에 두려고 정렬 키에 1 을 넣는다
            ordered.append((0.0, 1, order, entry))
            continue

        score = min(max(ranking["score"], 0.0), 1.0)
        entry = {
            **item,
            "article_id": article_id,
            "score_rerank": score,
            "reason": ranking["reason"],
            "duplicate_group": max(ranking["duplicate_group"], 0),
        }
        ordered.append((score, 0, order, entry))

    # score 내림차순. 같으면 LLM 이 본 것 우선, 그다음은 원래 순서를 지킨다
    ordered.sort(key=lambda row: (-row[0], row[1], row[2]))

    ranked = []
    for rank, (_, _, _, entry) in enumerate(ordered, start=1):
        entry["rank"] = rank
        ranked.append(entry)

    if dropped:
        logger.warning("rerank 응답에서 %d건을 걸러냄: %s", len(dropped), dropped)
    if unranked:
        logger.warning("LLM 이 %d건을 빠뜨려 뒤에 붙임: %s", len(unranked), unranked)

    return ranked, unranked, dropped


def fallback(items: list[dict]) -> list[dict]:
    """rerank 를 못 했을 때의 순위. 검색이 준 병합 순서를 그대로 쓴다.

    tavily score 로 다시 정렬하지 않는다 - 이 기능은 애초에 그 점수에 기대지 않기로 하고
    만든 것이라, 장애 상황에서만 슬쩍 되살리면 결과를 해석할 수 없게 된다.
    """
    return [
        {
            **item,
            "article_id": order,
            "rank": order,
            "score_rerank": 0.0,
            "reason": "rerank 실패로 검색 순서를 유지함",
            "duplicate_group": 0,
        }
        for order, item in enumerate(items, start=1)
    ]
