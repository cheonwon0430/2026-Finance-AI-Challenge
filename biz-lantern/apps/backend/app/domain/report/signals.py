"""이상징후의 골격. 신호 정의표·임계값·조사 항목 이름이 여기 있다.

탐지 로직은 detect.py 에, 조사 실행은 investigate.py 에 있다. 이 파일은 그 둘이 딛고
설 규칙만 갖는다 - rules.py 가 infer.py 에 대해 갖는 관계와 같다.

    [1] 조사 항목  TASK_* 이름과 kind
    [2] 임계값     THRESHOLD_*
    [3] 자료형     Signal · InvestigationTask
    [4] 정의표     SignalDefinition · SIGNALS
    [5] 팩토리     signal() · task()
    [6] 표기       won() · eok() · pct() · share()

판정(Finding)과 신호(Signal)는 왜 다른 자료형인가

    Finding.verdict 는 "그 데이터를 확인했는가" 를 말한다. CONFIRMED 는 값을 확보했다는
    뜻이지 그 값이 좋다 나쁘다가 아니다. B-2 가 CONFIRMED 라는 것은 부채총계를 읽었다는
    뜻일 뿐이다.

    Signal 은 "확인한 데이터에서 추가 조사가 필요한 패턴이 나왔는가" 를 말한다. 부채를
    읽은 것(Finding)과 부채가 43.7% 늘어난 것(Signal)은 다른 사건이고, 둘을 한 자료형에
    담으면 "확인하지 못했다" 와 "확인했는데 이상하다" 가 같은 칸에서 겨룬다.

    그래서 Signal 에는 verdict 가 없다. 점수·등급·severity 도 없다 - 무엇이 더 위험한지
    정하는 것은 이 시스템의 일이 아니다. 우리는 무엇을 더 봐야 하는지만 정한다.

임계값을 왜 한 곳에 모으는가

    실측으로 조정해야 하는 숫자이고, 조정 이력이 한 파일에 남아야 한다. 판정 함수마다
    흩어 놓으면 "30% 는 어디서 나온 숫자인가" 에 아무도 답하지 못한다.
"""

from dataclasses import dataclass
from typing import Any, TypedDict

from app.domain.report import evidence

# ---------------------------------------------------------------------------
# [1] 조사 항목
# ---------------------------------------------------------------------------
# task_id 는 "kind:target" 이다. kind 는 investigate 의 resolver 를 고르고 target 은
# 그 resolver 에 넘어가는 인자다.
#
# 문자열을 그대로 쓰지 않고 상수로 두는 이유: 정의표의 오타가 조용한 누락이 된다.
# 존재하지 않는 task_id 를 적으면 그 조사는 큐에 들어가고 아무 resolver 도 받지 못해
# NOT_ATTEMPTED 로 남는데, 그러면 "조사했는데 자료가 없었다(GAP)" 와 구분되지 않는다.
KIND_ACCOUNT = "account"
KIND_NOTE = "note"
KIND_SUMMARY = "summary"
KIND_SHAREHOLDER = "shareholder"
KIND_DISCLOSURE = "disclosure"
KIND_NEWS = "news"

# 조사 순서의 뼈대. 같은 문서 안에서 즉시 닫히는 것이 먼저다.
# 계정은 값이 바로 나오고, 주석은 원문을 읽어야 하고, 뉴스는 공시가 아니라 정황이다.
KIND_ORDER: tuple[str, ...] = (
    KIND_ACCOUNT,
    KIND_NOTE,
    KIND_SUMMARY,
    KIND_SHAREHOLDER,
    KIND_DISCLOSURE,
    KIND_NEWS,
)

# --- 계정 조사 ---
TASK_BORROWINGS_ACCOUNT = "account:borrowings"
TASK_CAPITAL_STOCK = "account:capital_stock"
TASK_PREFERRED_CAPITAL = "account:preferred_capital"
TASK_EQUITY_SERIES = "account:equity_series"
TASK_EQUITY_VS_CAPITAL = "account:equity_vs_capital"
TASK_FINANCING_CF = "account:financing_cash_flow"
TASK_INVESTING_CF = "account:investing_cash_flow"
TASK_RECEIVABLES = "account:receivables"
TASK_REVENUE_SERIES = "account:revenue_series"
TASK_OPERATING_INCOME_SERIES = "account:operating_income_series"
TASK_IDENTITY_CHECK = "account:identity_check"

