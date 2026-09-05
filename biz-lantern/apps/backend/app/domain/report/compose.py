"""판정을 문장으로 옮기고, 그 문장이 근거를 벗어나지 않았는지 기계로 검사한다.

infer.py 가 만든 Finding 과 Evidence 를 읽기만 한다 - 판정을 다시 하지 않고 산수도
하지 않는다(전부 F 블록이 이미 했다). 이 파일이 새로 만드는 것은 문장과 폐기 기록뿐이다.
LLM 호출 자체는 app/ai/news/llm_client.py 를 그대로 쓴다.

    [1] 자료형     Sentence · Dropped · ItemNarrative · ComposeResult
    [2] 근거팩     항목별 허용 근거 집합과 파생 역인덱스
    [3] 정형문     판정값 다섯의 문장. LLM 이 죽어도 남는 층이다
    [4] 요청       SENTENCE_SCHEMA · build_instructions · build_pack_text
    [5] 응답 읽기  parse_sentences
    [6] 후검증     네 단계와 1회 재생성
    [7] 진입점     narrate_item · run

서술을 두 층으로 쌓는 이유

    1층 정형문은 verdict·label·value·warnings 만으로 결정되고 LLM 과 무관하게 항상
    존재한다. 2층 서술은 CONFIRMED 항목에만 얹는다. 그래서 "문장이 하나도 없는 항목"
    이라는 상태가 존재할 수 없다 - 0개일 때의 처리 규칙을 만드는 대신 0개가 될 수
    없게 만들었다.

    LLM 이 value 를 예쁘게 고쳐 쓰는 것이 아니다. 세 가지를 한다. (가) 파생을 잇는다
    - value 에는 F-3 적자 전환도 F-6 환산도 한 글자가 없고 별개 조각으로만 있다.
    (나) value 가 사실이 아니라 포인터인 항목을 푼다 - B-5·B-6·C-3·D-1·E-1·E-2 의
    value 는 "주석 12. 차입금" 뿐이고 금액은 수천 자 원문 안에 있다. (다) 표를 문장으로
    옮긴다.

물러서지 않는 지점 넷

    1. 근거를 넓혀 환각을 통과시키지 않는다. 후검증에 막히면 프롬프트를 조이지 허용
       집합을 늘리지 않는다.
    2. 비-CONFIRMED 항목은 LLM 을 아예 부르지 않는다. 판정값 다섯의 뜻이 흐려지는 것이
       이 서비스의 가장 큰 위험인데, value 가 None 이라 모델에게 줄 사실 자체가 없고
       남는 것은 지어낼 여지뿐이다.
    3. 경고는 원문 그대로 승격시킨다. "국세청 진위확인 불일치" 는 폐업이 아니고 "최신
       3건만 확인" 은 정정이 없다는 뜻이 아니다. 그 구분을 infer 가 이미 문장 안에 넣어
       뒀으므로 compose 가 용어집을 따로 두면 두 곳이 언젠가 갈라진다.
    4. 부분 실패는 완결이다. 한 항목의 LLM 이 죽어도 나머지 항목과 그 항목의 정형문은
       그대로 산다.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, TypedDict

import httpx

from app.ai.news import llm_client
from app.ai.news.llm_client import LLMError
from app.domain.report import evidence, infer, rules
from app.domain.report.rules import Verdict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# [1] 자료형
# ---------------------------------------------------------------------------
KIND_CONFIRMED = "confirmed"  # 인용 근거에 그대로 적혀 있는 사실
KIND_INFERRED = "inferred"    # 근거 여럿을 이어 읽은 해석. 근거는 여전히 필수다
KIND_REFERENCE = "reference"  # 무엇을 확인했고 무엇을 못 했는가. 판정 계층의 소유물

# 모델이 쓸 수 있는 kind. reference 를 열어 주면 경고를 자기 말로 다시 쓰는 통로가 된다.
LLM_KINDS = frozenset({KIND_CONFIRMED, KIND_INFERRED})

ORIGIN_RULE = "rule"
ORIGIN_LLM = "llm"

STATUS_SKIPPED = "skipped"  # LLM 을 부르지 않았다 (비-CONFIRMED · client 없음)
STATUS_OK = "ok"
STATUS_PARTIAL = "partial"  # 일부 문장을 폐기했거나 재생성 호출이 실패했다
STATUS_ERROR = "error"      # 1차 호출부터 실패했다

MAX_SENTENCES = 4
MAX_SENTENCE_CHARS = 200
PACK_CHARS = 1200        # 조각 하나를 프롬프트에 넣을 때의 상한
PACK_TOTAL_CHARS = 12_000
MAX_TOKENS = 1200
MAX_CONCURRENCY = 4      # 20개를 한꺼번에 던지면 429 로 재시도 예산을 전부 태운다

TRUNCATION_MARK = "…(원문이 길어 이후 생략됨)"

# 환산 단위. value·warnings 경로로는 절대 들여보내지 않는다 - 환산값이 F 파생 근거에만
# 있다는 규칙(evidence.py)을 미래의 infer 변경에도 견디게 하는 뺄셈이다.
CONVERSION_UNITS = frozenset({"억원", "조원"})

REASON_UNKNOWN_ID = "존재하지 않는 근거 ID"
REASON_FOREIGN_ID = "다른 항목의 근거 ID"
REASON_NO_EVIDENCE = "근거를 대지 않았다"
REASON_BAD_KIND = "허용되지 않은 kind"
REASON_NUMBER = "근거에 없는 숫자"
REASON_UNIT = "허용되지 않은 단위"
REASON_TOO_LONG = "문장 길이 상한 초과"
REASON_OVERFLOW = "문장 개수 상한 초과"
REASON_MALFORMED = "형식이 깨진 문장"


class Sentence(TypedDict):
    text: str
    kind: str
    evidence_ids: list[str]
    origin: str


class Dropped(TypedDict):
    """폐기된 문장. 왜 버렸는지까지 남긴다 - 조용히 사라지면 프롬프트를 못 고친다."""

    text: str
    kind: str
    evidence_ids: list[str]
    reasons: list[str]
    attempt: int  # 1 = 첫 응답, 2 = 재생성


class ItemNarrative(TypedDict):
    item_id: str
    sentences: list[Sentence]  # 항상 1개 이상. 정형문이 맨 앞이다
    dropped: list[Dropped]
    pack_ids: list[str]        # 이 항목에 허용했던 근거 집합. 검증 재현용
    llm_status: str
    llm_error: str | None


class ComposeError(TypedDict):
    item_id: str | None  # None 이면 항목이 아니라 compose 전체의 실패다
    message: str


class ComposeResult(TypedDict):
    items: dict[str, ItemNarrative]
    errors: list[ComposeError]
    orphan_derived: list[str]  # 어느 항목에도 붙지 못한 파생 조각


# ComposeResult 에 status 를 두지 않는다. 룰베이스 문장만 남은 결과도 완결된 서술이고,
# 보고서 상태(COMPLETED/FAILED)를 정하는 것은 이 계층의 일이 아니다. 무엇이 터졌는지는
# errors 와 항목별 llm_status 에 그대로 남는다.


# ---------------------------------------------------------------------------
# [2] 근거팩
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Pack:
    """항목 하나에 허용된 근거와 그로부터 나온 검증 기준선.

    TypedDict 가 아니라 frozen dataclass 다. 경계를 넘지도 직렬화되지도 않는 내부
    작업물이고 frozenset 을 들고 있어 JSON 이 될 수 없다.

    baseline 은 어느 조각을 인용하든 늘 허용되는 토큰이다. 조각의 numbers 합집합만으로
    검증하면 재무 문장이 전부 죽는다 - account 조각의 원문은 "매출액 | 제 11(당) 기
    31,457,983,251" 이라 캘린더 연도가 없고 units 가 비어 있다. 연도와 "원" 은 오직
    infer 가 만든 value 안에만 있다(실측).
    """

    item_id: str
    finding: rules.Finding
    pieces: tuple[evidence.Evidence, ...]
    baseline_numbers: frozenset[str]
    baseline_units: frozenset[str]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(piece["evidence_id"] for piece in self.pieces)

    def piece(self, evidence_id: str) -> evidence.Evidence | None:
        for item in self.pieces:
            if item["evidence_id"] == evidence_id:
                return item

        return None


def _year_of(as_of: str | None) -> str | None:
    """기준일에서 4자리 연도만. 월·일은 뽑지 않는다.

    주석 본문의 "2025.12.31" 은 숫자 정규식이 "2025.12" 로 끊어 2025 를 내주지 않는다.
    그래서 "2025년 말 기준" 같은 멀쩡한 문장이 오탐으로 죽는다. 월·일까지 허용하면
    12·31 이 풀려 "12억원" 이 새어 들어오므로 연도만 더한다.
    """
    head = (as_of or "")[:4]

    return head if head.isdigit() else None


def _baselines(
    finding: rules.Finding, pieces: tuple[evidence.Evidence, ...]
) -> tuple[frozenset[str], frozenset[str]]:
    """value·warnings·기준연도에서 나오는 허용 토큰.

    이것이 근거를 느슨하게 만드는 것이 아닌 이유: value 와 warnings 는 LLM 을 한 번도
    거치지 않고 infer 가 같은 근거로부터 결정적으로 만든 문자열이고, 1층 정형문으로
    이미 화면에 인쇄된다. 2층이 그것을 다시 말하는 것이 1층보다 위험할 수 없다. 새로
    허용되는 것은 정확히 "룰베이스가 이미 말하기로 한 것" 뿐이다.

    단위는 환산 단위를 뺀 채로 돌려준다. 억원은 F-6 파생 조각을 인용해야만 통과한다.

    항목 라벨은 일부러 넣지 않는다. "매출·손익 3개년" 의 3 은 우리 정의표가 붙인
    제목이지 근거에서 나온 값이 아니고, 그걸 허용하면 개수 세기 금지가 B 블록에서
    통째로 풀린다. 그래서 정형문이 라벨을 인쇄해도 그 숫자는 허용되지 않는다 -
    정형문은 모델 출력이 아니라 검증 대상이 아니므로 아무 문제가 없다.
    """
    numbers: set[str] = set()
    units: set[str] = set()

    for text in [finding["value"] or "", *finding["warnings"]]:
        numbers |= set(evidence.number_tokens(text))
        units |= set(evidence.unit_tokens(text))

    for source in [finding["source"], *(piece["source"] for piece in pieces)]:
        year = _year_of(source.get("as_of"))
        if year:
            numbers.add(year)

    return frozenset(numbers), frozenset(units - CONVERSION_UNITS)


def build_packs(inferred: infer.InferResult) -> tuple[dict[str, _Pack], list[str]]:
    """항목별 근거팩과, 어느 항목에도 붙지 못한 파생 조각 ID.

    파생이 어느 항목에 붙는지 매핑표를 새로 만들지 않는다. 파생의 based_on 을 거꾸로
    타서 그 근거를 인용한 모든 항목에 붙인다 - infer._derive() 와 B 블록의 _cite() 가
    같은 evidence.account() 팩토리를 부르므로 조각 ID 가 그대로 일치한다. F-2(최대주주)
    가 C-1 과 A-4 양쪽에 붙는 1:N 은 오히려 옳다. A-4 가 같은 주주표를 등록한 이유가
    "대표이사가 최대주주인가" 이고 F-2 의 result 가 정확히 그 문장이다.

    겹치는 항목이 하나도 없는 파생은 조용히 사라지지 않고 orphan 으로 올라온다. B-1 이
    요약 폴백으로 갔는데 F-6 은 계정 기반인 경우가 그렇게 된다.
    """
    by_id = {piece["evidence_id"]: piece for piece in inferred["evidence"]}
    findings = inferred["findings"]

    attached: dict[str, list[str]] = {}
    orphan: list[str] = []

    for derived_id in inferred["derived"]:
        piece = by_id.get(derived_id)
        if piece is None:
            orphan.append(derived_id)
            continue

        base = set(piece.get("based_on") or [])
        hosts = [
            item.item_id
            for item in rules.ITEMS
            if item.item_id in findings
            and base & set(findings[item.item_id]["evidence_ids"])
        ]

        if not hosts:
            orphan.append(derived_id)
            continue

        for host in hosts:
            attached.setdefault(host, []).append(derived_id)

    packs: dict[str, _Pack] = {}
    for item in rules.ITEMS:
        found = findings.get(item.item_id)
        if found is None:
            continue

        cited = list(found["evidence_ids"])
        cited += [d for d in attached.get(item.item_id, []) if d not in cited]
        pieces = tuple(by_id[i] for i in cited if i in by_id)
        numbers, units = _baselines(found, pieces)

        packs[item.item_id] = _Pack(item.item_id, found, pieces, numbers, units)

    return packs, orphan


# ---------------------------------------------------------------------------
# [3] 정형문 - LLM 이 죽어도 남는 층
# ---------------------------------------------------------------------------
_HANGUL_START = 0xAC00
_HANGUL_END = 0xD7A3
_JONGSEONG = 28


def _has_jongseong(word: str) -> bool:
    """마지막 글자에 받침이 있는가. 보지 않으면 "매출액를" 같은 문장이 나온다."""
    tail = (word or "").strip()[-1:]
    if not tail:
        return True

    if _HANGUL_START <= ord(tail) <= _HANGUL_END:
        return (ord(tail) - _HANGUL_START) % _JONGSEONG != 0

    # 영숫자·기호로 끝나는 라벨은 받침이 있는 쪽으로 읽는다.
    return True


def _eul(word: str) -> str:
    return word + ("을" if _has_jongseong(word) else "를")


def _eun(word: str) -> str:
    return word + ("은" if _has_jongseong(word) else "는")


def _verdict_text(finding: rules.Finding) -> str:
    """판정값 다섯의 문장. 뒤에 붙는 부정형 한 절이 이 파일의 핵심이다.

    "없었다" 는 ABSENT 에만 쓴다. EXTRACTION_FAILED 와 SOURCE_UNAVAILABLE 에 "내용이
    없다는 뜻이 아니다" 를 못박아, 우리 파서의 실패나 미연동이 회사의 흠으로 둔갑하는
    길을 문장 층위에서 끊는다.
    """
    label = finding["label"]
    source = finding["source"]["name"]
    verdict = Verdict(finding["verdict"])

    if verdict is Verdict.CONFIRMED:
        value = finding["value"]
        return f"{label}: {value}" if value else f"{_eun(label)} 확인했다."

    if verdict is Verdict.ABSENT:
        return f"{source}에서 {_eul(label)} 확인했으나 해당 내용이 없었다."

    if verdict is Verdict.NOT_REQUIRED:
        # 이유를 붙이지 않는다. 같은 판정이 두 가지 사정에서 나온다 - D-3 은 법정
        # 공시사항이 아니라서, G-3 은 감사보고서를 받아 미제출신고를 물어볼 이유가
        # 없어서다. 한쪽 이유를 템플릿에 박으면 다른 쪽에서 거짓말이 된다.
        return f"{_eun(label)} 이 법인에서 확인 대상이 아니다."

    if verdict is Verdict.EXTRACTION_FAILED:
        return (
            f"{source} 문서는 확보했으나 {_eul(label)} 읽어내지 못했다. "
            "내용이 없다는 뜻이 아니다."
        )

    return (
        f"{_eul(label)} 확인할 출처를 확보하지 못했다. "
        "확인하지 못했다는 뜻이며 내용이 없다는 뜻이 아니다."
    )


def rule_sentences(finding: rules.Finding) -> list[Sentence]:
    """판정 하나 -> 정형문. 경고는 한 건당 문장 하나로 원문 그대로 승격시킨다.

    요약도 의역도 하지 않는다. infer 가 이미 "폐업이 아니라 대조 실패다" 처럼 오독을
    막는 절을 경고 문자열 안에 넣어 뒀고, 여기서 다시 쓰면 두 곳이 언젠가 갈라진다.
    """
    verdict = Verdict(finding["verdict"])
    kind = KIND_CONFIRMED if verdict is Verdict.CONFIRMED else KIND_REFERENCE

    sentences: list[Sentence] = [
        {
            "text": _verdict_text(finding),
            "kind": kind,
            "evidence_ids": list(finding["evidence_ids"]),
            "origin": ORIGIN_RULE,
        }
    ]

    sentences += [
        {
            "text": warning,
            "kind": KIND_REFERENCE,
            "evidence_ids": [],
            "origin": ORIGIN_RULE,
        }
        for warning in finding["warnings"]
    ]

    return sentences


# ---------------------------------------------------------------------------
# [4] 요청
# ---------------------------------------------------------------------------
SCHEMA_NAME = "report_item_sentences"

# strict 모드 규격: 모든 object 에 additionalProperties:false, 모든 필드 required.
# kind enum 에 reference 를 넣지 않는다 - "무엇을 확인하고 무엇을 못 했는가" 는 판정
# 계층의 소유물이고, 열어 주면 모델이 경고를 자기 말로 다시 쓰는 통로가 된다.
SENTENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": [KIND_CONFIRMED, KIND_INFERRED]},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "kind", "evidence_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sentences"],
    "additionalProperties": False,
}

_VERDICT_NOTE = {
    Verdict.CONFIRMED: "값을 확보했다",
    Verdict.ABSENT: "확인했으나 없었다",
    Verdict.NOT_REQUIRED: "공시의무가 없다",
    Verdict.EXTRACTION_FAILED: "문서는 있으나 파싱하지 못했다",
    Verdict.SOURCE_UNAVAILABLE: "출처를 확보하지 못했다",
}

_TYPE_LABELS = {
    "api_field": "API 필드",
    "summary": "공시 요약정보",
    "account": "계정",
    "table": "표",
    "paragraph": "문단",
    "note": "주석",
    "derived": "파생",
    "conflict": "충돌",
    "news": "뉴스",
    "patent": "특허",
}


def _source_line(source: evidence.Source) -> str:
    parts = [source["name"]]

    if source.get("as_of"):
        parts.append(f"{source.get('as_of_kind') or ''} {source['as_of']}".strip())

    if source.get("rcept_no"):
        parts.append(f"접수번호 {source['rcept_no']}")

    return " · ".join(parts)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + TRUNCATION_MARK


def _piece_text(piece: evidence.Evidence, *, limit: int) -> str:
    """조각 하나를 프롬프트 줄로. 원문은 여기서만 자른다.

    자르기는 안전한 방향으로만 작동한다 - 후검증은 잘리지 않은 piece["numbers"] 를
    기준으로 하므로, 자르기는 모델이 볼 수 있는 것을 줄일 뿐 통과 가능한 것을 넓히지
    않는다. 반대 방향(검증도 잘린 텍스트로 재토큰화)은 스냅샷 원칙이 금지한다.
    """
    kind = _TYPE_LABELS.get(piece["type"], piece["type"])
    rule_id = piece.get("rule_id")
    head = f"{kind}({rule_id})" if rule_id else kind

    lines = [f"- {piece['evidence_id']} | {head} | {piece['label']}"]

    formula = piece.get("formula")
    if formula:
        lines.append(f"  계산: {formula}")

    if piece.get("sides"):
        conflict_kind = evidence.CONFLICT_KIND_LABELS.get(
            piece.get("conflict_kind", ""), piece.get("conflict_kind", "")
        )
        resolution = evidence.RESOLUTION_LABELS.get(
            piece.get("resolution", ""), piece.get("resolution", "")
        )
        lines.append(f"  충돌: {conflict_kind} · 처리 {resolution}")

    lines.append(f"  단위: {', '.join(piece['units']) or '(없음)'}")
    lines.append(f"  원문: {_clip(piece['raw_content'], limit)}")

    return "\n".join(lines)


def build_pack_text(
    pack: _Pack, *, limit: int = PACK_CHARS, total: int = PACK_TOTAL_CHARS
) -> str:
    """근거팩 직렬화. 이 항목에 허용된 조각만 나온다."""
    finding = pack.finding
    verdict = Verdict(finding["verdict"])

    header = [
        f"[항목] {pack.item_id} {finding['label']}",
        f"[판정] {verdict.value} - {_VERDICT_NOTE[verdict]}",
        f"[출처] {_source_line(finding['source'])}",
        f"[요약] {finding['value'] or '(값 없음)'}",
        f"[주의] {' / '.join(finding['warnings']) or '(없음)'}",
        "",
        "[근거]",
    ]

    used = sum(len(line) + 1 for line in header)
    body: list[str] = []
    skipped = 0

    for piece in pack.pieces:
        block = _piece_text(piece, limit=limit)
        if used + len(block) + 1 > total:
            skipped += 1
            continue

        body.append(block)
        used += len(block) + 1

    if not body:
        body.append("- (없음)")

    if skipped:
        # 문자열 중간을 자르는 대신 조각을 통째로 뺀다. 잘린 사실은 남긴다.
        body.append(f"  (분량 때문에 조각 {skipped}건을 이 목록에서 제외했다)")

    return "\n".join(header + body)


def build_instructions(company_name: str, finding: rules.Finding) -> str:
    """판정 기준이 아니라 서술 규칙. 형식은 SENTENCE_SCHEMA 가 이미 강제한다.

    허용된 숫자 목록을 여기에도 재생성 프롬프트에도 넣지 않는다. 메뉴를 주면 모델이
    거기서 숫자를 골라 문장을 채운다.
    """
    return f"""
