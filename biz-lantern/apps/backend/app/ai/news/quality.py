"""
재정렬이 끝난 후보 전체를 보고 "이 검색 결과로 이 기업의 최신 동향을 파악할 수 있나"를
판단한다. 기사 하나하나를 보는 rerank 와 달리 **목록 전체를 하나로 놓고** 본다.

    rerank          기사끼리의 상대 순위          -> 어느 것이 위인가
    quality_check   목록 전체의 쓸모              -> 애초에 쓸 만한 것이 있나

이 둘을 나눈 이유는 판단의 대상이 다르기 때문이다. 1위 기사의 점수가 높아도 그게 동명이인
기사면 목록 전체는 쓸모가 없고, 반대로 관련 기사가 2건뿐이어도 그 둘이 정확하면 충분하다.

**고정된 threshold 를 코드에 두지 않는다.** "몇 점 이상 몇 건" 같은 규칙은 기업마다 후보
분포가 달라 번번이 어긋난다. 판단은 LLM 이 하고 코드는 돌아온 번호를 검증만 한다.

rerank.py 와 같은 계층 규칙을 따른다 - 네트워크를 타지 않고, LLM 호출은 nodes 가 한다.

    [1] 설정
    [2] 요청 만들기
    [3] 응답 읽기
    [4] 검증
"""
import json
import logging
from typing import Literal, TypedDict

from app.ai.news.llm_client import LLMError
from app.ai.news.signals import source_of

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
# 판단 근거로 보여줄 rerank 사유 길이. 전문을 다시 넣을 필요는 없다.
REASON_CHARS = 200

SCHEMA_NAME = "news_quality"