# --- 주석 조사 --- (target 은 notes.TOPICS 의 키여야 한다)
TASK_NOTE_BORROWINGS = "note:borrowings"
TASK_NOTE_CONVERTIBLE_BOND = "note:convertible_bond"
TASK_NOTE_CAPITAL = "note:capital"
TASK_NOTE_GOING_CONCERN = "note:going_concern"
TASK_NOTE_DEFICIT = "note:deficit"
TASK_NOTE_RELATED_PARTY = "note:related_party"
TASK_NOTE_CONTINGENCY = "note:contingency"
TASK_NOTE_OVERVIEW = "note:overview"
TASK_NOTE_LIQUIDITY = "note:liquidity"
TASK_NOTE_RECEIVABLE = "note:receivable"

# --- 표지·주주·공시·뉴스 ---
TASK_SUMMARY_OPINION = "summary:opinion"
TASK_SUMMARY_AUDITOR = "summary:auditor"
TASK_SHAREHOLDER_TABLE = "shareholder:table"
TASK_DISCLOSURE_CORRECTED = "disclosure:corrected"
TASK_NEWS_RECENT = "news:recent"

# 조사 항목의 사람이 읽을 이름. investigate 가 result 를 만들 때 쓴다.
TASK_LABELS: dict[str, str] = {
    TASK_BORROWINGS_ACCOUNT: "차입금 계정 (단기·장기)",
    TASK_CAPITAL_STOCK: "자본금 계정",
    TASK_PREFERRED_CAPITAL: "우선주·보통주 자본금 계정",
    TASK_EQUITY_SERIES: "자본총계 추이",
    TASK_EQUITY_VS_CAPITAL: "자본총계 대 자본금 (잠식 여부)",
    TASK_FINANCING_CF: "재무활동현금흐름 추이",
    TASK_INVESTING_CF: "투자활동현금흐름 추이",
    TASK_RECEIVABLES: "매출채권·미수금 계정",
    TASK_REVENUE_SERIES: "매출액 추이",
    TASK_OPERATING_INCOME_SERIES: "영업이익 추이",
    TASK_IDENTITY_CHECK: "자산 = 부채 + 자본 항등식",
    TASK_NOTE_BORROWINGS: "차입금 주석",
    TASK_NOTE_CONVERTIBLE_BOND: "전환사채·전환우선주 주석",
    TASK_NOTE_CAPITAL: "자본 주석",
    TASK_NOTE_GOING_CONCERN: "계속기업 불확실성 주석",
    TASK_NOTE_DEFICIT: "결손금처리계산서 주석",
    TASK_NOTE_RELATED_PARTY: "특수관계자 거래 주석",
    TASK_NOTE_CONTINGENCY: "우발채무·담보·지급보증 주석",
    TASK_NOTE_OVERVIEW: "회사의 개요 주석",
    TASK_NOTE_LIQUIDITY: "금융부채 유동성·만기 주석",
    TASK_NOTE_RECEIVABLE: "매출채권·미수금 주석",
    TASK_SUMMARY_OPINION: "감사의견",
    TASK_SUMMARY_AUDITOR: "감사인 (연도별)",
    TASK_SHAREHOLDER_TABLE: "주주현황 표",
    TASK_DISCLOSURE_CORRECTED: "정정 공시 이력",
    TASK_NEWS_RECENT: "최근 뉴스 (이미 수집된 것)",
}


