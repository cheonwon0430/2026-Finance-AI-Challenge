"""정리된 감사보고서(document_clean 결과)에서 재무제표를 꺼낸다.

document_clean 은 표를 격자와 계정 목록까지 만들어 주지만 "이 표가 무엇인지" 는
말해주지 않는다. class="FINANCE" 라는 것만 알 뿐이라 58개 계정이 재무상태표의
것인지 현금흐름표의 것인지 소비하는 쪽이 알 수 없다. 여기서 그 꼬리표를 붙인다.

document_clean.py 는 건드리지 않는다. 그 결과 dict 를 받아 읽기만 한다.

계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 재무제표 종류    섹션 제목 -> 종류
    [2] 계정 코드        ACODE 앞 9자리 -> 논리 이름
    [3] 기(期) 판별      헤더의 (당)/(전)
    [4] 값 꺼내기        부호 보정을 포함한다
    [5] 분류와 조회
    [6] 요약 폴백        EXTRACTION (IFRS·의견거절용)

왜 라벨이 아니라 ACODE 인가 (2026-09-03 실측, 보유 문서 12건)

    같은 계정의 라벨이 회사·연도마다 이만큼 갈린다.

        매출      I.매출액 / I.영업수익 / Ⅰ.매출액 / Ⅰ.영업수익 / 영업수익
        영업이익   III.영업손실 / III.영업이익 / V.영업이익(손실) / Ⅴ.영업이익(손실)
        당기순익   VIII.당기순손실 / VIII.당기순이익 / X.당기순이익(손실)

    로마숫자가 ASCII 'I' 와 유니코드 'Ⅰ' 로 섞여 있고, 흑자냐 적자냐에 따라
    이름 자체가 바뀌며, 주석 번호가 붙기도 한다(Ⅳ.판매비와관리비(주석19)).
    라벨 매칭으로는 어느 규칙을 세워도 샌다.

    반면 ACODE 앞 9자리는 12건 전부에서 위 라벨들을 하나로 묶었다. 예외 0건이다.
    document_clean.py 가 "ACODE 는 DART 표준 계정과목 코드라 회사가 달라도 같다"
    고 적어둔 것이 실제로 그렇다.

부호: 손실 계정은 양수로 적혀 온다 (같은 실측, 계정 24건 예외 0건)

    ACODE 뒤 5자리가 이익/손실을 인코딩한다.

        ...10000  이익 계정.  적자면 (1,234) 또는 △ 로 음수가 이미 표기된다
        ...20000  손실 계정.  값이 항상 양수로 적혀 있다 -> 우리가 뒤집어야 한다

            (주)센트비    III.영업손실     12500000020000    1,196,195,962  -> -1,196,195,962
            (주)핀샷      III.영업이익     12500000010000    1,780,389,159  ->  그대로
            (주)이롬넷    V.영업이익(손실) 12500000010000  (2,060,302,045)  ->  그대로(이미 음수)

    라벨로 판정하면 안 된다. 'V.영업이익(손실)' 처럼 이익과 손실이 한 라벨에
    같이 들어 있어서 "손실이 있으면 뒤집는다" 류의 규칙이 곧바로 깨진다.
"""

import re
from typing import Any

from app.domain.company.parser.document_clean import normalize_parse_key

# ---------------------------------------------------------------------------
# [1] 재무제표 종류 - 섹션 제목으로 가른다
# ---------------------------------------------------------------------------
# 제목은 '재 무 상 태 표' 처럼 자간이 벌어져 오므로 normalize_parse_key 로 공백을
# 지운 뒤 비교한다.
BALANCE_SHEET = "balance_sheet"
INCOME_STATEMENT = "income_statement"
CASH_FLOW = "cash_flow"
EQUITY_CHANGE = "equity_change"

# 앞 4개는 보유 문서 12건 전부에서 실측했다. 뒤 2개는 아직 만난 적 없는 표기라
# 방어적으로만 넣어둔다 - 걸리면 잡히고, 안 걸려도 잃을 것이 없다.
_TITLES: dict[str, str] = {
    "재무상태표": BALANCE_SHEET,
    "손익계산서": INCOME_STATEMENT,
    "현금흐름표": CASH_FLOW,
    "자본변동표": EQUITY_CHANGE,
    "대차대조표": BALANCE_SHEET,         # 미실측(구 명칭)
    "포괄손익계산서": INCOME_STATEMENT,  # 미실측
}

