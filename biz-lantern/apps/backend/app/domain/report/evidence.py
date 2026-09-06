"""보고서가 인용할 근거(Evidence) 조각을 만든다.

보고서의 모든 문장은 근거 ID 를 달고, 토글을 열면 DART 원문 스냅샷까지 닿아야 한다.
그 조각을 만드는 곳이 여기다. 판정(infer)도 서술(compose)도 전부 이 위에서 돈다.

수집·정리 계층(api/ · parser/ · pipeline)은 한 줄도 건드리지 않는다. 그 결과 dict 를
받아 읽기만 한다.

    [1] 자료형        Evidence · Source · Locator · ConflictSide
    [2] ID 규칙       네임스페이스 · 슬러그 · make_id · account_key
    [3] 출처          DART 뷰어 링크 · 출처별 source 생성기
    [4] 숫자 토큰     후검증이 대조할 집합
    [5] 조각 팩토리   API 필드 · 감사보고서 · 주석 · 파생/충돌
    [6] 레지스트리    EvidenceStore

설계에서 물러서지 않는 지점 다섯 가지

1. 조각은 참조될 때만 만든다.
   팩토리는 순수 함수고, 등록은 EvidenceStore 가 한다. 수집 결과를 통째로 조각화하지
   않는다 - 센트비 주석만 170블록이라 전량 조각화하면 인용되지도 않은 근거가 보고서에
   실린다. dump() 가 등록된 것만 돌려주므로 이 원칙이 구조적으로 강제된다.

2. 스냅샷과 로케이터를 둘 다 저장한다.
   raw_content 는 보고서에 굳는 원문이고, locator 는 추적용 좌표다. 위치만 저장하면
   파서를 고치는 순간 과거 보고서의 앵커가 전부 어긋난다. 반대로 스냅샷만 저장하면
   원문으로 되돌아갈 길이 없다.

3. raw_content 는 자르지 않는다. 항상 str 이고 None 이 아니다.
   빈 문자열은 "출처는 확인했는데 값이 비어 있었다" 는 뜻이다(계속사업자의 폐업일).
   문자열 자르기는 문장을 중간에서 끊어 근거 구실을 못 하게 만든다.

4. 시계를 읽지 않는다.
   datetime.now() 를 부르지 않는다. 조회일이 필요한 출처는 as_of 를 필수 인자로
   강제한다. 그러지 않으면 같은 입력이 날짜마다 다른 조각을 만들어 "재실행하면 같은
   ID · 같은 내용" 이라는 요구가 깨진다.

5. 단위를 환산하지 않는다.
   statements.summary_financials() 가 백만원을 원으로 이미 바꿔 주지만, 조각의
   raw_content 에는 원문만 넣는다. 환산은 F 블록 파생 근거의 일이다. 그래야
   "LLM 은 F 파생 근거에 적힌 숫자만 쓸 수 있다" 는 후검증 규칙이 성립한다.
"""

import hashlib
import logging
import re
from collections.abc import Iterable, Sequence
from typing import Any, Literal, TypedDict

