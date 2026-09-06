"""항목을 판정한다. 게이트(G)·법적 실체(A)·재무(B)와 그 파생(F).

판정 규칙의 골격은 rules.py 에, 근거 조각은 evidence.py 에 있다. 이 파일은 수집 결과를
읽어 그 둘을 엮는다. 수집·정리 계층(api/ · parser/ · pipeline)은 읽기만 한다.

    [1] 문맥        rules.Context - 항목마다 다시 계산하지 않으려고 한 번만 만든다
    [2] 게이트      G-1 ~ G-4
    [3] 법적 실체    A-1 ~ A-4 (A-4 는 교차검증)
    [4] 재무 시계열  3개년 병합 규칙
    [5] 재무        B-1 ~ B-6
    [6] 파생        F-3 ~ F-6
    [7] 진입점      run()

조각은 참조될 때만 만든다. 판정에 실제로 쓴 근거만 EvidenceStore 에 등록하고, 그
반환 ID 를 항목의 evidence_ids 에 넣는다.

산수는 전부 여기서 한다. LLM 은 F 블록이 만든 문자열을 옮기기만 하므로 계산 오류가
구조적으로 생기지 않는다.
"""

import re
from collections.abc import Callable
from typing import Any, TypedDict

from app.domain.company.parser import notes as nt
from app.domain.company.parser import statements as st
from app.domain.report import detect, evidence, rules
from app.domain.report.rules import ItemDefinition, Verdict

# 3개년을 보여준다. 보고서 3건에서 당기·전기가 나오므로 실제로는 4개년이 모이는데,
# 가장 오래된 해는 한 문서에만 있어 대조가 불가능하므로 표시에서 뺀다.
RECENT_YEARS = 3

INCOME_ACCOUNTS = ("revenue", "operating_income", "net_income")
BALANCE_ACCOUNTS = ("total_assets", "total_liabilities", "total_equity")
CASHFLOW_ACCOUNTS = (
    "operating_cash_flow",
    "investing_cash_flow",
    "financing_cash_flow",
)

# A-1 이 확인하는 핵심 필드. 이 중 하나라도 비면 기본정보가 성립하지 않는다.
CORE_COMPANY_FIELDS = ("corp_name", "ceo_nm", "est_dt", "adres")
COMPANY_FIELDS = CORE_COMPANY_FIELDS + ("jurir_no", "bizr_no", "induty_code", "acc_mt")

EMPLOYEE_CODE = "TOT_EMPL"
REGISTRATION_CODE = "CRP_RGS_NO"

# service 가 뉴스 워크플로 결과를 이 값으로 정규화해 넘긴다. NewsState 22개 키를 그대로
# 받지 않는 이유는 판정이 워크플로 자료구조에 묶이면 안 되기 때문이다.
NEWS_ERROR = "error"


# ---------------------------------------------------------------------------
# [1] 문맥
# ---------------------------------------------------------------------------
# rules.Context 는 rules.Context 로 옮겼다. detect·investigate 가 같은 문맥을 읽어야 하는데
# 그쪽이 infer 를 import 하면 순환이 되기 때문이다. GateState·NoteContext 와 한자리다.


# ---------------------------------------------------------------------------
# [2] 게이트
# ---------------------------------------------------------------------------
def _g1(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """DART 등록. 여기서 실패하면 보고서 전체가 설 자리가 없다."""
    company = context["company"]
    source = evidence.company_source(context["as_of"])

    if not context["gate"]["registered"]:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE, source=source)

    piece = context["store"].add(
        evidence.company_field(company, "corp_code", as_of=context["as_of"])
    )

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"DART 등록 법인 (고유번호 {company['corp_code']})",
        evidence_ids=[piece],
        source=source,
    )


def _g2(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """외부감사 대상 여부.

    감사보고서가 0건인 것은 파싱 실패가 아니라 확인 결과다. 비외감 법인이면 애초에
    제출 의무가 없으므로 ABSENT 로 적는다.
    """
    gate = context["gate"]
    store = context["store"]
    corp_code = context["corp_code"]

    if not gate["audited"]:
        return rules.finding(item, Verdict.ABSENT, value=None)

    pieces = [
        store.add(evidence.disclosure_item(corp_code, evidence.disclosure_view(report)))
        for report in gate["reports"]
    ]
    years = [r.get("fiscal_year") or "?" for r in gate["reports"]]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"외부감사 대상. 감사보고서 {len(pieces)}건 ({', '.join(years)})",
        evidence_ids=pieces,
        source=evidence.disclosure_source(evidence.disclosure_view(gate["reports"][0])),
    )


def _g3(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """감사보고서 미제출신고. 감사보고서가 0건일 때만 물어본다."""
    gate = context["gate"]

    if gate["audited"]:
        return rules.finding(item, Verdict.NOT_REQUIRED)

    if not gate["non_submission"]:
        return rules.finding(item, Verdict.ABSENT)

    store = context["store"]
    pieces = [
        store.add(evidence.disclosure_item(context["corp_code"], entry))
        for entry in gate["non_submission"]
    ]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"미제출신고 {len(pieces)}건",
        evidence_ids=pieces,
        source=evidence.disclosure_source(gate["non_submission"][0]),
    )


def _g4(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """재무제표 첨부 형식.

    IFRS 채택사와 의견거절 문서는 FINANCE 표가 아예 없는 것이 정상이다. 이 판정이
    없으면 정상 문서를 EXTRACTION_FAILED 로 오판한다.
    """
    gate = context["gate"]
    latest = gate["latest"]

    if latest is None:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE)

    store = context["store"]
    pieces = [
        store.add(evidence.summary_field(latest, code))
        for code in (st.IFRS_FLAG, st.OPINION_CODE)
        if code in (latest["clean"].get("summary") or {})
    ]
    fallback = gate["summary_fallback"]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value="요약 폴백 경로 (재무제표 표가 없는 것이 정상)"
        if fallback
        else "일반 경로 (재무제표 표 첨부)",
        evidence_ids=pieces,
        source=evidence.report_source(latest),
    )


# ---------------------------------------------------------------------------
# [3] 법적 실체
# ---------------------------------------------------------------------------
def _a1(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """법인 기본정보."""
    company = context["company"]
    source = evidence.company_source(context["as_of"])

    if not context["gate"]["registered"]:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE, source=source)

    missing = [f for f in CORE_COMPANY_FIELDS if not company.get(f)]
    if missing:
        return rules.finding(
            item,
            Verdict.EXTRACTION_FAILED,
            source=source,
            warnings=[f"기업개황에 없는 필드: {', '.join(missing)}"],
        )

    store = context["store"]
    pieces = [
        store.add(evidence.company_field(company, field, as_of=context["as_of"]))
        for field in COMPANY_FIELDS
        if company.get(field)
    ]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"{company['corp_name']} · 대표 {company['ceo_nm']} · 설립 "
        f"{_dashed(company['est_dt'])}",
        evidence_ids=pieces,
        source=source,
    )