FINANCE_CLASS = "FINANCE"


# ---------------------------------------------------------------------------
# [2] 계정 코드 - ACODE 앞 9자리
# ---------------------------------------------------------------------------
# 실측으로 확인한 것만 넣는다. 표준코드가 없는 회사 고유 계정은 99999999999999 로
# 오므로 여기에 걸리지 않는다.
CURRENT_ASSETS = "112000000"
NONCURRENT_ASSETS = "114000000"
TOTAL_ASSETS = "115000000"
CURRENT_LIABILITIES = "116000000"
NONCURRENT_LIABILITIES = "117000000"
TOTAL_LIABILITIES = "118000000"
CAPITAL_STOCK = "118100000"
TOTAL_EQUITY = "118900000"

REVENUE = "121000000"            # 매출액 / 영업수익
COST_OF_SALES = "122000000"
GROSS_PROFIT = "123000000"
OPERATING_EXPENSE = "124000000"  # 판매비와관리비 / 영업비용
OPERATING_INCOME = "125000000"   # 영업이익 / 영업손실
NON_OPERATING_INCOME = "125100000"
NON_OPERATING_EXPENSE = "126000000"
PRETAX_INCOME = "128000000"
INCOME_TAX = "128100000"
NET_INCOME = "129000000"         # 당기순이익 / 당기순손실

OPERATING_CASH_FLOW = "161000000"
INVESTING_CASH_FLOW = "162000000"
FINANCING_CASH_FLOW = "163000000"
NET_CASH_CHANGE = "164000000"
CASH_END = "166000000"

# 기초현금(165000000)은 뺐다. 실측에서 한 문서가 같은 코드에
# '외화표시현금의환율변동효과' 를 달고 있어 의미가 하나로 고정되지 않는다.
# 기말현금(166000000)은 12건 전부 일관되므로 남긴다.

# 보고서가 실제로 쓰는 계정. 논리 이름 -> (재무제표 종류, ACODE 앞 9자리)
REPORTED_ACCOUNTS: dict[str, tuple[str, str]] = {
    "revenue": (INCOME_STATEMENT, REVENUE),
    "operating_income": (INCOME_STATEMENT, OPERATING_INCOME),
    "net_income": (INCOME_STATEMENT, NET_INCOME),
    "total_assets": (BALANCE_SHEET, TOTAL_ASSETS),
    "total_liabilities": (BALANCE_SHEET, TOTAL_LIABILITIES),
    "total_equity": (BALANCE_SHEET, TOTAL_EQUITY),
    "capital_stock": (BALANCE_SHEET, CAPITAL_STOCK),
    "operating_cash_flow": (CASH_FLOW, OPERATING_CASH_FLOW),
    "investing_cash_flow": (CASH_FLOW, INVESTING_CASH_FLOW),
    "financing_cash_flow": (CASH_FLOW, FINANCING_CASH_FLOW),
}

_LOSS_SUFFIX = "20000"  # ACODE 뒤 5자리. 손실 계정이라 값이 양수로 적혀 온다


# ACODE 가 늘 붙어 있지는 않다 (2026-09-03 실측)
#
#     (주)트래블월렛 현금흐름표의 level 0 '영업활동으로인한현금흐름' 은 ACODE 가
#     빈 문자열이다. 같은 문서의 재무상태표·손익계산서에는 코드가 정상적으로 붙어
#     있고 현금흐름표 하위 계정에도 붙어 있는데 대분류만 비어 있다.
#
# 그래서 코드로 못 찾은 계정은 라벨로 한 번 더 찾는다. 라벨에는 번호 접두(Ⅰ. / I.)와
# 주석 참조((주석15))가 붙으므로 그 둘을 걷어낸 뒤 비교한다.
_LABEL_FALLBACK: dict[str, tuple[str, ...]] = {
    OPERATING_CASH_FLOW: ("영업활동으로인한현금흐름", "영업활동현금흐름"),
    INVESTING_CASH_FLOW: ("투자활동으로인한현금흐름", "투자활동현금흐름"),
    FINANCING_CASH_FLOW: ("재무활동으로인한현금흐름", "재무활동현금흐름"),
    TOTAL_ASSETS: ("자산총계",),
    TOTAL_LIABILITIES: ("부채총계",),
    TOTAL_EQUITY: ("자본총계",),
}