'{company_name}' 의 비상장기업 분석 보고서에서 '{finding["label"]}' 항목을 서술한다.
아래 [근거] 에 적힌 것만 가지고 2~4문장을 쓴다.

- 숫자는 [근거] 나 [요약] 에 적힌 표기를 그대로 옮긴다. 반올림·자릿수 축약·단위 환산·
  직접 계산을 하지 않는다. '314.6억원' 을 '약 315억원' 으로 쓰면 그 문장은 버려진다.
- [근거] 에 나오지 않는 단위를 쓰지 않는다. '억원' 은 파생(F-6) 조각을 인용할 때만
  쓸 수 있다.
- 개수를 세지 않는다. '3개년'·'2건' 처럼 직접 센 숫자를 쓰지 않는다. 필요한 개수는
  이미 [요약] 에 있다.
- 문장마다 딛고 선 조각의 ID 를 evidence_ids 에 빠짐없이 적는다. [근거] 목록에 없는
  ID 를 쓰면 그 문장은 버려진다.
- [주의] 는 우리가 확인하지 못한 범위다. 이미 별도 문장으로 인쇄했으니 다시 쓰지 말고,
  그 뜻을 넓히거나 좁히지도 마라.
- 총평·전망·투자 판단·권유를 쓰지 않는다. 이 항목에 대한 사실만 쓴다.
- URL 을 쓰지 않는다.