# ---------------------------------------------------------------------------
# [2] 임계값
# ---------------------------------------------------------------------------
# 단일 임계값을 하드코딩하지 않는 이유, 그리고 그 대안
#
#     비율만 쓰면 작은 계정에서 터진다. 센트비 매출채권은 353,734원에서 46,240,255원
#     으로 +12,969% 인데 절대액은 4,600만원이라 아무 의미가 없다.
#
#     절대액만 쓰면 큰 회사에서 아무것도 안 뜬다. 그렇다고 절대액 하한을 고정 원화로
#     박으면 회사 규모마다 다시 정해야 한다.
#
#     그래서 비율과 규모 대비 절대액 두 관문을 함께 요구한다. 절대액 하한을 원화가
#     아니라 자산총계 대비 비율로 잡으면 회사 크기와 무관하게 돈다.
#
# 방향에 대하여: 급증만 보고 급감은 보지 않는다. 센트비 2023->2024 부채 -64.7% 는
# 차입 상환일 수도 고객 예수금 감소일 수도 있는데 우리에겐 그걸 가를 계정이 없다.
# 판단할 수 없는 것을 신호로 만들면 오탐만 남는다.
THRESHOLD_DEBT_SURGE_RATE = 0.30           # 부채총계 전년 대비 증가율
THRESHOLD_DEBT_SURGE_OF_ASSETS = 0.05      # 증감액 / 당해 자산총계

THRESHOLD_FINANCING_OF_ASSETS = 0.10       # 재무활동CF 증가액 / 당해 자산총계

THRESHOLD_LOSS_STREAK = 2                  # 영업손실 연속 연수. 2년이면 추세다

THRESHOLD_PREFERRED_OF_CAPITAL = 0.30      # 우선주자본금 / 자본금

# 재작성 판정의 하한. 반올림·표기 차이를 걸러낸다. 1% 미만 차이를 재작성이라 부르면
# 단위 절사 하나로 신호가 뜬다.
THRESHOLD_RESTATEMENT_RATE = 0.01

# 억원 환산. infer.EOK 과 같은 값이지만 import 방향(detect -> infer)을 만들지 않으려고
# 여기서 다시 정의한다. 두 곳이 갈라질 위험보다 순환 import 가 더 나쁘다.
EOK = 100_000_000


# ---------------------------------------------------------------------------
# [3] 자료형
# ---------------------------------------------------------------------------
STATUS_RESOLVED = "RESOLVED"            # 조사했고 자료를 찾았다
STATUS_GAP = "GAP"                      # 조사했는데 자료가 없었다
STATUS_NOT_ATTEMPTED = "NOT_ATTEMPTED"  # 조사 자체를 시도하지 못했다


class Signal(TypedDict):
    """이상징후 하나.

    trigger 는 임계값 판정을 숫자까지 적은 한 문장이고, 이 문자열이 그대로
    evidence.derived(result=...) 로도 등록된다. 그래야 LLM 이 "43.7%" 를 인용할 때
    후검증이 그 숫자를 어떤 조각의 원문에서 찾아낼 수 있다 - 그러지 않으면 문장이
    통째로 폐기된다.

    investigations 는 task_id 참조다. 조사 결과 본체는 큐에 한 번만 있고 여러 신호가
    같은 것을 가리킨다.
    """

    signal_id: str
    label: str
    trigger: str
    facts: list[str]
    evidence_ids: list[str]
    investigations: list[str]
    source: evidence.Source
    warnings: list[str]


class InvestigationTask(TypedDict):
    """조사 항목 하나와 그 결과.

    requested_by 가 이 구조의 핵심이다. 어느 신호들이 이 자료를 함께 요구했는지가
    남아야 조사 우선순위를 정할 수 있고, 화면에서 "왜 이걸 봤는가" 를 말할 수 있다.
    """

    task_id: str
    kind: str
    target: str
    label: str
    requested_by: list[str]
    status: str
    result: str | None
    evidence_ids: list[str]


@dataclass(frozen=True)
class SignalDefinition:
    """신호 하나의 고정 정보. 탐지 결과가 아니라 정의다."""

    signal_id: str
    label: str
    investigations: tuple[str, ...]