from app.domain.company.parser.statements import (
    BALANCE_SHEET,
    CASH_FLOW,
    CURRENT_PERIOD,
    EQUITY_CHANGE,
    INCOME_STATEMENT,
    OPINION_CODE,
    OPINION_LABELS,
    PRIOR_PERIOD,
    REPORTED_ACCOUNTS,
    label_key,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# [1] 자료형
# ---------------------------------------------------------------------------
EvidenceType = Literal[
    "api_field",  # 기업개황 · 국세청 · 공시목록의 필드 하나
    "summary",    # EXTRACTION ACODE 한 칸
    "account",    # 재무제표 계정 하나 (당기·전기 값 포함)
    "table",      # 표 블록 하나. 행으로 쪼개지 않는다
    "paragraph",  # 문단 블록 하나
    "note",       # 주석 하위항목 하나. 존재 자체가 판정 근거다
    "derived",    # F 블록 파생 계산
    "conflict",   # A-4 교차검증에서 갈린 값
    "news",       # 예약 - 팩토리는 아직 없다
    "patent",     # 예약 - 팩토리는 아직 없다
]


class Source(TypedDict):
    """출처. 판정이 CONFIRMED 가 아니어도 항상 채운다.

    무엇을 확인하려 했는지가 곧 부재 확인의 근거다.
    """

    name: str
    as_of: str | None
    as_of_kind: str | None  # 기준일 / 조회일 / 접수일
    document_url: str | None
    rcept_no: str | None


class Locator(TypedDict, total=False):
    """조각이 원문 어디서 나왔는지. 추적용이지 앵커가 아니다."""

    kind: str
    corp_code: str
    rcept_no: str
    bizr_no: str
    field: str
    summary_code: str
    statement: str
    account_code: str  # ACODE 14자리 원문. ID 는 앞 9자리만 쓴다
    logical_name: str
    section_title: str | None
    subsection_number: int
    block_index: int  # 하위항목 안에서의 인덱스. ID 와 같은 값
    block_index_in_section: int | None  # 섹션 전역 인덱스. ID 에는 안 쓴다


class ConflictSide(TypedDict):
    """충돌한 두 값 중 한쪽."""

    label: str
    value: str
    as_of: str | None
    as_of_kind: str | None
    based_on: str


class _EvidenceBase(TypedDict):
    evidence_id: str
    type: EvidenceType
    label: str
    raw_content: str
    numbers: list[str]
    units: list[str]
    locator: Locator
    source: Source


class Evidence(_EvidenceBase, total=False):
    context: dict[str, str]  # api_field 의 형제 컨텍스트
    table: dict[str, Any]    # 표 격자 원본
    account: dict[str, Any]  # 계정 원본 (부호 보정된 값이 여기 있다)
    based_on: list[str]      # derived · conflict 가 딛고 선 근거
    formula: str
    rule_id: str
    conflict_kind: str
    resolution: str
    sides: list[ConflictSide]


# 충돌 유형과 처리. 판정은 infer 가 하고 여기서는 표기만 갖는다.
CONFLICT_TIMING = "timing"            # 시점 차이
CONFLICT_RELIABILITY = "reliability"  # 신뢰도 차이
CONFLICT_IDENTITY = "identity"        # 식별자 대조 불가

CONFLICT_KIND_LABELS = {
    CONFLICT_TIMING: "시점 차이",
    CONFLICT_RELIABILITY: "신뢰도 차이",
    CONFLICT_IDENTITY: "식별자 대조 불가",
}

RESOLUTION_BOTH = "both"
RESOLUTION_DART_FIRST = "dart_first"

RESOLUTION_LABELS = {
    RESOLUTION_BOTH: "병기",
    RESOLUTION_DART_FIRST: "DART 채택",
}


# ---------------------------------------------------------------------------
# [2] ID 규칙 - 결정적이어야 한다
# ---------------------------------------------------------------------------
# 랜덤 UUID 를 쓰지 않는다. 재실행마다 ID 가 바뀌면 보고서 간 비교도, 과거 보고서의
# 근거 추적도 불가능하다.
ID_PREFIX = "EV"

NS_COMPANY = "dart.company"
NS_DISCLOSURE = "dart.disclosure"
NS_NTS = "nts"
NS_SUMMARY = "audit.summary"
NS_ACCOUNT = "audit.account"
NS_TABLE = "audit.table"
NS_NOTE = "audit.note"
NS_PARA = "audit.para"
NS_DERIVED = "derived"
NS_CONFLICT = "conflict"

NS_NEWS = "news"

# 예약. 팩토리는 없다 - KIPRIS 응답 키가 실서버로 검증된 적이 없다.
NS_PATENT = "kipris.patent"

# 재무제표 약칭. ID 에 들어가므로 한 곳에서만 정한다.
STATEMENT_ABBR = {
    BALANCE_SHEET: "BS",
    INCOME_STATEMENT: "IS",
    CASH_FLOW: "CF",
    EQUITY_CHANGE: "SE",
}

# document_clean 이 표준코드 없는 회사 고유 계정에 붙이는 값
PLACEHOLDER_ACODE = "99999999999999"
LABEL_KEY_PREFIX = "L:"
_LABEL_SLUG_MAX = 40

_SEGMENT_UNSAFE = re.compile(r"\s+")
_SLUG_UNSAFE = re.compile(r"[\s:|]+")
_ID_SEGMENTS = 4


def _segment(text: str) -> str:
    """ID 세그먼트로 쓸 수 있게 공백만 지운다."""
    return _SEGMENT_UNSAFE.sub("_", (text or "").strip())


def _slug(text: str) -> str:
    """라벨 -> ID 세그먼트. 구분자와 공백을 없애고 길이를 제한한다."""
    return _SLUG_UNSAFE.sub("_", (text or "").strip())[:_LABEL_SLUG_MAX]


def make_id(namespace: str, *segments: str) -> str:
    """EV:{네임스페이스}:{세그먼트...}"""
    return ":".join([ID_PREFIX, namespace, *(_segment(s) for s in segments)])


def validate_id(evidence_id: str) -> str:
    """형식을 확인하고 그대로 돌려준다. 어기면 ValueError.

    조각 ID 가 깨지는 건 프로그래밍 오류다. 조용히 넘기면 8번 후검증이 존재하지 않는
    근거를 통과시킨다.
    """
    if not isinstance(evidence_id, str) or not evidence_id:
        raise ValueError(f"근거 ID 가 비었다: {evidence_id!r}")

    parts = evidence_id.split(":")

    if parts[0] != ID_PREFIX:
        raise ValueError(f"근거 ID 는 EV: 로 시작해야 한다: {evidence_id}")
    if len(parts) < _ID_SEGMENTS:
        raise ValueError(f"근거 ID 세그먼트가 부족하다: {evidence_id}")
    if any(not part for part in parts):
        raise ValueError(f"근거 ID 에 빈 세그먼트가 있다: {evidence_id}")
    if any(char.isspace() for char in evidence_id):
        raise ValueError(f"근거 ID 에 공백이 있다: {evidence_id}")

    return evidence_id


def account_key(entry: dict[str, Any], name: str | None = None) -> str:
    """계정 조각의 ID 꼬리. 논리 계정 > ACODE 앞 9자리 > 라벨.

    왜 논리 계정이 문서의 코드보다 먼저인가 (2026-09-05 실측, 감사보고서 73건)

        접수번호 20260410002719 문서는 자산총계·부채총계·자본총계·부채및자본총계에
        전부 같은 ACODE 11000000000000 을 달아 놓았다. 문서의 코드를 앵커로 믿으면
        서로 다른 세 계정이 한 ID 로 뭉개진다(EvidenceStore 가 충돌로 잡아냈다).

        우리는 그 행을 "코드가 무엇인지" 로 찾은 것이 아니라 statements.find_account
        가 REPORTED_ACCOUNTS 의 논리 계정으로 찾은 것이다. 그러니 앵커도 문서가 뭐라
        적었는지가 아니라 우리가 무엇을 찾았는지를 가리켜야 한다. 문서가 적은 14자리
        원문은 locator.account_code 에 그대로 남는다.

        덤으로 트래블월렛처럼 ACODE 가 빈 계정도 다른 회사와 같은 앵커를 갖게 되어
        문서 간 비교가 된다.

    왜 14자리 전체가 아니라 앞 9자리인가

        뒤 5자리가 이익(10000)/손실(20000)을 인코딩한다. 14자리를 그대로 쓰면 같은
        영업이익 계정이 흑자 연도와 적자 연도에 서로 다른 ID 를 갖게 되고, F-3
        (손익 전환) 이 연도를 이을 수 없다. 14자리 원문은 locator 에 남긴다.

    왜 위치 인덱스로 폴백하지 않는가

        트래블월렛 현금흐름표의 level 0 계정은 ACODE 가 빈 문자열이다(실측). 위치로
        도망가면 표가 한 줄만 바뀌어도 앵커가 어긋난다. 라벨은 문서가 인쇄한 값이라
        훨씬 안정적이다.
    """
    reported = REPORTED_ACCOUNTS.get(name or "")
    if reported is not None:
        return reported[1]

    code = entry.get("code") or ""

    if len(code) >= 9 and code != PLACEHOLDER_ACODE:
        return code[:9]

    return LABEL_KEY_PREFIX + _slug(label_key(entry.get("label") or ""))


# ---------------------------------------------------------------------------
# [3] 출처
# ---------------------------------------------------------------------------
# DART 원문 뷰어 링크는 이 저장소 어디에도 쓰인 적이 없다. api/ 에 있는 URL 은 전부
# opendart.fss.or.kr 의 API 엔드포인트고 crtfc_key 를 쿼리로 요구하는데, 그걸
# document_url 에 넣으면 인증키가 보고서 JSON 에 그대로 굳는다(pipeline.py 가
# _SECRET_PARAM 으로 로그에서 키를 지우는 것과 같은 이유로 넣지 않는다).
#
# 아래는 알려진 뷰어 형식이지만 이 저장소에서 확인된 사실이 아니다. 배포 전에 실물
# 확인이 필요하다. 또 이 URL 은 프레임셋 표지까지만 연다 - 본문 프레임이 요구하는
# dcmNo 를 우리는 갖고 있지 않아 문단 단위 딥링크는 원리적으로 불가능하다.
DART_VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

COMPANY_SOURCE_NAME = "DART 기업개황"
DISCLOSURE_SOURCE_NAME = "DART 공시검색"
NTS_SOURCE_NAME = "국세청 사업자등록정보 (진위확인)"
DERIVED_SOURCE_NAME = "파생 계산 (룰베이스)"
CONFLICT_SOURCE_NAME = "출처 교차검증"

AS_OF_LOOKUP = "조회일"
AS_OF_FISCAL = "기준일"
AS_OF_RECEIPT = "접수일"
AS_OF_PUBLISHED = "발행일"

NEWS_SOURCE_NAME = "뉴스 검색"


def document_url(rcept_no: str | None) -> str | None:
    """접수번호 -> DART 원문 링크. 접수번호가 없으면 None."""
    if not rcept_no:
        return None

    return DART_VIEWER_URL.format(rcept_no=rcept_no)


def _dashed_date(value: str | None) -> str | None:
    """20260331 -> 2026-03-31. 형식이 다르면 원문 그대로 둔다."""
    if not value:
        return None

    text = str(value).strip()

    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"

    return text


def company_source(as_of: str) -> Source:
    """기업개황. 레코드별 공개 URL 이 없어 document_url 은 None 이다."""
    return {
        "name": COMPANY_SOURCE_NAME,
        "as_of": as_of,
        "as_of_kind": AS_OF_LOOKUP,
        "document_url": None,
        "rcept_no": None,
    }


def nts_source(as_of: str) -> Source:
    return {
        "name": NTS_SOURCE_NAME,
        "as_of": as_of,
        "as_of_kind": AS_OF_LOOKUP,
        "document_url": None,
        "rcept_no": None,
    }


def disclosure_source(item: dict[str, Any]) -> Source:
    rcept_no = item.get("rcept_no")

    return {
        "name": DISCLOSURE_SOURCE_NAME,
        "as_of": _dashed_date(item.get("rcept_dt")),
        "as_of_kind": AS_OF_RECEIPT,
        "document_url": document_url(rcept_no),
        "rcept_no": rcept_no,
    }


def report_source(report: dict[str, Any]) -> Source:
    """감사보고서. 기준일은 접수일이 아니라 회계연도 말일이다."""
    rcept_no = report["rcept_no"]

    return {
        "name": report.get("report_nm") or "감사보고서",
        "as_of": report.get("fiscal_year"),
        "as_of_kind": AS_OF_FISCAL,
        "document_url": document_url(rcept_no),
        "rcept_no": rcept_no,
    }


def news_source(article: dict[str, Any]) -> Source:
    """기사 한 건. 기준일은 조회일이 아니라 **발행일**이다.

    document_url 에 기사 URL 을 그대로 둔다. DART 조각은 프레임셋이라 문단 딥링크가
    원리적으로 불가능했지만(DART_VIEWER_URL 주석) 기사는 그 주소가 곧 원문이다.
    """
    return {
        "name": article.get("site") or NEWS_SOURCE_NAME,
        "as_of": article.get("published_on"),
        "as_of_kind": AS_OF_PUBLISHED,
        "document_url": article.get("url"),
        "rcept_no": None,
    }


# ---------------------------------------------------------------------------
# [4] 숫자 토큰 - 후검증이 대조할 집합
# ---------------------------------------------------------------------------
# 8번 후검증은 "문장에 쓰인 숫자가 인용한 근거의 원문에 실제로 있는가" 를 본다.
# 그 대조 집합을 조각에 굳혀 저장한다. 매번 다시 토큰화하면 토크나이저를 고치는
# 순간 과거 보고서의 검증 결과가 달라진다 - 스냅샷 원칙은 토큰에도 적용된다.
#
# 부호는 떼고 저장한다. (1,234) / △1,234 / -1,234 가 모두 같은 값을 가리키는데
# 표기만 다르므로, 부호를 남기면 표기 차이만으로 멀쩡한 문장이 폐기된다. 부호의
# 정확성은 토큰 대조가 아니라 F 블록 파생 근거가 책임진다.
#
# 콤마는 반드시 세 자리를 끊을 때만 인정한다. 아무 콤마나 지우면 주석 참조가
# 금액으로 둔갑한다 - 업스테이지 '자본금(주석1,12)' 의 '1,12' 가 '112' 라는 있지도
# 않은 숫자가 되어, 후검증이 그 값을 쓴 문장을 통과시킨다(실측).
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")

# 긴 것부터 본다. 백만원을 원으로 잡으면 안 된다.
UNIT_WORDS = ("백만원", "천만원", "천원", "억원", "조원", "원", "%", "주", "달러")

# 법인격 표기는 단위가 아니다. 여기를 지우지 않으면 '(주)센트비' 의 '주' 가 주식 수
# 단위로 잡혀 **회사명이 들어간 문장이 전부 폐기된다**(실서버 실측 - G-1·G-2 가
# "허용되지 않은 단위: 주" 로 죽었다). 회사명은 거의 모든 항목에 등장하므로 파장이 크다.
_ENTITY_MARK = re.compile(r"\(주\)|㈜|\(유\)|\(재\)|\(사\)|주식회사|유한회사")


def number_tokens(text: str) -> list[str]:
    """텍스트 -> 정규화된 숫자 토큰. 콤마를 지우고 부호는 떼며 순서를 지킨다."""
    tokens: list[str] = []
    seen: set[str] = set()

    for match in _NUMBER.finditer(text or ""):
        token = match.group().replace(",", "")

        if not token or token in seen:
            continue

        seen.add(token)
        tokens.append(token)

    return tokens


def unit_tokens(text: str) -> list[str]:
    """텍스트에 실제로 나온 단위 어휘. 법인격 표기는 세지 않는다."""
    remaining = _ENTITY_MARK.sub(" ", text or "")
    found: list[str] = []

    for word in UNIT_WORDS:
        if word in remaining:
            found.append(word)
            remaining = remaining.replace(word, " ")

    return found


# ---------------------------------------------------------------------------
# [5] 조각 팩토리
# ---------------------------------------------------------------------------
COMPANY_FIELD_LABELS = {
    "corp_name": "법인명",
    "corp_code": "DART 고유번호",
    "ceo_nm": "대표이사",
    "est_dt": "설립일",
    "adres": "소재지",
    "jurir_no": "법인등록번호",
    "bizr_no": "사업자등록번호",
    "induty_code": "업종코드",
    "acc_mt": "결산월",
    "hm_url": "홈페이지",
    "corp_cls": "법인구분",
    "stock_code": "종목코드",
    "stock_name": "종목명",
}

NTS_FIELD_LABELS = {
    "verified": "진위확인 결과",
    "valid_code": "진위확인 코드",
    "operating": "정상 영업 여부",
    "status_code": "사업자상태 코드",
    "status": "사업자상태",
    "tax_type": "과세유형",
    "closed_at": "폐업일",
}

SUMMARY_LABELS = {
    OPINION_CODE: "감사의견",
    "IFRS_YN": "IFRS 채택 여부",
    "TOT_ASSETS": "자산총계(백만원)",
    "TOT_DEBTS": "부채총계(백만원)",
    "TOT_SALES": "매출액(백만원)",
    "TOT_EMPL": "직원수",
    "CRP_RGS_NO": "법인등록번호",
}

ACCOUNT_LABELS = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "total_assets": "자산총계",
    "total_liabilities": "부채총계",
    "total_equity": "자본총계",
    "capital_stock": "자본금",
    "operating_cash_flow": "영업활동현금흐름",
    "investing_cash_flow": "투자활동현금흐름",
    "financing_cash_flow": "재무활동현금흐름",
    "trade_receivable": "매출채권",
    "other_receivable": "미수금",
    "short_term_borrowings": "단기차입금",
    "long_term_borrowings": "장기차입금",
    "bond_with_warrant": "신주인수권부사채",
    "common_capital": "보통주자본금",
    "preferred_capital": "우선주자본금",
}