def _a2(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """사업자등록 상태.

    진위확인 불일치(valid != '01')를 폐업으로 적으면 안 된다. 그건 국세청이 우리가 준
    대표자명·개업일로 사업자를 특정하지 못했다는 뜻이지, 사업자가 없어졌다는 뜻이
    아니다. 상태를 확인하지 못한 것이므로 SOURCE_UNAVAILABLE 이다.
    """
    company = context["company"]
    nts = context["collected"].get("nts")
    source = evidence.nts_source(context["as_of"])
    bizr_no = company.get("bizr_no")

    if not bizr_no:
        return rules.finding(
            item,
            Verdict.SOURCE_UNAVAILABLE,
            source=source,
            warnings=["기업개황에 사업자등록번호가 없어 조회하지 못했다"],
        )

    if not nts:
        detail = context["collected"].get("nts_error") or "국세청 조회에 실패했다"
        return rules.finding(
            item, Verdict.SOURCE_UNAVAILABLE, source=source, warnings=[detail]
        )

    store = context["store"]
    fields = ("verified", "valid_code", "status", "status_code", "tax_type", "closed_at")
    pieces = [
        store.add(evidence.nts_field(nts, bizr_no, field, as_of=context["as_of"]))
        for field in fields
    ]

    status = nts.get("status")

    # 상태조회(/status)가 주 출처다. 진위확인 불일치는 상태를 못 받았다는 뜻이 아니라
    # 대표자·개업일로 사업자를 특정하지 못했다는 별개의 사실이므로, 판정을 막지 않고
    # 경고로만 남긴다. (국세청이 대조하는 것은 개업일자인데 우리가 주는 것은 DART
    # 설립일이라 정상 기업도 자주 어긋난다 - 실측으로 확인했다.)
    if not status:
        return rules.finding(
            item,
            Verdict.SOURCE_UNAVAILABLE,
            evidence_ids=pieces,
            source=source,
            warnings=["국세청 상태조회에서 사업자상태를 받지 못했다"],
        )

    warnings: list[str] = []
    if not nts.get("verified"):
        warnings.append(
            "국세청 진위확인(대표자·개업일 대조)은 일치하지 않는다. "
            "사업자 상태와는 별개이며 폐업을 뜻하지 않는다."
        )

    closed = nts.get("closed_at")

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"{status} (폐업일 {_dashed(closed)})" if closed else status,
        evidence_ids=pieces,
        source=source,
        warnings=warnings,
    )


def _a3(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """규모 지표. 감사보고서 표지 EXTRACTION 의 직원수."""
    latest = context["gate"]["latest"]

    if latest is None:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE)

    source = evidence.report_source(latest)
    raw = (latest["clean"].get("summary") or {}).get(EMPLOYEE_CODE)

    if not raw:
        return rules.finding(item, Verdict.ABSENT, source=source)

    piece = context["store"].add(evidence.summary_field(latest, EMPLOYEE_CODE))

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"직원수 {raw}명",
        evidence_ids=[piece],
        source=source,
    )


# A-4 교차검증 -------------------------------------------------------------
_DATE = re.compile(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")

# 시·도. 경기를 광주보다 먼저 본다 - '경기도 광주시' 가 광주광역시로 읽히면 안 된다.
_REGIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("경기", ("경기",)),
    ("서울", ("서울",)),
    ("부산", ("부산",)),
    ("대구", ("대구",)),
    ("인천", ("인천",)),
    ("대전", ("대전",)),
    ("울산", ("울산",)),
    ("세종", ("세종",)),
    ("광주", ("광주",)),
    ("강원", ("강원",)),
    ("충북", ("충청북도", "충북")),
    ("충남", ("충청남도", "충남")),
    ("전북", ("전라북도", "전북")),
    ("전남", ("전라남도", "전남")),
    ("경북", ("경상북도", "경북")),
    ("경남", ("경상남도", "경남")),
    ("제주", ("제주",)),
)


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _dashed(value: str | None) -> str | None:
    if not value or len(value) != 8 or not value.isdigit():
        return value

    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def _first_date(text: str) -> str | None:
    """본문 첫 번째 날짜 -> YYYYMMDD. 설립일 문장이 맨 앞에 온다."""
    match = _DATE.search(text or "")
    if match is None:
        return None

    year, month, day = match.groups()

    return f"{year}{int(month):02d}{int(day):02d}"


def _region_of(text: str) -> str | None:
    for canonical, aliases in _REGIONS:
        if any(alias in (text or "") for alias in aliases):
            return canonical

    return None


def _overview_conflict(
    context: rules.Context,
    field: str,
    label: str,
    dart_value: str,
    note_value: str,
    overview_id: str,
) -> str:
    """DART 값과 주석 값이 갈릴 때 충돌 조각을 만든다.

    시점 차이로 처리한다. 기업개황은 조회 시점의 현재 값이고 주석은 회계연도 말
    기준이라, 어느 쪽이 틀렸다고 말할 근거가 없다. 둘 다 기준일과 함께 보여준다.
    """
    latest = context["gate"]["latest"]
    company_id = context["store"].add(
        evidence.company_field(context["company"], field, as_of=context["as_of"])
    )

    return context["store"].add(
        evidence.conflict(
            context["corp_code"],
            field,
            label=label,
            kind=evidence.CONFLICT_TIMING,
            resolution=evidence.RESOLUTION_BOTH,
            sides=[
                evidence.conflict_side(
                    evidence.COMPANY_SOURCE_NAME,
                    dart_value,
                    based_on=company_id,
                    as_of=context["as_of"],
                    as_of_kind=evidence.AS_OF_LOOKUP,
                ),
                evidence.conflict_side(
                    "감사보고서 주석 「회사의 개요」",
                    note_value,
                    based_on=overview_id,
                    as_of=latest.get("fiscal_year") if latest else None,
                    as_of_kind=evidence.AS_OF_FISCAL,
                ),
            ],
        )
    )


def _check_registration(context: rules.Context) -> tuple[list[str], list[str]]:
    """법인등록번호: 기업개황 ↔ 표지 EXTRACTION. 숫자만 남겨 완전일치."""
    latest = context["gate"]["latest"]
    if latest is None:
        return [], []

    summary = latest["clean"].get("summary") or {}
    if REGISTRATION_CODE not in summary:
        return [], []

    dart = _digits(context["company"].get("jurir_no"))
    document = _digits(summary[REGISTRATION_CODE])
    if not dart or not document:
        return [], []

    store = context["store"]
    pieces = [
        store.add(
            evidence.company_field(
                context["company"], "jurir_no", as_of=context["as_of"]
            )
        ),
        store.add(evidence.summary_field(latest, REGISTRATION_CODE)),
    ]

    if dart == document:
        return pieces, []

    return pieces, [f"법인등록번호가 다르다: 기업개황 {dart} / 감사보고서 {document}"]