# ---------------------------------------------------------------------------
# [4] 정의표
# ---------------------------------------------------------------------------
# 신호를 늘리는 곳은 여기 한 곳이다. 정의를 넣고 detect._DETECTORS 에 탐지 함수를
# 등록하면 detect.run() 이 알아서 돈다 - rules.ITEMS 와 infer._RULES 의 관계와 같다.
#
# investigations 의 등재 순서가 곧 그 신호 안에서의 조사 우선순위다.
SIGNALS: tuple[SignalDefinition, ...] = (
    SignalDefinition(
        "OPERATING_LOSS_CONTINUED",
        "영업손실 지속",
        (
            TASK_EQUITY_VS_CAPITAL,
            TASK_FINANCING_CF,
            TASK_NOTE_GOING_CONCERN,
            TASK_NOTE_DEFICIT,
            TASK_NOTE_BORROWINGS,
            TASK_NEWS_RECENT,
        ),
    ),
    SignalDefinition(
        "PROFIT_SIGN_TURNED",
        "손익 전환",
        (
            TASK_REVENUE_SERIES,
            TASK_OPERATING_INCOME_SERIES,
            TASK_NOTE_OVERVIEW,
            TASK_NOTE_RELATED_PARTY,
            TASK_NEWS_RECENT,
        ),
    ),
    SignalDefinition(
        "SALES_UP_CFO_DOWN",
        "매출 증가와 영업현금흐름 악화",
        (
            TASK_RECEIVABLES,
            TASK_INVESTING_CF,
            TASK_NOTE_RECEIVABLE,
            TASK_NOTE_RELATED_PARTY,
            TASK_NOTE_CONTINGENCY,
            TASK_NEWS_RECENT,
        ),
    ),
    SignalDefinition(
        "DEBT_SURGE",
        "부채 급증",
        (
            TASK_BORROWINGS_ACCOUNT,
            TASK_CAPITAL_STOCK,
            TASK_FINANCING_CF,
            TASK_NOTE_BORROWINGS,
            TASK_NOTE_CONVERTIBLE_BOND,
            TASK_NOTE_RELATED_PARTY,
            TASK_NOTE_LIQUIDITY,
            TASK_DISCLOSURE_CORRECTED,
            TASK_NEWS_RECENT,
        ),
    ),
    SignalDefinition(
        "FINANCING_CF_SURGE",
        "재무활동현금흐름 급증",
        (
            TASK_BORROWINGS_ACCOUNT,
            TASK_CAPITAL_STOCK,
            TASK_PREFERRED_CAPITAL,
            TASK_EQUITY_SERIES,
            TASK_NOTE_BORROWINGS,
            TASK_NOTE_CAPITAL,
            TASK_NOTE_CONVERTIBLE_BOND,
            TASK_NEWS_RECENT,
        ),
    ),
    SignalDefinition(
        "CAPITAL_IMPAIRMENT",
        "자본잠식",
        (
            TASK_EQUITY_SERIES,
            TASK_CAPITAL_STOCK,
            TASK_FINANCING_CF,
            TASK_NOTE_GOING_CONCERN,
            TASK_NOTE_DEFICIT,
            TASK_SUMMARY_OPINION,
        ),
    ),
    SignalDefinition(
        "CB_FOUND",
        "투자성 증권 발견",
        (
            TASK_PREFERRED_CAPITAL,
            TASK_FINANCING_CF,
            TASK_NOTE_CONVERTIBLE_BOND,
            TASK_NOTE_CAPITAL,
            TASK_SHAREHOLDER_TABLE,
            TASK_NEWS_RECENT,
        ),
    ),
    SignalDefinition(
        "RESTATEMENT_DETECTED",
        "전기 수치 재작성",
        (
            TASK_IDENTITY_CHECK,
            TASK_DISCLOSURE_CORRECTED,
            TASK_SUMMARY_AUDITOR,
            TASK_SUMMARY_OPINION,
            TASK_NOTE_OVERVIEW,
        ),
    ),
    SignalDefinition(
        "PREFERRED_TERMS_UNKNOWN",
        "우선주 비중이 큰데 조건을 확인할 수 없음",
        (
            TASK_PREFERRED_CAPITAL,
            TASK_FINANCING_CF,
            TASK_NOTE_CAPITAL,
            TASK_NOTE_CONVERTIBLE_BOND,
            TASK_SHAREHOLDER_TABLE,
            TASK_NEWS_RECENT,
        ),
    ),
)