kind 는 근거에 그대로 적혀 있으면 confirmed, 근거 여럿을 이어 읽은 해석이면 inferred 다.
""".strip()


def build_repair_text(
    pack_text: str, failures: list[tuple[Sentence, list[str]]]
) -> str:
    """재생성 입력. 어긋난 토큰만 짚고 허용 목록은 보여주지 않는다."""
    lines = [
        pack_text,
        "",
        "[다시 쓸 문장]",
        "아래 문장은 근거를 벗어나 폐기됐다. 짚어 준 부분만 고쳐 다시 쓰라.",
        "고칠 수 없으면 그 내용을 빼고 남은 사실만으로 쓰라.",
        "",
    ]

    for index, (draft, reasons) in enumerate(failures, start=1):
        lines.append(f"{index}. {draft['text']}")
        lines += [f"   - {reason}" for reason in reasons]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# [5] 응답 읽기
# ---------------------------------------------------------------------------
def parse_sentences(
    response: dict,
) -> tuple[list[Sentence], list[tuple[Any, list[str]]]]:
    """응답 -> (초안, 형식 때문에 버린 것).

    거부·형식 오류를 조용히 빈 결과로 만들지 않는다. 빈 결과와 실패는 다른 사건이고,
    여기서 삼키면 "문장을 못 만들었다" 는 사실을 알 방법이 없다.

    배열 안 개별 항목이 깨진 것은 예외가 아니라 그 항목만 버린다 - 한 문장의 형식
    오류로 나머지 문장을 버릴 이유가 없다. 길이 초과 문장도 자르지 않고 버린다.
    자른 문장은 근거를 벗어나기 쉽다.
    """
    choices = response.get("choices") or []
    if not choices:
        raise LLMError(
            f"응답에 choices 가 없음: {json.dumps(response, ensure_ascii=False)[:200]}"
        )

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

    raw = parsed.get("sentences") if isinstance(parsed, dict) else None
    if not isinstance(raw, list):
        raise LLMError(f"sentences 배열이 없음: {content[:200]}")

    drafts: list[Sentence] = []
    rejects: list[tuple[Any, list[str]]] = []

    for entry in raw:
        if not isinstance(entry, dict):
            rejects.append((entry, [REASON_MALFORMED]))
            continue

        text = entry.get("text")
        ids = entry.get("evidence_ids")
        if not isinstance(text, str) or not text.strip() or not isinstance(ids, list):
            rejects.append((entry, [REASON_MALFORMED]))
            continue

        if len(text) > MAX_SENTENCE_CHARS:
            rejects.append((entry, [f"{REASON_TOO_LONG}: {len(text)}자"]))
            continue

        if len(drafts) >= MAX_SENTENCES:
            rejects.append((entry, [REASON_OVERFLOW]))
            continue

        drafts.append({
            "text": text.strip(),
            "kind": str(entry.get("kind") or ""),
            "evidence_ids": [i for i in ids if isinstance(i, str)],
            "origin": ORIGIN_LLM,
        })

    return drafts, rejects


# ---------------------------------------------------------------------------
# [6] 후검증
# ---------------------------------------------------------------------------
def allowed_numbers(
    pack: _Pack, cited: list[evidence.Evidence]
) -> frozenset[str]:
    """이 문장이 쓸 수 있는 숫자. 인용한 조각 + 기준선.

    조각의 numbers 는 생성 시점에 굳어 있으므로 다시 토큰화하지 않는다 - 토크나이저를
    고치는 순간 과거 보고서의 검증 결과가 달라진다.
    """
    tokens = set(pack.baseline_numbers)
    for piece in cited:
        tokens |= set(piece["numbers"])

    return frozenset(tokens)


def allowed_units(pack: _Pack, cited: list[evidence.Evidence]) -> frozenset[str]:
    """이 문장이 쓸 수 있는 단위.

    기준선에서 환산 단위를 이미 뺐으므로 억원은 인용한 조각의 units 로만 들어온다.
    그 자리는 F-6 파생 조각뿐이다. 문서 원문에 조원이 인쇄돼 있으면 그 조각의 units
    에 있으므로 통과한다 - 원문 인용은 환산이 아니다.
    """
    tokens = set(pack.baseline_units)
    for piece in cited:
        tokens |= set(piece["units"])

    return frozenset(tokens)


def verify(draft: Sentence, pack: _Pack, known_ids: frozenset[str]) -> list[str]:
    """문장 하나를 검사한다. 빈 리스트면 통과.

    근거 ID 를 전역 장부가 아니라 항목 팩으로 좁힌다. 전역으로 열면 B-4 감사의견
    문장에 주주표 조각을 달아도 통과한다 - "실재하는 ID" 와 "이 주장을 뒷받침하는 ID"
    는 다른 사건이고 우리가 검사하려던 것은 후자다. 팩은 프롬프트에 실제로 보여준
    집합과 정확히 같으므로, 팩 밖의 ID 는 정의상 지어낸 것 아니면 잘못 붙인 것이다.

    사유는 둘로 가른다. 전역에도 없으면 환각이고 전역에는 있으면 프롬프트 문제다.
    뭉개면 고칠 곳을 못 찾는다.
    """
    reasons: list[str] = []

    if draft["kind"] not in LLM_KINDS:
        reasons.append(f"{REASON_BAD_KIND}: {draft['kind']}")

    cited: list[evidence.Evidence] = []
    for evidence_id in draft["evidence_ids"]:
        piece = pack.piece(evidence_id)
        if piece is not None:
            cited.append(piece)
            continue

        label = REASON_FOREIGN_ID if evidence_id in known_ids else REASON_UNKNOWN_ID
        reasons.append(f"{label}: {evidence_id}")

    if not cited:
        reasons.append(REASON_NO_EVIDENCE)

    numbers = allowed_numbers(pack, cited)
    reasons += [
        f"{REASON_NUMBER}: {token}"
        for token in evidence.number_tokens(draft["text"])
        if token not in numbers
    ]

    units = allowed_units(pack, cited)
    reasons += [
        f"{REASON_UNIT}: {word}"
        for word in evidence.unit_tokens(draft["text"])
        if word not in units
    ]

    return reasons


def _dropped(entry: Any, reasons: list[str], *, attempt: int) -> Dropped:
    """초안이든 깨진 원본이든 같은 모양으로 남긴다."""
    data = entry if isinstance(entry, dict) else {}
    ids = data.get("evidence_ids")

    return {
        "text": str(data.get("text") or ""),
        "kind": str(data.get("kind") or ""),
        "evidence_ids": [i for i in (ids or []) if isinstance(i, str)],
        "reasons": reasons,
        "attempt": attempt,
    }


# ---------------------------------------------------------------------------
# [7] 진입점
# ---------------------------------------------------------------------------
async def _ask(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    instructions: str,
    user_content: str,
) -> tuple[list[Sentence], list[tuple[Any, list[str]]]]:
    async with semaphore:
        response = await llm_client.complete_json(
            client,
            instructions,
            user_content,
            SENTENCE_SCHEMA,
            SCHEMA_NAME,
            max_tokens=MAX_TOKENS,
        )

    return parse_sentences(response)


async def narrate_item(
    client: httpx.AsyncClient | None,
    pack: _Pack,
    known_ids: frozenset[str],
    *,
    company_name: str,
    semaphore: asyncio.Semaphore,
) -> ItemNarrative:
    """항목 하나의 서술. 예외를 올리지 않는다.

    LLMError 를 안에서 잡아 llm_status 로 바꾸므로 gather 에 return_exceptions 가
    필요 없고, 한 항목의 실패가 형제 항목을 취소할 수 없다.

    재생성은 항목당 정확히 1회다. 문장별로 부르면 문장 3개에 호출이 4번이 된다.
    """
    narrative: ItemNarrative = {
        "item_id": pack.item_id,
        "sentences": rule_sentences(pack.finding),
        "dropped": [],
        "pack_ids": list(pack.ids),
        "llm_status": STATUS_SKIPPED,
        "llm_error": None,
    }

    if client is None or Verdict(pack.finding["verdict"]) is not Verdict.CONFIRMED:
        return narrative

    instructions = build_instructions(company_name, pack.finding)
    pack_text = build_pack_text(pack)

    try:
        drafts, rejects = await _ask(client, semaphore, instructions, pack_text)
    except LLMError as error:
        narrative["llm_status"] = STATUS_ERROR
        narrative["llm_error"] = str(error)
        return narrative

    narrative["dropped"] += [_dropped(e, r, attempt=1) for e, r in rejects]

    kept: list[Sentence] = []
    failed: list[tuple[Sentence, list[str]]] = []
    for draft in drafts:
        reasons = verify(draft, pack, known_ids)
        if reasons:
            failed.append((draft, reasons))
        else:
            kept.append(draft)

    if failed:
        narrative["dropped"] += [_dropped(d, r, attempt=1) for d, r in failed]
        kept += await _repair(
            client, semaphore, narrative, pack, known_ids, instructions,
            build_repair_text(pack_text, failed),
        )

    for draft in kept[:MAX_SENTENCES]:
        narrative["sentences"].append(draft)

    narrative["dropped"] += [
        _dropped(draft, [REASON_OVERFLOW], attempt=2) for draft in kept[MAX_SENTENCES:]
    ]

    if narrative["llm_status"] != STATUS_ERROR:
        narrative["llm_status"] = (
            STATUS_PARTIAL if narrative["dropped"] else STATUS_OK
        )

    return narrative


async def _repair(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    narrative: ItemNarrative,
    pack: _Pack,
    known_ids: frozenset[str],
    instructions: str,
    user_content: str,
) -> list[Sentence]:
    """재생성 1회. 다시 어긋난 문장은 그대로 폐기한다(3회째는 없다)."""
    try:
        drafts, rejects = await _ask(client, semaphore, instructions, user_content)
    except LLMError as error:
        # 1차 통과분은 살린다. 재생성 실패가 이미 검증된 문장을 지울 이유가 없다.
        narrative["llm_error"] = str(error)
        return []

    narrative["dropped"] += [_dropped(e, r, attempt=2) for e, r in rejects]

    repaired: list[Sentence] = []
    for draft in drafts:
        reasons = verify(draft, pack, known_ids)
        if reasons:
            narrative["dropped"].append(_dropped(draft, reasons, attempt=2))
        else:
            repaired.append(draft)

    return repaired


async def run(
    client: httpx.AsyncClient | None,
    inferred: infer.InferResult,
    *,
    company_name: str,
) -> ComposeResult:
    """판정 결과 -> 항목별 서술.

    as_of 를 받지 않는다. 인쇄할 시점은 전부 source.as_of 에 굳어 있으므로, 시계를
    읽지 않는다는 원칙을 인자를 아예 두지 않는 것으로 지킨다.

    client=None 은 "LLM 을 쓰지 않는다" 는 명시적 요청이다. 그래도 정형문은 전부 나오고
    보고서는 완결된다.

    설정 확인은 한 번만 한다. 25번 던져 전부 같은 이유로 죽게 두지 않는다.
    """
    errors: list[ComposeError] = []

    if client is not None:
        try:
            llm_client.ensure_configured()
        except LLMError as error:
            errors.append({"item_id": None, "message": str(error)})
            client = None

    packs, orphan = build_packs(inferred)
    known_ids = frozenset(piece["evidence_id"] for piece in inferred["evidence"])
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    ordered = [packs[item.item_id] for item in rules.ITEMS if item.item_id in packs]
    narratives = await asyncio.gather(*(
        narrate_item(
            client, pack, known_ids, company_name=company_name, semaphore=semaphore
        )
        for pack in ordered
    ))

    errors += [
        {"item_id": narrative["item_id"], "message": narrative["llm_error"] or ""}
        for narrative in narratives
        if narrative["llm_error"]
    ]

    if orphan:
        logger.warning(
            "어느 항목에도 붙지 못한 파생 근거 %d건: %s", len(orphan), orphan
        )

    return {
        "items": {narrative["item_id"]: narrative for narrative in narratives},
        "errors": errors,
        "orphan_derived": orphan,
    }