QUALITY_SCHEMA = {
    "type": "object",
    "properties": {
        "search_quality": {"type": "string", "enum": ["sufficient", "insufficient"]},
        "reason": {"type": "string"},
        "selected_article_ids": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["search_quality", "reason", "selected_article_ids"],
    "additionalProperties": False,
}

logger = logging.getLogger(__name__)

Quality = Literal["sufficient", "insufficient"]


class Judgement(TypedDict):
    search_quality: Quality
    reason: str
    selected_article_ids: list[int]


# ---------------------------------------------------------------------------
# [2] 요청 만들기
# ---------------------------------------------------------------------------
def build_instructions(company: str, top_n: int, aliases: tuple[str, ...] = ()) -> str:
    """판단 기준.

    개수나 점수 하나로 자르지 말라고 못 박는 게 이 프롬프트의 요지다. 그런 규칙이라면
    애초에 LLM 에게 물을 이유가 없다.
    """
    also = f"\n이 기업은 {', '.join(aliases)} 로도 불린다." if aliases else ""

    return f"""
아래는 '{company}'에 대한 웹 검색 결과를 관련도 순으로 정렬한 목록이다.{also}

이 목록에 '{company}'와 직접 관련 있고, 그 기업의 제품·서비스·사업을 이해하는 데 쓸모 있는
정보가 충분히 들어 있는지 판단하라.

sufficient / insufficient 중 하나를 고른다.

판단 원칙:
- 결과 개수만 보고 판단하지 않는다. 많아도 쓸모없을 수 있고 적어도 충분할 수 있다.
- 특정 결과 하나의 점수만 보고 판단하지 않는다. 목록 전체를 놓고 본다.
- 관련 결과가 1~2건뿐이어도 그것이 이 기업의 실제 제품·서비스·사업을 분명히 알려 준다면
  sufficient 로 본다.
- 후보가 많더라도 이름만 같은 다른 기업·다른 대상이 대부분이라면 insufficient 다.
- 기업의 실체(무엇을 만들고 파는 회사인지)가 전혀 드러나지 않으면 insufficient 다.
- 기업명이 문자열로 들어 있다는 것만으로 그 기업 자료로 보지 않는다. 이름이 일부만
  겹치는 다른 회사는 다른 회사다. 제목과 내용을 보고 같은 회사인지 직접 판단한다.

**다음은 그 자체로 insufficient 의 이유가 되지 않는다:**
언론 기사가 아님 / 자사 홈페이지 / 제품 소개 페이지 / 자사 블로그 / 정책·공식 문서.
문서의 형식이 아니라 '이 기업을 이해하는 데 쓸모 있는가' 로 판단한다.
다만 이 기업과 직접 관련이 없다면 형식과 무관하게 낮게 본다.

selected_article_ids:
- sufficient 이면 다음 단계로 넘길 결과를 최대 {top_n}개까지 고른다.
  같은 사건이나 같은 내용을 다룬 것(duplicate_group 이 같은 것)은 그중 하나만 고른다.
- insufficient 이면 빈 배열로 둔다.
- 억지로 {top_n}개를 채우지 않는다. 쓸 만한 것이 2건이면 2건만 고른다.

reason 에는 그렇게 판단한 근거를 한국어 한두 문장으로 쓴다. 무엇이 문제였는지,
또는 무엇이 확인됐는지가 드러나게 쓴다.
"""


def build_digest(
    ranked: list[dict],
    *,
    reason_chars: int = REASON_CHARS,
) -> str:
    """재정렬 결과를 판단용 목록으로. rerank.build_digest 와 같은 것을 뺀다.

    URL, 회사명 등장 여부, 날짜를 넣지 않는다. 앞의 둘은 코드가 미리 내린 틀린 판단이고,
    날짜는 Tavily 가 크롤링 시점을 발행일 자리에 실어 보내기 때문이다. 셋 다 LLM 이
    그대로 믿고 따라가는 것을 실제로 확인했다.

    번호는 article_id 다. rerank 가 쓴 것과 같은 번호라 사람이 두 출력을 대조할 수 있다.
    """
    lines = []

    for item in ranked:
        title = (item.get("title") or "").strip() or "(제목 없음)"
        source = source_of(item.get("url") or "") or "(출처 없음)"
        group = item.get("duplicate_group") or 0
        reason = " ".join((item.get("reason") or "").split())[:reason_chars]

        lines.append(
            f"[{item['article_id']}] {item.get('score_rerank', 0.0):.2f}  {title}\n"
            f"    출처: {source} | 중복그룹: {group}\n"
            f"    순위 사유: {reason}"
        )

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# [3] 응답 읽기
# ---------------------------------------------------------------------------
def parse_quality(response: dict) -> Judgement:
    """Chat Completions 응답에서 판단 결과를 꺼낸다.

    거부·형식 오류를 조용히 insufficient 로 만들지 않는다. "판단해 보니 부족하다" 와
    "판단을 못 했다" 는 다른 사건이고, 여기서 섞으면 구별할 방법이 없어진다.
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

    if not isinstance(parsed, dict):
        raise LLMError(f"객체가 아닌 응답: {content[:200]}")

    ids: list[int] = []
    for value in parsed.get("selected_article_ids") or []:
        # 번호가 문자열로 오는 게이트웨이가 있어 int 로 맞춰 본다
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue

    quality = str(parsed.get("search_quality") or "").strip().lower()

    return {
        # 두 값 중 하나가 아니면 판단이 성립하지 않은 것으로 본다
        "search_quality": "sufficient" if quality == "sufficient" else "insufficient",
        "reason": str(parsed.get("reason") or "").strip(),
        "selected_article_ids": ids,
    }


# ---------------------------------------------------------------------------
# [4] 검증
# ---------------------------------------------------------------------------
def resolve(ranked: list[dict], judgement: Judgement, top_n: int) -> Judgement:
    """고른 번호를 검증한다. 범위 밖·중복·초과분을 걸러낸다.

    **비어 있으면 비어 있는 채로 둔다.** 예전에는 sufficient 인데 고른 게 없으면 상위
    top_n 으로 채웠는데, 그러면 관련 기사가 없는 기업도 다음 단계로 기사가 넘어갔다.
    없는 것은 없다고 끝내는 게 맞다 - 0건은 nodes 가 no_relevant_news 로 받는다.
    """
    valid = {item["article_id"] for item in ranked}

    selected: list[int] = []
    for article_id in judgement["selected_article_ids"]:
        if article_id not in valid or article_id in selected:
            logger.warning("품질 판단이 쓸 수 없는 번호를 줌: %s", article_id)
            continue

        if len(selected) >= top_n:
            break

        selected.append(article_id)

    reason = judgement["reason"]

    if judgement["search_quality"] == "insufficient":
        # 부족하다고 판단했으면 고른 기사도 의미가 없다. 다음 단계로 넘기지 않는다.
        return {"search_quality": "insufficient", "reason": reason, "selected_article_ids": []}

    return {
        "search_quality": "sufficient",
        "reason": reason,
        "selected_article_ids": selected,
    }