STATEMENT_LABELS = {
    BALANCE_SHEET: "재무상태표",
    INCOME_STATEMENT: "손익계산서",
    CASH_FLOW: "현금흐름표",
    EQUITY_CHANGE: "자본변동표",
}

# 형제 컨텍스트의 기본값. 토글에 값만 덩그러니 뜨면 어느 법인 것인지 알 수 없다.
# 기업개황 dict 를 통째로 복사하지 않는 이유는 조각마다 같은 내용이 11번 실리기
# 때문이다. 더 필요하면 호출부가 context_fields 로 넓힌다.
IDENTITY_FIELDS = ("corp_name", "corp_code")

_PERIOD_ORDER = (CURRENT_PERIOD, PRIOR_PERIOD)


def _text(value: Any) -> str:
    """조각의 raw_content 는 항상 문자열이다. None 은 빈 문자열이 된다."""
    if value is None:
        return ""

    return str(value)


def _evidence(
    evidence_id: str,
    kind: EvidenceType,
    label: str,
    raw_content: str,
    locator: Locator,
    source: Source,
    **extra: Any,
) -> Evidence:
    """공통 조립. 숫자·단위 토큰은 여기서 한 번만 만든다."""
    evidence: dict[str, Any] = {
        "evidence_id": validate_id(evidence_id),
        "type": kind,
        "label": label,
        "raw_content": raw_content,
        "numbers": number_tokens(raw_content),
        "units": unit_tokens(raw_content),
        "locator": locator,
        "source": source,
    }
    evidence.update({key: value for key, value in extra.items() if value is not None})

    return evidence  # type: ignore[return-value]