def _check_overview(context: rules.Context) -> tuple[list[str], list[str]]:
    """설립일·소재지: 기업개황 ↔ 주석 「회사의 개요」 본문."""
    latest = context["gate"]["latest"]
    overview = (
        nt.find_subsection(context["notes"]["subsections"], "overview")
        if context["notes"]["parsed"]
        else None
    )
    if latest is None or overview is None:
        return [], []

    store = context["store"]
    overview_id = store.add(evidence.note_subsection(latest, overview))
    pieces = [overview_id]
    warnings: list[str] = []
    text = overview.get("text") or ""
    company = context["company"]

    founded = _first_date(text)
    dart_founded = _digits(company.get("est_dt"))
    if not founded:
        warnings.append("주석에서 설립일을 찾지 못해 설립일은 대조하지 못했다")
    elif dart_founded and founded != dart_founded:
        pieces.append(
            _overview_conflict(
                context,
                "est_dt",
                "설립일",
                _dashed(dart_founded) or dart_founded,
                _dashed(founded) or founded,
                overview_id,
            )
        )
        warnings.append(
            f"설립일이 다르다: 기업개황 {_dashed(dart_founded)} / "
            f"주석 {_dashed(founded)}"
        )

    note_region = _region_of(text)
    dart_region = _region_of(company.get("adres") or "")
    if not note_region or not dart_region:
        warnings.append("소재지의 시·도를 읽지 못해 소재지는 대조하지 못했다")
    elif note_region != dart_region:
        pieces.append(
            _overview_conflict(
                context,
                "adres",
                "소재지",
                company.get("adres") or "",
                _address_phrase(text) or note_region,
                overview_id,
            )
        )
        warnings.append(
            f"소재지 시·도가 다르다: 기업개황 {dart_region} / 주석 {note_region}"
        )

    return pieces, warnings


def _address_phrase(text: str) -> str | None:
    """충돌 표시에 쓸 주석 본문의 소재지 구절. 못 찾으면 None."""
    for canonical, aliases in _REGIONS:
        for alias in aliases:
            index = (text or "").find(alias)
            if index >= 0:
                return " ".join(text[index : index + 40].split())

    return None


def _check_largest_shareholder(context: rules.Context) -> tuple[list[str], list[str]]:
    """대표이사 ↔ 최대주주.

    불일치를 '시점 차이' 로 두면 안 된다. 대표이사와 최대주주는 애초에 다를 수 있어서
    어느 쪽이 틀린 것이 아니라 그냥 동일인이 아니라는 사실이다. 그래서 충돌 유형은
    식별자 대조 불가(CONFLICT_IDENTITY)를 쓴다.
    """
    latest = context["gate"]["latest"]
    holders = _holders(context)
    ceo = (context["company"].get("ceo_nm") or "").strip()

    if latest is None or not holders or not ceo:
        return [], []


    top = _largest_holder(holders)
    if top is None:
        return [], []

    names = {name.strip().replace(" ", "") for name in ceo.split(",") if name.strip()}

    store = context["store"]
    subsection, block = _shareholder_tables(context)[0]
    pieces = [
        store.add(evidence.note_table(latest, subsection, block)),
        store.add(
            evidence.company_field(context["company"], "ceo_nm", as_of=context["as_of"])
        ),
    ]

    if top["holder"].replace(" ", "") in names:
        return pieces, []

    pieces.append(
        store.add(
            evidence.conflict(
                context["corp_code"],
                "largest_shareholder",
                label="대표이사와 최대주주",
                kind=evidence.CONFLICT_IDENTITY,
                resolution=evidence.RESOLUTION_BOTH,
                sides=[
                    evidence.conflict_side(
                        evidence.COMPANY_SOURCE_NAME,
                        f"대표이사 {ceo}",
                        based_on=pieces[1],
                        as_of=context["as_of"],
                        as_of_kind=evidence.AS_OF_LOOKUP,
                    ),
                    evidence.conflict_side(
                        "감사보고서 주석 주주현황",
                        f"최대주주 {top['holder']} {top['ratio_text']}",
                        based_on=pieces[0],
                        as_of=latest.get("fiscal_year"),
                        as_of_kind=evidence.AS_OF_FISCAL,
                    ),
                ],
            )
        )
    )

    return pieces, [
        (
            f"대표이사와 최대주주가 동일인이 아니다: 대표 {ceo} / "
            f"최대주주 {top['holder']} {top['ratio_text']}"
        )
    ]


def _a4(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """정보 일관성. 출처가 갈리면 원인을 단정하지 않고 둘 다 보여준다."""
    source = evidence.company_source(context["as_of"])

    if not context["gate"]["registered"]:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE, source=source)

    pieces: list[str] = []
    warnings: list[str] = []

    for check in (
        _check_registration,
        _check_overview,
        _check_largest_shareholder,
    ):
        found, notes = check(context)
        pieces += found
        warnings += notes

    if not pieces:
        return rules.finding(
            item,
            Verdict.SOURCE_UNAVAILABLE,
            source=source,
            warnings=["대조할 수 있는 출처를 확보하지 못했다"],
        )

    conflicts = [w for w in warnings if "다르다" in w or "동일인이 아니다" in w]
    value = (
        f"대조 {len(pieces)}건 중 불일치 {len(conflicts)}건"
        if conflicts
        else "확인한 항목이 모두 일치한다"
    )

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=value,
        evidence_ids=pieces,
        source=source,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# [4] 재무 시계열 - 3개년 병합
# ---------------------------------------------------------------------------
def build_series(reports: list[dict[str, Any]]) -> dict[str, dict[int, dict[str, Any]]]:
    """보고서 여러 건 -> {논리계정: {회계연도: 값}}.

    문서 한 건에 당기·전기가 함께 실려 연도가 겹친다. **겹치는 연도는 접수일이 가장
    늦은 문서의 값을 쓴다.** 최신 보고서가 전기 수치를 재작성했을 수 있고, 그때는
    나중에 제출된 쪽이 회사의 최종 입장이기 때문이다. 두 값의 차이를 계산하거나
    어느 쪽이 옳은지 판단하지 않는다.

    오래된 문서부터 넣어 최신 문서가 덮어쓰게 한다.
    """
    merged: dict[str, dict[int, dict[str, Any]]] = {}

    for report in sorted(reports, key=lambda r: r.get("rcept_dt") or ""):
        base = _fiscal_year(report)
        if base is None:
            continue

        for name, entry in st.extract_financials(report["clean"]).items():
            periods = entry.get("periods") or {}
            for period, offset in ((st.CURRENT_PERIOD, 0), (st.PRIOR_PERIOD, 1)):
                value = periods.get(period)
                if value is None:
                    continue

                merged.setdefault(name, {})[base - offset] = {
                    "raw": value["raw"],
                    "value": value["value"],
                    "report": report,
                    "entry": entry,
                    "name": name,
                }

    return merged