# 번호 접두는 반드시 구분자(. 또는 ))를 요구한다. 그러지 않으면 '1분기매출' 같은
# 라벨의 앞글자까지 먹는다.
_NUMBERING_PREFIX = re.compile(r"^[IVXivxⅠ-Ⅻ0-9]+[.)]")
_NOTE_REFERENCE = re.compile(r"\(주석[^)]*\)")


def label_key(label: str) -> str:
    """계정 라벨 -> 매칭용 키. 번호 접두와 주석 참조를 걷어낸다.

        'Ⅰ. 영업활동으로 인한 현금흐름(주석15)' -> '영업활동으로인한현금흐름'
    """
    key = normalize_parse_key(label or "")
    key = _NOTE_REFERENCE.sub("", key)

    return _NUMBERING_PREFIX.sub("", key).strip()


# ---------------------------------------------------------------------------
# [3] 기(期) 판별
# ---------------------------------------------------------------------------
# 헤더가 '제 11(당) 기' / '제10(전)기' 처럼 자간이 제각각이라 공백을 지우고 본다.
CURRENT_PERIOD = "current"
PRIOR_PERIOD = "prior"


def period_of(header: str | None) -> str | None:
    """열 헤더 -> 당기/전기. 판단할 수 없으면 None."""
    if not header:
        return None

    key = normalize_parse_key(header)

    if "(당)" in key:
        return CURRENT_PERIOD
    if "(전)" in key:
        return PRIOR_PERIOD

    return None


# ---------------------------------------------------------------------------
# [4] 값 꺼내기
# ---------------------------------------------------------------------------
def signed_value(code: str, value: float | None) -> float | None:
    """손실 계정의 부호를 바로잡는다. raw 는 건드리지 않는다.

    document_clean.parse_amount 가 (1,234) 와 △ 는 이미 음수로 만들어 준다.
    여기서 보는 건 그것과 다른 문제다 - 손실 계정인데 부호 표시 없이 양수로만
    적혀 오는 경우다.
    """
    if value is None:
        return None

    if (code or "")[9:] == _LOSS_SUFFIX and value > 0:
        return -value

    return value