def flatten_table(block: dict[str, Any]) -> str:
    """표 -> 후검증과 LLM 이 읽을 평탄화 문자열. 셀은 한 글자도 바꾸지 않는다.

    document_clean 의 표 렌더러는 재사용하지 않는다. private 인 데다 across 칸을
    비우는 보여주기용 가공을 하는데, 그 가공본을 스냅샷으로 굳히면 원문 보존 원칙과
    충돌한다.
    """
    lines = [" | ".join(row) for row in (block.get("header") or [])]
    lines += [" | ".join(row) for row in (block.get("rows") or [])]

    return "\n".join(lines)


def _table_payload(block: dict[str, Any]) -> dict[str, Any]:
    """프론트 표 렌더러가 쓸 격자 원본. 문자열과 둘 다 저장한다."""
    return {
        "class": block.get("class"),
        "header": block.get("header"),
        "rows": block.get("rows"),
        "across": block.get("across"),
        "units": block.get("units"),
    }


# ---- [5-1] API 필드 --------------------------------------------------------
def company_field(
    company: dict[str, Any],
    field: str,
    *,
    as_of: str,
    context_fields: Sequence[str] = IDENTITY_FIELDS,
) -> Evidence:
    """DART 기업개황의 필드 하나."""
    corp_code = company["corp_code"]

    return _evidence(
        make_id(NS_COMPANY, corp_code, field),
        "api_field",
        COMPANY_FIELD_LABELS.get(field, field),
        _text(company.get(field)),
        {"kind": NS_COMPANY, "corp_code": corp_code, "field": field},
        company_source(as_of),
        context={key: _text(company.get(key)) for key in context_fields},
    )