def _fiscal_year(report: dict[str, Any]) -> int | None:
    fiscal = report.get("fiscal_year")
    if not fiscal or len(fiscal) < 4 or not fiscal[:4].isdigit():
        return None

    return int(fiscal[:4])


def _years(series: dict[str, dict[int, Any]], names: tuple[str, ...]) -> list[int]:
    """표시할 회계연도. 최신순 RECENT_YEARS 개."""
    found: set[int] = set()
    for name in names:
        found |= set(series.get(name) or {})

    return sorted(found, reverse=True)[:RECENT_YEARS]


def _cite(context: rules.Context, names: tuple[str, ...], years: list[int]) -> list[str]:
    """표시한 연도의 값이 나온 계정 조각만 등록한다."""
    store = context["store"]
    series = context["series"]
    pieces: list[str] = []

    for name in names:
        by_year = series.get(name) or {}
        for year in years:
            cell = by_year.get(year)
            if cell is None:
                continue
            piece = store.add(
                evidence.account(cell["report"], cell["name"], cell["entry"])
            )
            if piece not in pieces:
                pieces.append(piece)

    return pieces


def _series_text(
    series: dict[str, dict[int, Any]], name: str, years: list[int]
) -> str | None:
    by_year = series.get(name) or {}
    parts = [
        f"{year}년 {_won(by_year[year]['value'], by_year[year]['raw'])}"
        for year in years
        if year in by_year
    ]

    return " · ".join(parts) if parts else None


def _won(value: float | None, raw: str) -> str:
    if value is None:
        return raw

    return f"{int(value):,}원"


# ---------------------------------------------------------------------------
# [5] 재무
# ---------------------------------------------------------------------------
def _financial_item(
    item: ItemDefinition,
    context: rules.Context,
    names: tuple[str, ...],
    statement: str,
    *,
    fallback: bool,
) -> rules.Finding:
    """B-1 ~ B-3 공통. 폴백 유무만 다르다."""
    gate = context["gate"]
    latest = gate["latest"]

    if not gate["audited"] or latest is None:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE)

    source = evidence.report_source(latest)
    years = _years(context["series"], names)

    if years:
        pieces = _cite(context, names, years)
        labels = [
            f"{evidence.ACCOUNT_LABELS.get(name, name)} {text}"
            for name in names
            if (text := _series_text(context["series"], name, years))
        ]
        return rules.finding(
            item,
            Verdict.CONFIRMED,
            value=" / ".join(labels),
            evidence_ids=pieces,
            source=source,
        )

    if fallback and gate["summary_fallback"]:
        return _summary_fallback(item, context, names, source, statement)

    return _no_accounts(item, context, statement, source)


def _no_accounts(
    item: ItemDefinition,
    context: rules.Context,
    statement: str,
    source: evidence.Source,
) -> rules.Finding:
    """계정을 하나도 못 찾았을 때, 그 이유를 셋으로 가른다.

    한 판정으로 뭉개면 우리 파서의 실패와 회사의 미첨부가 구분되지 않는다.
    감사보고서 71건 실측에서 현금흐름표를 못 찾은 13건이 정확히 이렇게 갈렸다.

        의견거절 3건   재무제표를 아예 첨부하지 않았다        -> ABSENT
        IFRS 9건      재무제표가 표가 아닌 형식이라 못 읽었다  -> EXTRACTION_FAILED
        해당 표만 없음 1건  나머지는 읽었는데 이 표만 없다      -> ABSENT
        표는 있는데 계정 미검출                              -> EXTRACTION_FAILED
    """
    latest = context["gate"]["latest"]
    summary = (latest["clean"].get("summary") or {}) if latest else {}
    store = context["store"]

    if summary.get(st.OPINION_CODE) == st.DISCLAIMER_OPINION:
        return rules.finding(
            item,
            Verdict.ABSENT,
            evidence_ids=[store.add(evidence.summary_field(latest, st.OPINION_CODE))],
            source=source,
            warnings=["감사의견이 의견거절이라 재무제표가 첨부되지 않았다"],
        )

    if summary.get(st.IFRS_FLAG) == "Y":
        return rules.finding(
            item,
            Verdict.EXTRACTION_FAILED,
            evidence_ids=[store.add(evidence.summary_field(latest, st.IFRS_FLAG))],
            source=source,
            warnings=["IFRS 형식이라 재무제표가 표로 첨부되지 않아 읽지 못했다"],
        )

    pieces = _statement_pieces(context, statement)
    if not pieces:
        return rules.finding(
            item,
            Verdict.ABSENT,
            source=source,
            warnings=["해당 재무제표가 문서에 첨부되지 않았다"],
        )

    return rules.finding(
        item,
        Verdict.EXTRACTION_FAILED,
        evidence_ids=pieces,
        source=source,
        warnings=["재무제표는 읽었으나 대상 계정을 찾지 못했다"],
    )


def _summary_fallback(
    item: ItemDefinition,
    context: rules.Context,
    names: tuple[str, ...],
    source: evidence.Source,
    statement: str,
) -> rules.Finding:
    """IFRS·의견거절 문서의 폴백. 표지 총액으로 최소한의 규모만 말한다.

    단위 환산은 하지 않는다. 원문이 백만원이면 백만원으로 둔다 - 환산은 F 블록의
    일이고, 그래야 후검증이 "환산값은 파생 근거에만 있다" 를 강제할 수 있다.
    """
    latest = context["gate"]["latest"]
    summary = st.summary_financials(latest["clean"])
    usable = {name: summary[name] for name in names if name in summary}

    if not usable:
        return _no_accounts(item, context, statement, source)

    store = context["store"]
    pieces = [
        store.add(evidence.summary_field(latest, cell["code"]))
        for cell in usable.values()
    ]
    labels = [
        f"{evidence.ACCOUNT_LABELS.get(name, name)} {cell['raw']}{cell['unit']}"
        for name, cell in usable.items()
    ]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=" / ".join(labels),
        evidence_ids=pieces,
        source=source,
        warnings=["재무제표 표가 없어 표지 요약(백만원 단위)으로 대체했다"],
    )