_BY_ID = {item.signal_id: item for item in SIGNALS}


def definition(signal_id: str) -> SignalDefinition:
    """신호 정의를 꺼낸다. 없는 id 는 오타이므로 실패시킨다."""
    try:
        return _BY_ID[signal_id]
    except KeyError:
        raise KeyError(f"정의되지 않은 신호: {signal_id}") from None


# ---------------------------------------------------------------------------
# [5] 팩토리
# ---------------------------------------------------------------------------
def signal(
    item: SignalDefinition,
    *,
    trigger: str,
    facts: list[str],
    evidence_ids: list[str],
    source: evidence.Source,
    warnings: list[str] | None = None,
) -> Signal:
    """신호 하나. 정의에서 id·label 을, 정의표에서 조사 목록을 자동으로 옮긴다.

    evidence_ids 를 비워 둘 수 없게 막는다. 근거 없는 이상징후는 그냥 주장이고,
    화면의 토글이 원문에 닿지 못한다 - evidence.derived() 가 based_on 을 강제하는 것과
    같은 이유다.
    """
    if not evidence_ids:
        raise ValueError(
            f"신호 {item.signal_id} 에 근거가 없다. 근거 없는 이상징후는 주장이지 "
            "발견이 아니다."
        )

    return {
        "signal_id": item.signal_id,
        "label": item.label,
        "trigger": trigger,
        "facts": list(facts),
        "evidence_ids": list(evidence_ids),
        "investigations": list(item.investigations),
        "source": source,
        "warnings": list(warnings or []),
    }


def task(task_id: str, requested_by: list[str]) -> InvestigationTask:
    """조사 항목 하나. 아직 실행하지 않은 상태로 만든다."""
    kind, _, target = task_id.partition(":")
    if not kind or not target:
        raise ValueError(f"조사 항목 id 형식이 아니다 (kind:target 이어야 한다): {task_id}")

    if kind not in KIND_ORDER:
        raise ValueError(f"알 수 없는 조사 종류: {kind} ({task_id})")

    return {
        "task_id": task_id,
        "kind": kind,
        "target": target,
        "label": TASK_LABELS.get(task_id, task_id),
        "requested_by": list(requested_by),
        "status": STATUS_NOT_ATTEMPTED,
        "result": None,
        "evidence_ids": [],
    }


# ---------------------------------------------------------------------------
# [6] 표기
# ---------------------------------------------------------------------------
# 표기를 한 곳에 모으는 이유: 이 문자열들이 그대로 derived 조각의 원문이 되고, 후검증은
# 그 원문에 있는 숫자만 LLM 에게 허용한다. 표기가 함수마다 갈리면 같은 값이 두 표기로
# 남아 어느 쪽도 검증을 통과하지 못한다.
def won(value: float) -> str:
    return f"{int(value):,}원"


def eok(value: float) -> str:
    """억원 환산. 이 문자열이 원문에 있어야 LLM 이 억원을 쓸 수 있다(F-6 과 같은 규율)."""
    return f"{value / EOK:,.1f}억원"


def pct(rate: float) -> str:
    """증감률. 부호를 붙여 방향을 명시한다."""
    return f"{rate * 100:+,.1f}%"


def share(rate: float) -> str:
    """비중. 방향이 없으므로 부호를 붙이지 않는다."""
    return f"{rate * 100:,.1f}%"


def year_facts(
    by_year: dict[int, dict[str, Any]], years: list[int], label: str
) -> list[str]:
    """연도별 값을 사람이 읽을 줄로. facts 에 그대로 들어간다."""
    return [
        f"{year}년 {label} {won(by_year[year]['value'])}"
        for year in years
        if year in by_year and by_year[year]["value"] is not None
    ]