def nts_field(
    nts: dict[str, Any], bizr_no: str, field: str, *, as_of: str
) -> Evidence:
    """국세청 사업자등록 확인 결과의 필드 하나.

    형제 컨텍스트에 verified 를 함께 넣는다. 진위확인이 불일치면 사업자상태는
    조회되지 않은 값이라, 그 사실 없이 status 만 보면 폐업과 대조 실패를 구분할 수
    없다.
    """
    return _evidence(
        make_id(NS_NTS, bizr_no, field),
        "api_field",
        NTS_FIELD_LABELS.get(field, field),
        _text(nts.get(field)),
        {"kind": NS_NTS, "bizr_no": bizr_no, "field": field},
        nts_source(as_of),
        context={"b_no": bizr_no, "verified": _text(nts.get("verified"))},
    )


def disclosure_view(report: dict[str, Any]) -> dict[str, Any]:
    """감사보고서 -> 공시 목록 항목 모양.

    disclosure_item 은 list.json 항목을 받는데 수집 단계가 제출인을 flr_nm 이 아니라
    auditor 로 옮겨 담았으므로 이름을 되돌려 준다 - 감사인이 누구였는지가 감사보고서
    근거의 핵심 정보다.

    infer 안에 두었던 것을 여기로 올렸다. investigate 도 같은 변환이 필요한데 그쪽이
    infer 를 import 하면 infer -> detect -> investigate -> infer 순환이 된다. 애초에
    disclosure_item 의 입력 모양을 맞추는 일이라 이 파일의 몫이다.
    """
    return {
        "rcept_no": report["rcept_no"],
        "rcept_dt": report.get("rcept_dt"),
        "report_nm": report.get("report_nm"),
        "flr_nm": report.get("auditor"),
    }


def disclosure_item(corp_code: str, item: dict[str, Any]) -> Evidence:
    """공시 목록 항목 하나. E-3(정정 이력)과 G-3(미제출신고)의 근거다.

    감사보고서 본문이 아니라 목록이므로 audit.* 네임스페이스에 넣지 않는다.
    """
    rcept_no = item["rcept_no"]
    report_nm = item.get("report_nm") or ""
    parts = [
        _dashed_date(item.get("rcept_dt")),
        report_nm,
        f"제출인 {item['flr_nm']}" if item.get("flr_nm") else None,
        f"비고 {item['rm']}" if item.get("rm") else None,
    ]

    return _evidence(
        make_id(NS_DISCLOSURE, corp_code, rcept_no),
        "api_field",
        report_nm or "공시",
        " ".join(part for part in parts if part),
        {"kind": NS_DISCLOSURE, "corp_code": corp_code, "rcept_no": rcept_no},
        disclosure_source(item),
    )