def _statement_pieces(context: rules.Context, statement: str) -> list[str]:
    """못 읽은 표 자체를 근거로 남긴다. 그래야 '못 읽었다' 를 보여줄 수 있다."""
    latest = context["gate"]["latest"]
    if latest is None:
        return []

    block = st.classify_statements(latest["clean"]).get(statement)
    if block is None:
        return []

    return [context["store"].add(evidence.statement_table(latest, statement, block))]


def _b1(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    return _financial_item(
        item, context, INCOME_ACCOUNTS, st.INCOME_STATEMENT, fallback=True
    )


def _b2(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    return _financial_item(
        item, context, BALANCE_ACCOUNTS, st.BALANCE_SHEET, fallback=True
    )


def _b3(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """현금흐름은 폴백이 없다. 표지 EXTRACTION 에 현금흐름 항목이 아예 없다."""
    return _financial_item(
        item, context, CASHFLOW_ACCOUNTS, st.CASH_FLOW, fallback=False
    )


def _b4(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """감사의견. 코드로 판정한다.

    본문에서 '적정' 같은 단어를 찾는 문자열 매칭을 쓰지 않는다. 보유 문서 5건 전부에서
    실패했던 방식이다.
    """
    latest = context["gate"]["latest"]

    if latest is None:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE)

    source = evidence.report_source(latest)
    code, label = st.audit_opinion(latest["clean"])

    if not code:
        return rules.finding(
            item,
            Verdict.EXTRACTION_FAILED,
            source=source,
            warnings=["표지 요약에 감사의견 코드가 없다"],
        )

    piece = context["store"].add(evidence.summary_field(latest, st.OPINION_CODE))

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=label or f"코드 {code} (해석표에 없는 의견)",
        evidence_ids=[piece],
        source=source,
        warnings=[] if label else [f"처음 보는 감사의견 코드다: {code}"],
    )


def _note_item(item: ItemDefinition, context: rules.Context, topic: str) -> rules.Finding:
    """주석 하위항목 하나로 판정하는 항목. B-5·B-6 이 함께 쓴다."""
    latest = context["gate"]["latest"]
    source = evidence.report_source(latest) if latest else None
    verdict, subsection = rules.note_verdict(
        context["notes"], topic, audited=context["gate"]["audited"]
    )

    if verdict is not Verdict.CONFIRMED:
        warnings = (
            ["주석 번호에 결번이 있어 없다고 단정할 수 없다"]
            if verdict is Verdict.EXTRACTION_FAILED and context["notes"]["gaps"]
            else []
        )
        return rules.finding(item, verdict, source=source, warnings=warnings)

    piece = context["store"].add(evidence.note_subsection(latest, subsection))

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"주석 {subsection['number']}. {subsection['head']}",
        evidence_ids=[piece],
        source=source,
    )


def _b5(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    return _note_item(item, context, "borrowings")


def _b6(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """계속기업 불확실성.

    설계 문서는 전용 EXTRACTION 코드를 찾지 못해 유보했지만, 감사보고서 74건 실측에서
    주석 하위항목 '계속기업가정' 이 4건에서 오탐 0으로 잡혔다. 감사보고서 본문 키워드
    탐색(5건 전부 실패)이 아니라 B-5 와 같은 주석 하위섹션 분기로 판정한다.
    """
    return _note_item(item, context, "going_concern")


# ---------------------------------------------------------------------------
# [6] 자본구조 · 사업 실질 · 리스크
# ---------------------------------------------------------------------------
# 주석 하위항목 하나로 끝나는 항목은 _note_item 한 줄이면 된다. 4갈래 분기는
# rules.note_verdict() 가 이미 한다.
def _shareholder_tables(context: rules.Context) -> list[tuple[dict, dict]]:
    """(하위항목, 주주표 블록) 목록.

    표 헤더에 '주주명' 이 있고 '피투자회사' 가 없는 표만 고른다. 배제 조건이 없으면
    업스테이지에서 종속기업 투자내역표가 걸려 "주주는 UPSTAGE AI, INC. 100%" 라는
    정반대 서술이 나온다(실측 오탐).

    실측(감사보고서 67건): 주주표가 있는 문서 32건, 없는 문서 35건, 2개 이상인 문서 0건.
    """
    found = []

    for subsection in context["notes"]["subsections"]:
        for block in subsection["blocks"]:
            if block.get("type") == "table" and nt.is_shareholder_table(block):
                found.append((subsection, block))

    return found


# 지분율 표기가 갈린다 (실측 195행): '13.77%' 121행 / '28.29' 74행. 둘 다 읽어야 한다.
# shares 에도 '6,050,000주' 처럼 단위가 붙는 경우가 있다.
_RATIO = re.compile(r"-?\d+(?:\.\d+)?")

PREFERRED_SHARE = "우선주"


def _ratio(text: str | None) -> float | None:
    """'13.77%' / '28.29' -> 13.77. 읽지 못하면 None."""
    match = _RATIO.search((text or "").replace(",", ""))

    return float(match.group()) if match else None


# '기타' 는 개별 주주가 아니라 남은 주주를 한 줄로 묶은 것이다. 최대주주를 고를 때
# 빼지 않으면 센트비의 최대주주가 최성욱(13.77%)이 아니라 '기타'(33.15%)가 되고,
# 업스테이지도 '기타주주'(29.58%)가 된다. 실측으로 확인한 오탐이다.
#
# 다만 종류별 비중(F-1)에서는 빼면 안 된다. 우선주 55.77% 안에 기타 26.76% 가 들어
# 있어서, 빼면 소계와 맞지 않는다.
_AGGREGATE_HOLDER_PREFIX = "기타"
_AGGREGATE_HOLDER_WORDS = ("소액주주",)


def _is_aggregate_holder(name: str) -> bool:
    """개별 주주가 아니라 묶음 행인가."""
    key = (name or "").replace(" ", "")

    return key.startswith(_AGGREGATE_HOLDER_PREFIX) or any(
        word in key for word in _AGGREGATE_HOLDER_WORDS
    )


def _holders(context: rules.Context) -> list[dict[str, Any]]:
    """주주를 지분율 내림차순으로. 합계·소계 행은 뺀다.

    한 사람이 보통주와 우선주를 따로 들고 있으면 행이 둘로 나뉘므로 이름으로 합산한다.
    소계 행을 빼고 개별 행만 더해야 종류별 합이 소계와 맞는다(센트비 실측으로 확인).

    묶음 행('기타')은 목록에 남기되 is_aggregate 로 표시한다. 최대주주를 고르는 쪽이
    걸러야 하고, 주주 수를 셀 때는 있는 그대로 세는 편이 정직하다.
    """
    totals: dict[str, dict[str, Any]] = {}

    for _subsection, block in _shareholder_tables(context):
        for row in nt.parse_shareholders(block):
            if row["is_total"]:
                continue
            ratio = _ratio(row["ratio"])
            if ratio is None:
                continue

            entry = totals.setdefault(
                row["holder"],
                {
                    "holder": row["holder"],
                    "ratio": 0.0,
                    "is_aggregate": _is_aggregate_holder(row["holder"]),
                },
            )
            entry["ratio"] += ratio

    for entry in totals.values():
        entry["ratio_text"] = f"{entry['ratio']:.2f}%"

    return sorted(totals.values(), key=lambda e: e["ratio"], reverse=True)


def _largest_holder(holders: list[dict[str, Any]]) -> dict[str, Any] | None:
    """최대주주. 묶음 행은 건너뛴다."""
    return next((h for h in holders if not h["is_aggregate"]), None)


def _share_class_ratios(context: rules.Context) -> dict[str, float]:
    """주식 종류별 지분율 합. 종류 열이 없는 표에서는 빈 dict 다.

    실측: 주주표 32건 중 '주식의 종류' 열이 있는 표는 3건뿐이다. 나머지는 종류별
    비중을 계산할 수 없고, 그럴 때는 F-1 파생을 아예 만들지 않는다.
    """
    totals: dict[str, float] = {}

    for _subsection, block in _shareholder_tables(context):
        for row in nt.parse_shareholders(block):
            share_class = row["share_class"]
            if row["is_total"] or not share_class:
                continue
            ratio = _ratio(row["ratio"])
            if ratio is None:
                continue

            key = share_class.replace(" ", "")
            totals[key] = totals.get(key, 0.0) + ratio

    return totals


def _c1(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """주주 구성·지분율.

    주주현황은 감사보고서 필수 기재사항이 아니다. 없는 것이 절반(35/67)이고 그건
    확인한 결과이지 우리 실패가 아니다.
    """
    latest = context["gate"]["latest"]
    source = evidence.report_source(latest) if latest else None

    if not context["gate"]["audited"]:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE)

    if not context["notes"]["parsed"]:
        return rules.finding(item, Verdict.EXTRACTION_FAILED, source=source)

    tables = _shareholder_tables(context)

    if not tables:
        if context["notes"]["gaps"]:
            return rules.finding(
                item,
                Verdict.EXTRACTION_FAILED,
                source=source,
                warnings=["주석 번호에 결번이 있어 없다고 단정할 수 없다"],
            )
        return rules.finding(item, Verdict.ABSENT, source=source)

    store = context["store"]
    pieces = [
        store.add(evidence.note_table(latest, subsection, block))
        for subsection, block in tables
    ]
    holders = _holders(context)
    top = _largest_holder(holders)

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"주주 {len(holders)}인. 최대주주 {top['holder']} {top['ratio_text']}"
        if top
        else f"주주표 {len(pieces)}건",
        evidence_ids=pieces,
        source=source,
    )


def _c2(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """자본금·발행주식. 주석 「자본금」 또는 재무상태표 자본금 계정."""
    found = _note_item(item, context, "capital")
    capital = context["series"].get("capital_stock") or {}

    if found["verdict"] is Verdict.CONFIRMED.value or not capital:
        return found

    years = sorted(capital, reverse=True)
    cell = capital[years[0]]
    piece = context["store"].add(
        evidence.account(cell["report"], cell["name"], cell["entry"])
    )

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"{years[0]}년 자본금 {_won(cell['value'], cell['raw'])}",
        evidence_ids=[piece],
        source=evidence.report_source(cell["report"]),
        warnings=["자본금 주석은 찾지 못해 재무상태표 계정으로 대신했다"],
    )


def _c3(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """투자성 증권(전환사채·신주인수권부사채·전환우선주).

    실측 3/67 이다. ABSENT 가 정상 판정이고 그건 "발행하지 않았다" 는 뜻이다.
    """
    return _note_item(item, context, "convertible_bond")


def _c4(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """투자 라운드·금액. 공시에 기재되지 않고 연동한 출처도 없다."""
    return rules.finding(
        item,
        Verdict.SOURCE_UNAVAILABLE,
        warnings=["투자 라운드는 공시 기재사항이 아니고 연동한 출처가 없다"],
    )


def _d1(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """주요 사업 내용. 1차 소스는 뉴스가 아니라 공시 원문이다."""
    found = _note_item(item, context, "overview")
    induty = context["company"].get("induty_code")

    if not induty:
        return found

    piece = context["store"].add(
        evidence.company_field(context["company"], "induty_code", as_of=context["as_of"])
    )
    found["evidence_ids"].append(piece)

    return found


def _d2(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """특허. KIPRIS 미연동.

    코드는 있으나 특허검색 응답의 키 이름이 실서버로 검증된 적이 없다. 같은 방식의
    추정이 행정이력 API 에서 이미 한 번 틀렸으므로(실제 키는 소문자였다) 지금 상태로
    CONFIRMED 를 내면 검증되지 않은 응답을 근거라고 부르는 셈이다.
    """
    return rules.finding(
        item,
        Verdict.SOURCE_UNAVAILABLE,
        warnings=[
            (
                "KIPRIS 를 아직 연동하지 않았다. 특허검색 응답의 키 이름을 실서버로 "
                "확정한 뒤에 붙인다"
            )
        ],
    )


def _d3(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """주요 매출처.

    비상장 외부감사 대상 법인의 법정 공시사항이 아니다. 확인 대상이 아니므로 ABSENT 가
    아니라 NOT_REQUIRED 다 - ABSENT 로 적으면 "찾아봤는데 없다" 가 되어 없는 흠을 만든다.
    """
    latest = context["gate"]["latest"]

    return rules.finding(
        item,
        Verdict.NOT_REQUIRED,
        source=evidence.report_source(latest) if latest else None,
    )


def _d4(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """최근 동향(뉴스).

    뉴스 워크플로는 async 라 이 계층에서 부를 수 없다. 대신 service 가 먼저 받아
    collected["news"] 에 넣어 주고, 여기서는 _a2 가 collected["nts"] 를 읽는 것과 똑같이
    동기로 판정만 한다. 판정은 infer 가, 서술은 compose 가 한다는 계층이 그대로 유지된다.

    기사 0건은 ABSENT 다. 검색은 했고 결과가 없었다는 뜻이지 우리가 못 읽은 게 아니다.
    """
    news = context["collected"].get("news")
    source = evidence.news_source({})

    if not news:
        detail = context["collected"].get("news_error") or "뉴스를 조회하지 않았다"
        return rules.finding(
            item, Verdict.SOURCE_UNAVAILABLE, source=source, warnings=[detail]
        )

    if news.get("status") == NEWS_ERROR:
        return rules.finding(
            item,
            Verdict.SOURCE_UNAVAILABLE,
            source=source,
            warnings=news.get("errors") or ["뉴스 검색이 실패했다"],
        )

    articles = news.get("articles") or []
    if not articles:
        return rules.finding(
            item,
            Verdict.ABSENT,
            source=source,
            warnings=["검색했으나 이 기업의 최근 기사를 찾지 못했다"],
        )

    store = context["store"]
    pieces = [
        store.add(evidence.news_item(context["corp_code"], article))
        for article in articles
    ]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"최근 기사 {len(pieces)}건",
        evidence_ids=pieces,
        source=source,
        # 뉴스는 공시가 아니다. 이 경고가 화면의 '참고' 배지와 짝을 이룬다.
        warnings=["뉴스는 공시가 아니다. 수치는 공시로 다시 확인해야 한다"],
    )


def _e1(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """특수관계자 거래. 실측 66/67 로 거의 항상 있다."""
    return _note_item(item, context, "related_party")


def _e2(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """우발채무·소송·보증.

    우발 주석을 먼저 보고, 없으면 소송 주석을 본다. 담보제공·지급보증도 우발 키워드에
    포함되어 있다(실측 52 -> 61/67).

    본문 전역 문자열 탐색을 쓰지 않는다 - '충당부채' 는 주석이 아니라 재무상태표
    세부항목에서 잡힌다는 실측 오탐이 있다.
    """
    found = _note_item(item, context, "contingency")

    if found["verdict"] == Verdict.CONFIRMED.value:
        return found

    litigation = _note_item(item, context, "litigation")

    return litigation if litigation["verdict"] == Verdict.CONFIRMED.value else found


def _e3(item: ItemDefinition, context: rules.Context) -> rules.Finding:
    """공시 정정 이력.

    수집 결과가 F001 원본 목록을 돌려주지 않으므로 최신 3건의 corrected 플래그만 본다.
    그보다 오래된 보고서의 정정은 보이지 않는다 - 그 한계를 경고로 남긴다.
    """
    gate = context["gate"]

    if not gate["audited"]:
        return rules.finding(item, Verdict.SOURCE_UNAVAILABLE)

    limit = [f"최신 {len(gate['reports'])}건만 확인했다. 그 이전 정정은 보이지 않는다"]
    corrected = [report for report in gate["reports"] if report.get("corrected")]

    if not corrected:
        return rules.finding(
            item,
            Verdict.ABSENT,
            source=evidence.disclosure_source(evidence.disclosure_view(gate["reports"][0])),
            warnings=limit,
        )

    store = context["store"]
    pieces = [
        store.add(evidence.disclosure_item(context["corp_code"], evidence.disclosure_view(r)))
        for r in corrected
    ]

    return rules.finding(
        item,
        Verdict.CONFIRMED,
        value=f"정정 공시 {len(corrected)}건",
        evidence_ids=pieces,
        source=evidence.disclosure_source(evidence.disclosure_view(corrected[0])),
        warnings=limit,
    )


# ---------------------------------------------------------------------------
# [7] 파생 - 산수는 전부 여기서 한다
# ---------------------------------------------------------------------------
EOK = 100_000_000


def _eok(value: float) -> str:
    return f"{value / EOK:,.1f}억원"


def _pair(series: dict[str, dict[int, Any]], name: str) -> tuple[Any, Any] | None:
    """최근 2개년 (당해, 직전). 둘 다 값이 있어야 한다."""
    by_year = series.get(name) or {}
    years = sorted((y for y in by_year if by_year[y]["value"] is not None), reverse=True)

    if len(years) < 2:
        return None

    return by_year[years[0]] | {"year": years[0]}, by_year[years[1]] | {
        "year": years[1]
    }


def _derive(context: rules.Context) -> list[str]:
    """F-3 ~ F-6. B 입력만으로 닫히는 파생만 만든다.

    F-1(우선주 비중)·F-2(최대주주 지분율)는 주주표가 있어야 하므로 여기 없다.
    """
    series = context["series"]
    store = context["store"]
    corp = context["corp_code"]
    pieces: list[str] = []

    def cite(cell: dict[str, Any]) -> str:
        return store.add(evidence.account(cell["report"], cell["name"], cell["entry"]))

    # F-3 손익 전환
    net = _pair(series, "net_income")
    if net is not None:
        current, prior = net
        if (current["value"] > 0) != (prior["value"] > 0):
            turned = "적자 전환" if current["value"] < 0 else "흑자 전환"
            pieces.append(
                store.add(
                    evidence.derived(
                        corp,
                        "F-3",
                        label="손익 전환",
                        formula=f"{prior['year']}년 부호 -> {current['year']}년 부호",
                        result=f"{prior['year']}년 {int(prior['value']):,}원 -> "
                        f"{current['year']}년 {int(current['value']):,}원 ({turned})",
                        based_on=[cite(prior), cite(current)],
                    )
                )
            )

    # F-4 매출은 늘었는데 영업현금흐름은 줄었다
    revenue = _pair(series, "revenue")
    cash = _pair(series, "operating_cash_flow")
    if revenue is not None and cash is not None:
        rev_now, rev_before = revenue
        cash_now, cash_before = cash
        if rev_now["value"] > rev_before["value"] and cash_now["value"] < cash_before["value"]:
            pieces.append(
                store.add(
                    evidence.derived(
                        corp,
                        "F-4",
                        label="매출 증가 · 영업현금흐름 감소",
                        formula="매출 증감 부호 vs 영업활동현금흐름 증감 부호",
                        result=f"매출 {int(rev_before['value']):,}원 -> "
                        f"{int(rev_now['value']):,}원 증가, 영업활동현금흐름 "
                        f"{int(cash_before['value']):,}원 -> "
                        f"{int(cash_now['value']):,}원 감소",
                        based_on=[
                            cite(rev_before),
                            cite(rev_now),
                            cite(cash_before),
                            cite(cash_now),
                        ],
                    )
                )
            )

    # F-1 · F-2 주주 구성 파생
    pieces += _shareholder_derived(context)

    # F-5 부채비율
    pieces += _debt_ratio(context, cite)

    # F-6 단위 환산. LLM 이 억원으로 말하려면 그 숫자가 근거 원문에 있어야 한다.
    pieces += _conversions(context, cite)

    return pieces


def _shareholder_derived(context: rules.Context) -> list[str]:
    """F-1 우선주 비중 · F-2 최대주주. 주주표가 있어야 돌아간다.

    scope 는 rcept_no 다 - 두 계산 모두 한 보고서 안에서 닫힌다.
    """
    tables = _shareholder_tables(context)
    latest = context["gate"]["latest"]
    if not tables or latest is None:
        return []

    store = context["store"]
    rcept_no = latest["rcept_no"]
    subsection, block = tables[0]
    table_id = store.add(evidence.note_table(latest, subsection, block))
    made: list[str] = []

    # F-2 최대주주. 지분율만 있으면 되므로 주주표 32건 전부에서 계산된다.
    top = _largest_holder(_holders(context))
    if top is not None:
        ceo = (context["company"].get("ceo_nm") or "").strip()
        names = {n.strip().replace(" ", "") for n in ceo.split(",") if n.strip()}
        same = top["holder"].replace(" ", "") in names
        made.append(
            store.add(
                evidence.derived(
                    rcept_no,
                    "F-2",
                    label="최대주주 지분율",
                    formula="주주별 지분율 합계의 최댓값 (합계·소계 행 제외)",
                    result=f"최대주주 {top['holder']} {top['ratio_text']}"
                    + (f" · 대표이사({ceo})가 최대주주다" if same else ""),
                    based_on=[table_id],
                )
            )
        )

    # F-1 우선주 비중. 주식 종류 열이 있는 표에서만 계산된다(실측 3/32).
    by_class = _share_class_ratios(context)
    preferred = sum(v for k, v in by_class.items() if PREFERRED_SHARE in k)
    if by_class and preferred:
        others = sum(v for k, v in by_class.items() if PREFERRED_SHARE not in k)
        verdict = "과반" if preferred > others else "과반 아님"
        made.append(
            store.add(
                evidence.derived(
                    rcept_no,
                    "F-1",
                    label="우선주 비중",
                    formula="주식 종류별 지분율 합계 비교",
                    result=f"우선주 {preferred:.2f}% / 그 외 {others:.2f}% ({verdict})",
                    based_on=[table_id],
                )
            )
        )

    return made


def _debt_ratio(context: rules.Context, cite: Callable[[dict], str]) -> list[str]:
    series = context["series"]
    years = _years(series, ("total_liabilities", "total_equity"))
    made: list[str] = []

    for year in years:
        debt = (series.get("total_liabilities") or {}).get(year)
        equity = (series.get("total_equity") or {}).get(year)
        if not debt or not equity or not equity["value"]:
            continue

        ratio = debt["value"] / equity["value"] * 100
        made.append(
            context["store"].add(
                evidence.derived(
                    context["corp_code"],
                    "F-5",
                    variant=str(year),
                    label=f"{year}년 부채비율",
                    formula="부채총계 / 자본총계 x 100",
                    result=f"{year}년 부채비율 {ratio:,.1f}% "
                    f"(부채 {int(debt['value']):,}원 / 자본 {int(equity['value']):,}원)",
                    based_on=[cite(debt), cite(equity)],
                )
            )
        )

    return made


def _conversions(context: rules.Context, cite: Callable[[dict], str]) -> list[str]:
    """최신 연도 금액의 억원 환산. 항목마다 하나씩."""
    series = context["series"]
    made: list[str] = []

    for name in INCOME_ACCOUNTS + BALANCE_ACCOUNTS + CASHFLOW_ACCOUNTS:
        by_year = series.get(name) or {}
        years = sorted(
            (y for y in by_year if by_year[y]["value"] is not None), reverse=True
        )
        if not years:
            continue

        cell = by_year[years[0]]
        label = evidence.ACCOUNT_LABELS.get(name, name)
        made.append(
            context["store"].add(
                evidence.derived(
                    context["corp_code"],
                    "F-6",
                    variant=f"{name}:{years[0]}",
                    label=f"{label} 단위 환산",
                    formula="원 / 100,000,000",
                    result=f"{years[0]}년 {label} {int(cell['value']):,}원 = "
                    f"약 {_eok(cell['value'])}",
                    based_on=[cite(cell)],
                )
            )
        )

    return made


# ---------------------------------------------------------------------------
# [8] 진입점
# ---------------------------------------------------------------------------
_RULES: dict[str, Callable[[ItemDefinition, rules.Context], rules.Finding]] = {
    "G-1": _g1,
    "G-2": _g2,
    "G-3": _g3,
    "G-4": _g4,
    "A-1": _a1,
    "A-2": _a2,
    "A-3": _a3,
    "A-4": _a4,
    "B-1": _b1,
    "B-2": _b2,
    "B-3": _b3,
    "B-4": _b4,
    "B-5": _b5,
    "B-6": _b6,
    "C-1": _c1,
    "C-2": _c2,
    "C-3": _c3,
    "C-4": _c4,
    "D-1": _d1,
    "D-2": _d2,
    "D-3": _d3,
    "D-4": _d4,
    "E-1": _e1,
    "E-2": _e2,
    "E-3": _e3,
}


class InferResult(TypedDict):
    findings: dict[str, rules.Finding]
    derived: list[str]
    evidence: list[evidence.Evidence]
    gate: rules.GateState
    signals: list[Any]        # detect.Signal. 자료형은 signals.py 가 소유한다
    investigations: list[Any]  # detect 가 실행한 조사 큐
    coverage: dict[str, Any]   # 무엇을 평가할 수 있었는가


def run(collected: dict[str, Any], *, as_of: str) -> InferResult:
    """수집 결과 -> 항목 판정 + 근거 조각.

    as_of 는 조회일이다. evidence.py 가 시계를 읽지 않으므로 여기서도 만들지 않고
    인자로 받아 그대로 넘긴다 - 그래야 같은 입력이 항상 같은 조각을 만든다.
    """
    gate = rules.gate_state(collected)
    context: rules.Context = {
        "collected": collected,
        "company": collected.get("company") or {},
        "corp_code": collected["corp_code"],
        "as_of": as_of,
        "gate": gate,
        "notes": rules.note_context(gate["latest"]),
        "series": build_series(gate["reports"]),
        "store": evidence.EvidenceStore(),
    }

    findings = {
        item_id: rule(rules.definition(item_id), context)
        for item_id, rule in _RULES.items()
    }

    # 파생이 먼저 끝나야 한다. 승격 신호(손익 전환·매출과 현금흐름의 괴리)가 F-3·F-4
    # 조각을 찾아 인용하고, 부채 급증이 F-5 부채비율을 붙이기 때문이다.
    derived = _derive(context)

    # 이상징후 탐지와 후속 조사. context 를 그대로 넘긴다 - series·notes·gate·store 가
    # 이미 다 만들어져 있으므로 재수집 없이 끝난다. store 를 공유하므로 조사가 등록한
    # 근거 조각도 아래 dump() 에 함께 담긴다.
    detected = detect.run(context, findings, derived)

    return {
        "findings": findings,
        "derived": derived,
        "evidence": context["store"].dump(),
        "gate": gate,
        "signals": detected["signals"],
        "investigations": detected["tasks"],
        "coverage": detected["coverage"],
    }
