"""항목 판정의 골격. 판정값·항목 정의표·게이트·공통 분기가 여기 있다.

항목별 판정 로직은 infer.py 에 있고, 이 파일은 그 판정이 딛고 설 규칙만 갖는다.
근거 조각은 evidence.py 가 만든다 - 여기서는 조각 ID 를 받아 항목에 매달 뿐이다.

    [1] 판정값     Verdict
    [2] 항목 정의  ItemDefinition · ITEMS
    [3] 결과       Finding · finding() 팩토리
    [4] 게이트     gate_state()
    [5] 공통 분기  note_verdict()

판정값 다섯을 왜 나누는가

    ABSENT 와 SOURCE_UNAVAILABLE 을 뭉개면 이 서비스의 근거가 사라진다. 전자는
    "확인해보니 없더라" 는 정보이고, 후자는 "확인하지 못했다" 는 고백이다. 핀샷에
    주주표가 없는 것과 감사보고서를 못 받은 것은 전혀 다른 사실이다.

    NOT_REQUIRED 도 따로 둔다. 비상장 외감법인의 매출처는 법정 공시사항이 아니라
    애초에 확인 대상이 아니다. 그걸 ABSENT 로 적으면 "찾아봤는데 없다" 는 뜻이 되어
    회사에 없는 흠을 만든다.

    EXTRACTION_FAILED 는 문서는 받았는데 못 읽은 경우다. 이걸 ABSENT 로 적는 것이
    가장 위험하다 - 우리 파서의 실패가 회사의 부재로 둔갑한다.

판정이 CONFIRMED 가 아니어도 source 는 항상 채운다. 무엇을 확인하려 했는지가 곧 부재
확인의 근거다. value 만 비운다.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypedDict

from app.domain.company.parser import notes as nt
from app.domain.company.parser import statements as st
from app.domain.report import evidence


# ---------------------------------------------------------------------------
# [1] 판정값
# ---------------------------------------------------------------------------
class Verdict(StrEnum):
    CONFIRMED = "CONFIRMED"                    # 값을 확보했다
    ABSENT = "ABSENT"                          # 확인했으나 없었다
    NOT_REQUIRED = "NOT_REQUIRED"              # 애초에 공시의무가 없다
    EXTRACTION_FAILED = "EXTRACTION_FAILED"    # 문서는 있는데 파싱하지 못했다
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"  # 문서·출처 자체를 확보하지 못했다


# ---------------------------------------------------------------------------
# [2] 항목 정의
# ---------------------------------------------------------------------------
SECTION_GATE = "gate"
SECTION_ENTITY = "entity"      # A. 법적 실체
SECTION_FINANCE = "finance"    # B. 재무
SECTION_CAPITAL = "capital"    # C. 자본구조·투자
SECTION_BUSINESS = "business"  # D. 사업 실질
SECTION_RISK = "risk"          # E. 리스크


NOTES_SOURCE_NAME = "DART 감사보고서 주석"


@dataclass(frozen=True)
class ItemDefinition:
    """항목 하나의 고정 정보. 판정 결과가 아니라 정의다."""

    item_id: str
    label: str
    section: str
    source_name: str


# 항목을 늘리는 곳은 여기 한 곳이다. 정의를 넣고 infer._RULES 에 판정 함수를 등록하면
# infer.run() 이 알아서 돈다.
ITEMS: tuple[ItemDefinition, ...] = (
    ItemDefinition("G-1", "DART 등록", SECTION_GATE, evidence.COMPANY_SOURCE_NAME),
    ItemDefinition("G-2", "외부감사 대상", SECTION_GATE, evidence.DISCLOSURE_SOURCE_NAME),
    ItemDefinition(
        "G-3", "감사보고서 미제출신고", SECTION_GATE, evidence.DISCLOSURE_SOURCE_NAME
    ),
    ItemDefinition("G-4", "재무제표 첨부 형식", SECTION_GATE, "DART 감사보고서"),
    ItemDefinition("A-1", "법인 기본정보", SECTION_ENTITY, evidence.COMPANY_SOURCE_NAME),
    ItemDefinition("A-2", "사업자등록 상태", SECTION_ENTITY, evidence.NTS_SOURCE_NAME),
    ItemDefinition("A-3", "규모 지표", SECTION_ENTITY, "DART 감사보고서"),
    ItemDefinition("A-4", "정보 일관성", SECTION_ENTITY, evidence.CONFLICT_SOURCE_NAME),
    ItemDefinition("B-1", "매출·손익 3개년", SECTION_FINANCE, "DART 감사보고서"),
    ItemDefinition("B-2", "자산·부채·자본 3개년", SECTION_FINANCE, "DART 감사보고서"),
    ItemDefinition("B-3", "현금흐름 3개년", SECTION_FINANCE, "DART 감사보고서"),
    ItemDefinition("B-4", "감사의견", SECTION_FINANCE, "DART 감사보고서"),
    ItemDefinition("B-5", "차입금", SECTION_FINANCE, NOTES_SOURCE_NAME),
    ItemDefinition("B-6", "계속기업 불확실성", SECTION_FINANCE, NOTES_SOURCE_NAME),
    ItemDefinition("C-1", "주주 구성·지분율", SECTION_CAPITAL, NOTES_SOURCE_NAME),
    ItemDefinition("C-2", "자본금·발행주식", SECTION_CAPITAL, NOTES_SOURCE_NAME),
    ItemDefinition("C-3", "투자성 증권", SECTION_CAPITAL, NOTES_SOURCE_NAME),
    ItemDefinition("C-4", "투자 라운드·금액", SECTION_CAPITAL, "미연동"),
    ItemDefinition("D-1", "주요 사업 내용", SECTION_BUSINESS, NOTES_SOURCE_NAME),
    ItemDefinition("D-2", "특허", SECTION_BUSINESS, "KIPRIS"),
    ItemDefinition("D-3", "주요 매출처", SECTION_BUSINESS, "DART 감사보고서"),
    ItemDefinition("D-4", "최근 동향", SECTION_BUSINESS, "뉴스 검색"),
    ItemDefinition("E-1", "특수관계자 거래", SECTION_RISK, NOTES_SOURCE_NAME),
    ItemDefinition("E-2", "우발채무·소송·보증", SECTION_RISK, NOTES_SOURCE_NAME),
    ItemDefinition("E-3", "공시 정정 이력", SECTION_RISK, evidence.DISCLOSURE_SOURCE_NAME),
)

_BY_ID = {item.item_id: item for item in ITEMS}


def definition(item_id: str) -> ItemDefinition:
    """항목 정의를 꺼낸다. 없는 id 는 오타이므로 실패시킨다."""
    try:
        return _BY_ID[item_id]
    except KeyError:
        raise KeyError(f"정의되지 않은 항목: {item_id}") from None


# ---------------------------------------------------------------------------
# [3] 결과와 팩토리
# ---------------------------------------------------------------------------
class Finding(TypedDict):
    item_id: str
    label: str
    section: str
    verdict: str
    value: str | None
    evidence_ids: list[str]
    source: evidence.Source
    warnings: list[str]


def finding(
    item: ItemDefinition,
    verdict: Verdict,
    *,
    value: str | None = None,
    evidence_ids: list[str] | None = None,
    source: evidence.Source | None = None,
    warnings: list[str] | None = None,
) -> Finding:
    """판정 결과 하나. 정의에서 id·label·section 을 자동으로 옮긴다.

    두 가지를 여기서 강제한다.

    1. verdict 가 CONFIRMED 가 아니면 value 를 None 으로 만든다. 판정 함수가 실수로
       값을 넘겨도 여기서 막힌다. "확인하지 못했다" 고 말하면서 값을 같이 보여주는
       모순이 구조적으로 생기지 않는다.

    2. evidence_ids 는 verdict 와 무관하게 남긴다. ABSENT 의 근거는 "주석 목차를
       전수 확인했다" 는 조각이고, 그걸 지우면 부재 확인이 근거를 잃는다.
       (feat/보고서생성 브랜치는 originalText 를 함께 지웠는데 그 지점만 갈라선다.)

    source 는 어느 판정에서든 채운다. 무엇을 확인하려 했는지가 부재의 근거다.
    """
    return {
        "item_id": item.item_id,
        "label": item.label,
        "section": item.section,
        "verdict": verdict.value,
        "value": value if verdict is Verdict.CONFIRMED else None,
        "evidence_ids": list(evidence_ids or []),
        "source": source or _default_source(item),
        "warnings": list(warnings or []),
    }


def _default_source(item: ItemDefinition) -> evidence.Source:
    """출처를 특정하지 못했을 때의 최소 형태. 이름만이라도 남긴다."""
    return {
        "name": item.source_name,
        "as_of": None,
        "as_of_kind": None,
        "document_url": None,
        "rcept_no": None,
    }


# ---------------------------------------------------------------------------
# [4] 게이트 - 결과가 하위 블록 전체를 좌우한다
# ---------------------------------------------------------------------------
DART_OK = "000"


class GateState(TypedDict):
    """게이트 판정 결과. B 블록 함수들이 첫 줄에서 이걸 보고 갈린다."""

    registered: bool          # G-1. DART 기업개황을 정상 조회했는가
    audited: bool             # G-2. 감사보고서를 한 건이라도 받았는가
    reports: list[dict]       # 최신순. audited 가 False 면 빈 리스트
    latest: dict | None       # 최신 보고서. G-4 와 A-3·A-4 가 이걸 본다
    summary_fallback: bool    # G-4. FINANCE 표 0개가 정상인 문서인가
    non_submission: list[dict]  # G-3. G-2 가 0건일 때만 채워진다


def gate_state(collected: dict[str, Any]) -> GateState:
    """수집 결과 -> 게이트 판정.

    G-4 를 따로 두는 이유: IFRS 채택사와 의견거절 문서는 FINANCE 표가 아예 없는 것이
    정상이다(실측 8.3% + 5.0%). 구분하지 않으면 정상 문서를 EXTRACTION_FAILED 로
    오판한다.
    """
    company = collected.get("company") or {}
    reports = list(collected.get("audit_reports") or [])
    latest = reports[0] if reports else None

    return {
        "registered": company.get("status") == DART_OK,
        "audited": bool(reports),
        "reports": reports,
        "latest": latest,
        "summary_fallback": (
            st.needs_summary_fallback(latest["clean"]) if latest else False
        ),
        "non_submission": list(collected.get("non_submission") or []),
    }


# ---------------------------------------------------------------------------
# [5] 주석 항목 공통 분기
# ---------------------------------------------------------------------------
class NoteContext(TypedDict):
    """보고서 한 건의 주석 상태. 항목마다 다시 쪼개지 않으려고 한 번만 만든다."""

    parsed: bool                    # 주석 섹션을 찾아 하위항목으로 쪼갰는가
    subsections: list[dict[str, Any]]
    gaps: list[int]                 # 번호 결번. 있으면 항목을 놓쳤을 수 있다


def note_context(report: dict[str, Any] | None) -> NoteContext:
    """보고서 -> 주석 하위항목과 결번."""
    if report is None:
        return {"parsed": False, "subsections": [], "gaps": []}

    section = nt.find_notes_section(report["clean"])
    if section is None:
        return {"parsed": False, "subsections": [], "gaps": []}

    subsections = nt.split_subsections(section)
    if not subsections:
        return {"parsed": False, "subsections": [], "gaps": []}

    return {
        "parsed": True,
        "subsections": subsections,
        "gaps": nt.numbering_gaps(subsections),
    }


def note_verdict(
    context: NoteContext, topic: str, *, audited: bool
) -> tuple[Verdict, dict[str, Any] | None]:
    """주석 하위항목 하나를 찾는 4갈래 분기. B-5·B-6 과 이후 E-1·E-2 가 함께 쓴다.

        문서 없음        -> SOURCE_UNAVAILABLE
        주석 못 읽음      -> EXTRACTION_FAILED
        찾음             -> CONFIRMED
        못 찾았는데 결번   -> EXTRACTION_FAILED
        못 찾았고 결번 0   -> ABSENT

    마지막 두 갈래를 나누는 이유: 목차가 온전해야 "없다" 를 단정할 수 있다. 번호가
    빠져 있으면 그 자리에 있었을지도 모르는 항목을 우리가 놓친 것일 수 있다.
    실측(감사보고서 74건)에서 결번이 있는 문서가 2건 나왔으므로 헛도는 분기가 아니다.

    제목 앞 30자만 본다. 본문 전역을 훑으면 다른 항목이 지나가는 말로 꺼낸 단어에
    걸린다 - '충당부채' 는 주석이 아니라 재무상태표 세부항목에서 잡힌다는 실측 오탐이
    있다.
    """
    if not audited:
        return Verdict.SOURCE_UNAVAILABLE, None

    if not context["parsed"]:
        return Verdict.EXTRACTION_FAILED, None

    found = nt.find_subsection(context["subsections"], topic)
    if found is not None:
        return Verdict.CONFIRMED, found

    if context["gaps"]:
        return Verdict.EXTRACTION_FAILED, None

    return Verdict.ABSENT, None