# ---- [5-2] 감사보고서 - 요약 · 계정 · 표 -----------------------------------
def summary_field(report: dict[str, Any], code: str) -> Evidence:
    """표지 EXTRACTION 의 ACODE 한 칸.

    raw_content 에는 코드 원문을 그대로 둔다. 감사의견을 적정이라는 한글로 굳히면
    문자열 매칭이 되살아난다 - 보유 문서 5건 전부에서 실패했던 그 방식이다. 해석은
    label 에만 붙인다.

    ACODE 화이트리스트를 두지 않는다. A-3(직원수 TOT_EMPL)과 A-4(법인등록번호
    CRP_RGS_NO)가 statements.py 의 상수에 없는 코드를 쓴다.
    """
    rcept_no = report["rcept_no"]
    raw = _text((report["clean"].get("summary") or {}).get(code))

    label = SUMMARY_LABELS.get(code, code)
    if code == OPINION_CODE and OPINION_LABELS.get(raw):
        label = f"{label} ({OPINION_LABELS[raw]})"

    return _evidence(
        make_id(NS_SUMMARY, rcept_no, code),
        "summary",
        label,
        raw,
        {"kind": NS_SUMMARY, "rcept_no": rcept_no, "summary_code": code},
        report_source(report),
    )


def account(report: dict[str, Any], name: str, entry: dict[str, Any]) -> Evidence:
    """재무제표 계정 하나. entry 는 statements.extract_financials() 의 항목이다.

    raw_content 에는 periods 의 raw 원문만 넣는다. 부호 보정된 값은 account 쪽에만
    둔다 - 후검증의 기준선이 원문이기 때문이다.
    """
    rcept_no = report["rcept_no"]
    statement = entry["statement"]
    periods = entry.get("periods") or {}

    parts = [entry["label"]]
    for period in _PERIOD_ORDER:
        value = periods.get(period)
        if value is None:
            continue
        parts.append(f"{value.get('header') or period} {value['raw']}")

    return _evidence(
        make_id(
            NS_ACCOUNT, rcept_no, STATEMENT_ABBR[statement], account_key(entry, name)
        ),
        "account",
        f"{ACCOUNT_LABELS.get(name, name)} ({entry['label']})",
        " | ".join(parts),
        {
            "kind": NS_ACCOUNT,
            "rcept_no": rcept_no,
            "statement": statement,
            "account_code": _text(entry.get("code")),
            "logical_name": name,
        },
        report_source(report),
        account={
            "logical_name": name,
            "code": entry.get("code"),
            "statement": statement,
            "periods": periods,
        },
    )


def statement_table(
    report: dict[str, Any], statement: str, block: dict[str, Any]
) -> Evidence:
    """재무제표 표 하나.

    FINANCE 표는 있는데 계정을 못 찾았다(EXTRACTION_FAILED)를 말하려면 그 표 자체를
    보여줘야 한다. 그 경우 원문에 닿는 유일한 조각이다.
    """
    rcept_no = report["rcept_no"]

    return _evidence(
        make_id(NS_TABLE, rcept_no, STATEMENT_ABBR[statement]),
        "table",
        STATEMENT_LABELS.get(statement, statement),
        flatten_table(block),
        {"kind": NS_TABLE, "rcept_no": rcept_no, "statement": statement},
        report_source(report),
        table=_table_payload(block),
    )


# ---- [5-3] 주석 ------------------------------------------------------------
# 블록 앵커의 k 는 하위항목 안에서의 인덱스다. 섹션 전역 인덱스가 아니다.
#
#     1. 파손 반경   전역 인덱스는 주석 3번에 문단이 하나 늘면 뒤따르는 모든
#                    하위항목의 블록 ID 가 통째로 밀린다.
#     2. 앵커의 출처 s7 의 7 은 문서가 직접 인쇄한 번호다. 파서 산출물이 아니라
#                    원문 내용이라 파서를 다시 써도 변하지 않는다.
#     3. 애초에 없다 split_subsections 가 주는 block_index 는 시작 문단 것 하나뿐이고
#                    뒤따라 붙는 표 블록에는 전역 인덱스가 아예 없다.
#
# 전역 인덱스는 버리지 않고 locator.block_index_in_section 에 남긴다.
def _note_locator(rcept_no: str, subsection: dict[str, Any], **extra: Any) -> Locator:
    locator: dict[str, Any] = {
        "kind": NS_NOTE,
        "rcept_no": rcept_no,
        "subsection_number": subsection["number"],
    }
    locator.update(extra)

    return locator  # type: ignore[return-value]


def note_subsection(report: dict[str, Any], subsection: dict[str, Any]) -> Evidence:
    """주석 하위항목 하나. 본문 전체를 자르지 않고 그대로 굳힌다."""
    rcept_no = report["rcept_no"]
    number = subsection["number"]

    return _evidence(
        make_id(NS_NOTE, rcept_no, f"s{number}"),
        "note",
        f"주석 {number}. {subsection['head']}",
        _text(subsection.get("text")),
        _note_locator(
            rcept_no,
            subsection,
            block_index_in_section=subsection.get("block_index"),
        ),
        report_source(report),
    )