def account_values(account: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """계정 하나 -> {당기: {...}, 전기: {...}}.

    raw 를 함께 넘긴다. 보고서가 인용할 때 쓰는 건 가공값이 아니라 원문이고,
    나중에 LLM 이 쓴 숫자를 검증할 기준도 raw 다.
    """
    found: dict[str, dict[str, Any]] = {}

    for value in account["values"]:
        period = period_of(value.get("header"))

        # 같은 기(期)에 두 칸이 잡히면 먼저 온 쪽을 남긴다. level 0 계정은
        # 바깥 칸에만 값이 있어 실제로는 기당 한 칸씩만 채워진다.
        if period is None or period in found:
            continue

        found[period] = {
            "raw": value["raw"],
            "value": signed_value(account.get("code") or "", value.get("value")),
            "header": value.get("header"),
        }

    return found


# ---------------------------------------------------------------------------
# [5] 재무제표 분류와 조회
# ---------------------------------------------------------------------------
def classify_statements(clean: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """정리 결과 -> {재무제표 종류: 표 블록}.

    class="FINANCE" 인 표만 본다. 표지의 EXTRACTION 표와 레이아웃용 NORMAL 표가
    같은 섹션에 섞여 있기 때문이다
    (실측: 문서당 FINANCE 4 / EXTRACTION 11 / NORMAL 49~111).
    """
    statements: dict[str, dict[str, Any]] = {}

    for section in clean.get("sections") or []:
        kind = _TITLES.get(normalize_parse_key(section.get("title") or ""))
        if kind is None or kind in statements:
            continue

        for block in section["blocks"]:
            if block.get("type") != "table" or block.get("class") != FINANCE_CLASS:
                continue
            if not block.get("accounts"):
                continue

            statements[kind] = block
            break

    return statements


def find_account(table: dict[str, Any], code9: str) -> dict[str, Any] | None:
    """표에서 계정을 찾는다. ACODE 를 먼저 보고, 없으면 라벨로 한 번 더 본다.

    어느 쪽이든 level 0(대분류)을 우선한다. 총계를 찾는데 하위 세부 항목이 걸리면
    곤란하기 때문이다.
    """
    matched = [a for a in table["accounts"] if (a.get("code") or "")[:9] == code9]

    if not matched:
        labels = _LABEL_FALLBACK.get(code9)
        if labels:
            matched = [a for a in table["accounts"] if label_key(a["label"]) in labels]

    if not matched:
        return None

    return next((a for a in matched if a.get("level") == 0), matched[0])


def extract_financials(clean: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """정리 결과 -> {논리 계정명: {label, code, statement, periods}}.

    찾지 못한 계정은 키 자체를 만들지 않는다. 빈 dict 를 넣으면 "값이 0" 인지
    "못 찾았다" 인지 소비하는 쪽에서 구분할 수 없다.
    """
    statements = classify_statements(clean)
    found: dict[str, dict[str, Any]] = {}

    for name, (kind, code9) in REPORTED_ACCOUNTS.items():
        table = statements.get(kind)
        if table is None:
            continue

        account = find_account(table, code9)
        if account is None:
            continue

        values = account_values(account)
        if not values:
            continue

        found[name] = {
            "label": account["label"],
            "code": account["code"],
            "statement": kind,
            "periods": values,
        }

    return found


# ---------------------------------------------------------------------------
# [6] 요약 폴백 - EXTRACTION
# ---------------------------------------------------------------------------
# IFRS 채택사와 의견거절 문서는 FINANCE 표가 아예 없다(실측 8.3% + 5.0%).
# 그때도 표지 EXTRACTION 에는 총액이 남아 있어 최소한의 규모는 말할 수 있다.
IFRS_FLAG = "IFRS_YN"
OPINION_CODE = "SUPV_OPIN"

OPINION_LABELS = {
    "100000000000": "적정",
    "411000000000": "의견거절",
}
DISCLAIMER_OPINION = "411000000000"

# EXTRACTION 의 금액 단위는 백만원이다 (survey_ifrs.py 의 자산 구간 정의로 확인).
SUMMARY_UNIT_WON = 1_000_000

SUMMARY_ACCOUNTS = {
    "total_assets": "TOT_ASSETS",
    "total_liabilities": "TOT_DEBTS",
    "revenue": "TOT_SALES",
}


def audit_opinion(clean: dict[str, Any]) -> tuple[str | None, str | None]:
    """(코드, 한글 이름). 모르는 코드면 이름만 None 으로 두고 코드는 살린다.

    문자열 매칭을 쓰지 않는다. 본문에서 '적정' 같은 단어를 찾는 방식은 보유 문서
    5건 전부에서 판정에 실패했다(dump_extracted/_structure_report.md).
    """
    code = (clean.get("summary") or {}).get(OPINION_CODE)
    if not code:
        return None, None

    return code, OPINION_LABELS.get(code)


def has_finance_tables(clean: dict[str, Any]) -> bool:
    """FINANCE 표가 하나라도 있는가."""
    return bool(classify_statements(clean))


def needs_summary_fallback(clean: dict[str, Any]) -> bool:
    """FINANCE 표가 없는 것이 '정상' 인 문서인가.

    이 둘은 파싱 실패가 아니다. IFRS 채택사는 재무제표를 NORMAL 표로 넣고,
    의견거절 문서는 재무제표를 아예 첨부하지 않는다. 구분하지 않으면 정상 문서를
    EXTRACTION_FAILED 로 오판한다.
    """
    summary = clean.get("summary") or {}

    return (
        summary.get(IFRS_FLAG) == "Y"
        or summary.get(OPINION_CODE) == DISCLAIMER_OPINION
    )


def summary_financials(clean: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """EXTRACTION 총액 -> 원 단위. 백만원으로 적혀 있어 환산해 둔다."""
    summary = clean.get("summary") or {}
    found: dict[str, dict[str, Any]] = {}

    for name, code in SUMMARY_ACCOUNTS.items():
        raw = summary.get(code)
        if raw is None or raw == "":
            continue

        try:
            millions = int(str(raw).replace(",", ""))
        except ValueError:
            continue

        found[name] = {
            "raw": raw,
            "unit": "백만원",
            "value": millions * SUMMARY_UNIT_WON,
            "code": code,
            "source": "EXTRACTION",
        }

    return found