def note_block(
    report: dict[str, Any], subsection: dict[str, Any], index: int
) -> Evidence:
    """주석 하위항목 안의 블록 하나. 문단이면 paragraph, 표면 table."""
    rcept_no = report["rcept_no"]
    number = subsection["number"]
    block = subsection["blocks"][index]
    is_table = block.get("type") == "table"

    # 시작 블록(index 0)만 섹션 전역 인덱스를 안다. 뒤에 붙은 표는 알 길이 없다.
    in_section = subsection.get("block_index") if index == 0 else None

    return _evidence(
        make_id(NS_NOTE, rcept_no, f"s{number}.b{index}"),
        "table" if is_table else "paragraph",
        f"주석 {number}. {subsection['head']}",
        flatten_table(block) if is_table else _text(block.get("text")),
        _note_locator(
            rcept_no,
            subsection,
            block_index=index,
            block_index_in_section=in_section,
        ),
        report_source(report),
        table=_table_payload(block) if is_table else None,
    )


def note_table(
    report: dict[str, Any], subsection: dict[str, Any], block: dict[str, Any]
) -> Evidence:
    """하위항목에 딸린 표. 블록의 위치를 동일성으로 찾아 note_block 에 넘긴다."""
    for index, candidate in enumerate(subsection["blocks"]):
        if candidate is block:
            return note_block(report, subsection, index)

    raise ValueError(
        f"주석 {subsection['number']} 에 속하지 않는 표다. 다른 하위항목의 표를 "
        "잘못 붙이면 근거가 엉뚱한 곳을 가리킨다."
    )


def section_paragraph(
    report: dict[str, Any], section: dict[str, Any], block_index: int
) -> Evidence:
    """주석 밖 문단. 번호가 없어 매달 것이 없으므로 내용 해시로 앵커한다.

    해시는 결정적이고 블록 재배치에 면역이다. 같은 문단이 두 번 나오면 한 조각으로
    합쳐지는데, 그건 오히려 맞다. 대신 불투명하므로 위치는 locator 에 남긴다.
    """
    rcept_no = report["rcept_no"]
    text = _text(section["blocks"][block_index].get("text"))
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    title = section.get("title")

    return _evidence(
        make_id(NS_PARA, rcept_no, f"h{digest}"),
        "paragraph",
        title or "본문",
        text,
        {
            "kind": NS_PARA,
            "rcept_no": rcept_no,
            "section_title": title,
            "block_index": block_index,
        },
        report_source(report),
    )


# ---- [5-3b] 뉴스 -----------------------------------------------------------
def _join(head: str, body: str) -> str:
    """제목 줄과 본문을 잇는다. 본문이 없으면 제목 줄만."""
    return head + chr(10) + body if body else head


def news_item(corp_code: str, article: dict[str, Any]) -> Evidence:
    """기사 한 건.

    raw_content 는 **기사에서 뽑은 텍스트**다. 뉴스 워크플로가 만든 summaries 는 LLM 이
    쓴 것이라 근거로 삼으면 LLM 출력을 근거라고 부르는 셈이 된다 - 이 시스템이 막으려는
    바로 그것이다.

    앵커는 URL 해시다. URL 자체는 길고 ':' 와 '/' 가 섞여 ID 문법에 들어가지 못하는데,
    기사의 동일성은 URL 이 정한다. section_paragraph 가 쓰는 방식과 같다.
    """
    url = _text(article.get("url"))
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]

    head = " | ".join(
        part
        for part in (
            _text(article.get("title")) or "제목 없음",
            _text(article.get("site")),
            _text(article.get("published_on")),
        )
        if part
    )
    body = _text(article.get("content"))

    return _evidence(
        make_id(NS_NEWS, corp_code, f"h{digest}"),
        "news",
        _text(article.get("title")) or "기사",
        _join(head, body),
        {"kind": NS_NEWS, "corp_code": corp_code, "url": url},
        news_source(article),
    )


# ---- [5-4] 파생 · 충돌 -----------------------------------------------------
# 여기 두는 이유: ID 문법의 소유자는 하나여야 하고, based_on 은 그래프 간선이라
# 그것을 만드는 곳과 검사하는 곳(EvidenceStore.dangling)이 같은 파일에 있어야 한다.
# 대신 이 모듈은 룰을 모른다 - rules.py 를 import 하지 않고 rule_id 를 검증 없는
# 문자열로 받는다. F-1 이 무슨 계산인지, 충돌이 어느 유형인지는 infer 가 정한다.
_RCEPT_NO_LENGTH = 14


def derived(
    scope: str,
    rule_id: str,
    *,
    label: str,
    formula: str,
    result: str,
    based_on: Sequence[str],
    variant: str | None = None,
) -> Evidence:
    """F 블록 파생 근거.

    scope 는 계산이 닫히는 범위다. 한 보고서 안에서 끝나는 계산(F-1 우선주 비중)은
    rcept_no, 3개년을 걸치는 계산(F-3 손익 전환)은 corp_code 를 쓴다.
    variant 는 같은 룰이 대상마다 여러 번 나올 때의 꼬리다(revenue:2025). 해시를
    쓰지 않는 이유는 토글을 열어 놓고 디버깅할 수 있어야 하기 때문이다.

    raw_content(= result)에는 환산 전과 후를 모두 담아야 한다. 후검증이 "환산값은 F
    파생 근거에만 있을 수 있다" 를 강제하려면 그 숫자가 실제로 어떤 조각의 원문에
    들어 있어야 하고, 그 유일한 자리가 여기다.
    """
    if not based_on:
        raise ValueError(
            f"파생 근거 {rule_id} 에 based_on 이 없다. 파생은 정의상 원본을 가리켜야 "
            "하고, 그러지 않으면 토글이 원문에 닿지 못한다."
        )

    tail = rule_id if variant is None else f"{rule_id}:{variant}"
    locator: Locator = (
        {"kind": NS_DERIVED, "rcept_no": scope}
        if len(scope) == _RCEPT_NO_LENGTH
        else {"kind": NS_DERIVED, "corp_code": scope}
    )

    return _evidence(
        make_id(NS_DERIVED, scope, tail),
        "derived",
        label,
        result,
        locator,
        {
            "name": DERIVED_SOURCE_NAME,
            "as_of": None,
            "as_of_kind": None,
            "document_url": None,
            "rcept_no": None,
        },
        based_on=list(based_on),
        formula=formula,
        rule_id=rule_id,
    )


def conflict_side(
    label: str,
    value: str,
    *,
    based_on: str,
    as_of: str | None = None,
    as_of_kind: str | None = None,
) -> ConflictSide:
    """충돌한 두 값 중 한쪽. infer 가 dict 를 손으로 짜지 않게 여기서 만든다."""
    return {
        "label": label,
        "value": value,
        "as_of": as_of,
        "as_of_kind": as_of_kind,
        "based_on": based_on,
    }


def conflict(
    corp_code: str,
    field: str,
    *,
    label: str,
    kind: str,
    resolution: str,
    sides: Sequence[ConflictSide],
) -> Evidence:
    """충돌 자체를 근거로 승격시킨다.

    그래야 토글에서 양쪽을 다 볼 수 있다. 채택하지 않은 쪽도 sides 에 남긴다 -
    무엇을 보고 무엇을 버렸는지가 근거다.
    """
    if len(sides) < 2:
        raise ValueError(f"충돌 근거 {field} 에는 양쪽이 다 있어야 한다.")

    lines = []
    for side in sides:
        stamp = ""
        if side.get("as_of"):
            kinds = side.get("as_of_kind")
            stamp = f" ({kinds} {side['as_of']})" if kinds else f" ({side['as_of']})"
        lines.append(f"{side['label']}{stamp}: {side['value']}")

    return _evidence(
        make_id(NS_CONFLICT, corp_code, field),
        "conflict",
        label,
        "\n".join(lines),
        {"kind": NS_CONFLICT, "corp_code": corp_code, "field": field},
        {
            "name": CONFLICT_SOURCE_NAME,
            "as_of": None,
            "as_of_kind": None,
            "document_url": None,
            "rcept_no": None,
        },
        based_on=[side["based_on"] for side in sides],
        conflict_kind=kind,
        resolution=resolution,
        sides=list(sides),
    )


# ---------------------------------------------------------------------------
# [6] 레지스트리
# ---------------------------------------------------------------------------
class EvidenceStore:
    """참조된 조각만 모으는 장부.

    같은 조각을 여러 항목이 참조하는 것이 기본이다 - A-1 도 A-4 도 대표자명을 본다.
    그래서 등록은 멱등이어야 하고, add 는 언제나 ID 를 돌려준다.

    같은 ID 에 다른 내용이 들어오면 접미사를 붙이지 않는다. 그러면 등록 순서에 따라
    ID 가 달라져 결정성 요구를 정면으로 위반한다. 먼저 등록된 것을 남기고 경고와
    collisions 로 드러낸다. strict 면 즉시 실패한다 - 테스트는 strict 로 돌려서
    라벨 폴백 충돌 같은 것을 조기에 잡는다.
    """

    _REQUIRED = ("type", "label", "raw_content", "locator", "source")

    def __init__(self, *, strict: bool = False) -> None:
        self._items: dict[str, Evidence] = {}
        self.collisions: list[tuple[str, Evidence, Evidence]] = []
        self.strict = strict

    def add(self, evidence: Evidence) -> str:
        evidence_id = validate_id(evidence.get("evidence_id", ""))

        for key in self._REQUIRED:
            if key not in evidence:
                raise ValueError(f"근거 {evidence_id} 에 {key} 가 없다")

        existing = self._items.get(evidence_id)

        if existing is None:
            self._items[evidence_id] = evidence
            return evidence_id

        if existing != evidence:
            if self.strict:
                raise ValueError(
                    f"같은 ID 에 다른 내용이 들어왔다: {evidence_id}\n"
                    f"  기존: {existing['raw_content'][:60]!r}\n"
                    f"  신규: {evidence['raw_content'][:60]!r}"
                )

            logger.warning(
                "근거 ID 충돌 %s - 먼저 등록된 것을 유지한다. 기존=%r 신규=%r",
                evidence_id,
                existing["raw_content"][:60],
                evidence["raw_content"][:60],
            )
            self.collisions.append((evidence_id, existing, evidence))

        return evidence_id

    def add_all(self, items: Iterable[Evidence]) -> list[str]:
        return [self.add(item) for item in items]

    def get(self, evidence_id: str) -> Evidence | None:
        return self._items.get(evidence_id)

    def ids(self) -> list[str]:
        return list(self._items)

    def dump(self) -> list[Evidence]:
        """등록된 조각만, 등록 순서대로."""
        return list(self._items.values())

    def dangling(self) -> list[str]:
        """based_on 이 가리키는데 장부에 없는 ID.

        비어 있지 않으면 토글이 중간에서 끊긴다 - 파생·충돌은 종착점이 아니다.
        """
        missing: list[str] = []

        for evidence in self._items.values():
            for ref in evidence.get("based_on") or []:
                if ref not in self._items and ref not in missing:
                    missing.append(ref)

        return missing

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, evidence_id: object) -> bool:
        return evidence_id in self._items
