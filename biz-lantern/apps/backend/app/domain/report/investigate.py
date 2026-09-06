"""이상징후가 요구한 조사를 실행한다. 큐 병합·우선순위·resolver.

    [1] 큐 병합    plan()
    [2] 우선순위   prioritize()
    [3] resolver   kind 별 조사 실행
    [4] 진입점     run()

왜 큐를 따로 두는가

    신호는 여러 개가 동시에 뜨고, 서로 다른 신호가 같은 자료를 요구한다. 센트비 실측에서
    DEBT_SURGE 와 FINANCING_CF_SURGE 가 둘 다 차입금 주석을 요구한다. 신호마다 따로
    조사하면 같은 주석 원문 조각이 두 번 등록되고, 근거팩이 부풀고, PACK_TOTAL_CHARS
    한도에 먼저 걸려 **다른 근거가 잘려 나간다.** 병합은 선택이 아니라 필수다.

    정의표 9개 신호가 요청하는 조사는 연인원 57건인데 고유 항목은 26건이다. 절반 이상이
    중복이다.

이 계층은 네트워크에 나가지 않는다

    resolver 는 rules.Context 만 읽는다 - series·notes·gate·store 는 infer.run() 이
    시작할 때 이미 다 만들어 놓은 것이다. pipeline 을 다시 부르지 않고 DART 를 다시
    치지 않는다. "이미 수집한 것을 목적을 갖고 다시 읽는다" 가 1단계의 정의다.

    2단계(뉴스 재검색·투자이력·홈페이지·채용·특허)는 kind 를 하나 늘리고 resolver 를
    등록하면 되는 자리로 비워 두었다. InvestigationTask 자료형은 그대로 쓴다.

GAP 을 부재로 말하지 않는다

    조사했는데 자료가 없는 것(GAP)과 자료가 없다는 사실(부재)은 다르다. 주석 목차에
    결번이 있으면 우리가 놓친 것일 수 있으므로 "없다" 고 단정하지 않는다 -
    rules.note_verdict 가 ABSENT 와 EXTRACTION_FAILED 를 가르는 그 규율을 여기서도
    그대로 적용한다.
"""

from collections.abc import Callable
from typing import Any

from app.domain.company.parser import notes as nt
from app.domain.company.parser import statements as st
from app.domain.report import evidence, rules
from app.domain.report import signals as sg

# 조사 결과에 보여줄 연도 수. infer.RECENT_YEARS 와 같은 값이지만 import 방향을
# 만들지 않으려고 여기서 정한다.
DISPLAY_YEARS = 3

# 뉴스는 조사 결과에 제목만 싣는다. 본문까지 result 에 넣으면 조사 한 줄이 수천 자가
# 되어 화면에서 읽을 수 없다 - 본문은 news 근거 조각에 이미 통째로 들어 있다.
NEWS_LIMIT = 3


# ---------------------------------------------------------------------------
# [1] 큐 병합
# ---------------------------------------------------------------------------
def plan(signals: list[sg.Signal]) -> list[sg.InvestigationTask]:
    """신호들의 조사 목록 -> 중복을 없앤 조사 큐.

    등장 순서를 지킨다. 정의표가 적어 둔 조사 순서가 그 신호 안에서의 우선순위이고,
    먼저 뜬 신호의 순서를 뒤에 온 신호가 흔들지 않아야 결과가 결정적이다.

    같은 task_id 를 요청한 신호는 requested_by 에 쌓인다. 그 길이가 곧 우선순위의
    첫 번째 기준이 된다.
    """
    order: list[str] = []
    requested: dict[str, list[str]] = {}

    for signal in signals:
        for task_id in signal["investigations"]:
            if task_id not in requested:
                requested[task_id] = []
                order.append(task_id)

            if signal["signal_id"] not in requested[task_id]:
                requested[task_id].append(signal["signal_id"])

    return [sg.task(task_id, requested[task_id]) for task_id in order]


# ---------------------------------------------------------------------------
# [2] 우선순위
# ---------------------------------------------------------------------------
def prioritize(tasks: list[sg.InvestigationTask]) -> list[sg.InvestigationTask]:
    """조사 순서를 정한다.

        1. 여러 신호가 함께 요청한 것 먼저.
           같은 자료를 두 신호가 요구했다는 것은 그것이 이번 보고서의 중심이라는 뜻이다.
        2. 같은 문서 안에서 즉시 닫히는 것 먼저 (KIND_ORDER).
           계정은 값이 바로 나오고 뉴스는 공시가 아니라 정황이다.
        3. 동점이면 큐에 들어온 순서 (= 정의표 등재 순서).

    3번이 있어야 정렬이 결정적이다. 같은 입력이 같은 보고서를 만들어야 한다.
    """
    seq = {task["task_id"]: index for index, task in enumerate(tasks)}

    return sorted(
        tasks,
        key=lambda task: (
            -len(task["requested_by"]),
            sg.KIND_ORDER.index(task["kind"]),
            seq[task["task_id"]],
        ),
    )


# ---------------------------------------------------------------------------
# [3] resolver
# ---------------------------------------------------------------------------
def _resolved(
    task: sg.InvestigationTask, result: str, evidence_ids: list[str]
) -> sg.InvestigationTask:
    task["status"] = sg.STATUS_RESOLVED
    task["result"] = result
    task["evidence_ids"] = evidence_ids

    return task


def _gap(task: sg.InvestigationTask, reason: str) -> sg.InvestigationTask:
    """조사했는데 자료가 없었다. 왜 없는지를 반드시 적는다.

    근거 조각은 만들지 않는다. "자료가 없다" 는 원문이 없으므로 조각이 될 수 없다 -
    rules.finding() 이 비-CONFIRMED 에 value 를 싣지 못하게 막는 것과 같은 규율이다.
    """
    task["status"] = sg.STATUS_GAP
    task["result"] = reason
    task["evidence_ids"] = []

    return task


# --- 계정 -------------------------------------------------------------------
# 조사 항목 -> 훑을 논리 계정. 대부분의 계정 조사는 "이 계정들의 연도별 값을 보여 달라"
# 한 가지라서 표로 둔다. 표에 없는 둘(잠식 여부·항등식)만 따로 함수를 갖는다.
_ACCOUNT_SERIES: dict[str, tuple[str, ...]] = {
    "borrowings": ("short_term_borrowings", "long_term_borrowings", "bond_with_warrant"),
    "capital_stock": ("capital_stock",),
    "preferred_capital": ("preferred_capital", "common_capital"),
    "equity_series": ("total_equity",),
    "financing_cash_flow": ("financing_cash_flow",),
    "investing_cash_flow": ("investing_cash_flow",),
    "receivables": ("trade_receivable", "other_receivable"),
    "revenue_series": ("revenue",),
    "operating_income_series": ("operating_income",),
}


def _years_of(by_year: dict[int, dict[str, Any]], limit: int = DISPLAY_YEARS) -> list[int]:
    """값이 있는 회계연도. 최신순."""
    return sorted(
        (year for year in by_year if by_year[year]["value"] is not None), reverse=True
    )[:limit]


def _cite(context: rules.Context, cell: dict[str, Any]) -> str:
    """계정 셀 하나를 근거로 등록하고 ID 를 돌려준다.

    infer._cite 와 같은 팩토리를 부르므로 ID 가 그대로 겹친다. 겹치는 것이 옳다 -
    B-2 가 등록한 부채총계 조각과 이 조사가 등록한 것은 같은 원문이다.
    """
    return context["store"].add(
        evidence.account(cell["report"], cell["name"], cell["entry"])
    )


def _series_report(
    context: rules.Context, names: tuple[str, ...]
) -> tuple[list[str], list[str]]:
    """계정들의 연도별 값 -> (읽을 줄, 근거 ID).

    최근 2개년 증감을 함께 적는다. 조사의 목적이 "이 계정이 그 변화의 원인인가" 이므로
    값만 나열하면 답이 되지 않는다 - 센트비 차입금은 2024·2025 둘 다 36억이라
    "변동 없음" 이 나와야 부채 급증의 원인이 아니라는 결론이 선다.
    """
    series = context["series"]
    lines: list[str] = []
    pieces: list[str] = []

    for name in names:
        by_year = series.get(name) or {}
        years = _years_of(by_year)
        if not years:
            continue

        label = evidence.ACCOUNT_LABELS.get(name, name)
        parts = [f"{year}년 {sg.won(by_year[year]['value'])}" for year in years]

        if len(years) >= 2:
            delta = by_year[years[0]]["value"] - by_year[years[1]]["value"]
            if delta == 0:
                parts.append("변동 없음")
            else:
                way = "증가" if delta > 0 else "감소"
                parts.append(f"전년 대비 {sg.won(abs(delta))} {way}")

        lines.append(f"{label} " + " · ".join(parts))

        for year in years:
            piece = _cite(context, by_year[year])
            if piece not in pieces:
                pieces.append(piece)

    return lines, pieces


def _resolve_account(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    target = task["target"]

    if target == "equity_vs_capital":
        return _resolve_equity_vs_capital(task, context)

    if target == "identity_check":
        return _resolve_identity(task, context)

    names = _ACCOUNT_SERIES.get(target)
    if names is None:
        return _gap(task, f"조사 항목을 해석하지 못했다: {task['task_id']}")

    lines, pieces = _series_report(context, names)
    if not lines:
        labels = " · ".join(evidence.ACCOUNT_LABELS.get(n, n) for n in names)
        return _gap(
            task,
            f"재무제표에서 해당 계정을 찾지 못했다 ({labels}). 계정이 없는 것이 "
            "정상일 수 있다 - 무차입 회사에 차입금 계정은 없다.",
        )

    return _resolved(task, " / ".join(lines), pieces)


def _resolve_equity_vs_capital(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    """자본잠식 여부. 자본총계와 자본금을 같은 해로 맞춰 본다."""
    series = context["series"]
    equity = series.get("total_equity") or {}
    capital = series.get("capital_stock") or {}
    shared = sorted(
        (
            year
            for year in set(equity) & set(capital)
            if equity[year]["value"] is not None and capital[year]["value"] is not None
        ),
        reverse=True,
    )

    if not shared:
        return _gap(task, "자본총계와 자본금이 같은 해에 함께 잡힌 적이 없다.")

    year = shared[0]
    equity_value = equity[year]["value"]
    capital_value = capital[year]["value"]

    if equity_value <= 0:
        verdict = "완전자본잠식"
    elif equity_value < capital_value:
        verdict = "부분자본잠식"
    else:
        verdict = "자본잠식 아님"

    return _resolved(
        task,
        f"{year}년 자본총계 {sg.won(equity_value)} / 자본금 {sg.won(capital_value)} "
        f"({verdict})",
        [_cite(context, equity[year]), _cite(context, capital[year])],
    )


def _resolve_identity(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    """자산 = 부채 + 자본 이 유지되는가.

    재작성 신호의 확인용이다. 항등식이 깨지면 우리가 다른 표에서 값을 주워 온 것이고,
    유지되면 회사가 실제로 숫자를 바꾼 것이다.
    """
    series = context["series"]
    assets = series.get("total_assets") or {}
    debts = series.get("total_liabilities") or {}
    equity = series.get("total_equity") or {}

    shared = sorted(
        (
            year
            for year in set(assets) & set(debts) & set(equity)
            if all(
                table[year]["value"] is not None for table in (assets, debts, equity)
            )
        ),
        reverse=True,
    )

    if not shared:
        return _gap(task, "자산·부채·자본이 같은 해에 함께 잡힌 적이 없다.")

    lines: list[str] = []
    pieces: list[str] = []

    for year in shared[:DISPLAY_YEARS]:
        gap = assets[year]["value"] - (debts[year]["value"] + equity[year]["value"])
        state = "일치" if gap == 0 else f"차이 {sg.won(abs(gap))}"
        lines.append(f"{year}년 {state}")
        for table in (assets, debts, equity):
            piece = _cite(context, table[year])
            if piece not in pieces:
                pieces.append(piece)

    return _resolved(task, "자산 = 부채 + 자본 " + " · ".join(lines), pieces)


# --- 주석 -------------------------------------------------------------------
def _resolve_note(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    """주석 하위항목 하나를 찾아 원문과 표를 근거로 붙인다.

    표를 반드시 함께 붙인다. 실측에서 센트비 차입금 주석의 text 는 "(1) 보고기간종료일
    현재 단기차입금의 내역은 다음과 같습니다." 뿐이고 **금액은 전부 표 블록에 있다**
    (신한은행 · 3.51% · 800,000 / 1,000,000 / 900,000). 하위항목만 붙이면 조사가
    "차입금 주석이 있다" 까지만 말하고 "얼마인가" 에 답하지 못한다.
    """
    notes = context["notes"]
    latest = context["gate"]["latest"]

    if latest is None:
        return _gap(task, "감사보고서를 확보하지 못해 주석을 볼 수 없다.")

    if not notes["parsed"]:
        return _gap(
            task,
            "주석을 하위항목으로 쪼개지 못했다. 해당 내용이 없다는 뜻이 아니라 "
            "우리가 읽지 못했다는 뜻이다.",
        )

    try:
        found = nt.find_subsection(notes["subsections"], task["target"])
    except KeyError:
        return _gap(task, f"알 수 없는 주석 주제다: {task['target']}")

    if found is None:
        if notes["gaps"]:
            missing = ", ".join(str(n) for n in notes["gaps"])
            return _gap(
                task,
                f"해당 주석을 찾지 못했다. 주석 번호에 결번({missing})이 있어 "
                "우리가 놓쳤을 가능성이 있으므로 없다고 단정하지 않는다.",
            )

        return _gap(
            task,
            "주석 목차를 결번 없이 전부 확인했고 해당 항목이 없다. 회사가 이 주석을 "
            "쓰지 않았다.",
        )

    store = context["store"]
    pieces = [store.add(evidence.note_subsection(latest, found))]
    tables = 0

    for index, block in enumerate(found["blocks"]):
        if block.get("type") != "table":
            continue
        pieces.append(store.add(evidence.note_block(latest, found, index)))
        tables += 1

    detail = f", 표 {tables}개" if tables else ", 표 없음"

    return _resolved(task, f"주석 {found['number']}. {found['head']}{detail}", pieces)


# --- 표지 -------------------------------------------------------------------
def _resolve_summary(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    reports = context["gate"]["reports"]
    latest = context["gate"]["latest"]

    if latest is None:
        return _gap(task, "감사보고서를 확보하지 못했다.")

    store = context["store"]

    if task["target"] == "opinion":
        code, label = st.audit_opinion(latest["clean"])
        if not code:
            return _gap(task, "표지에서 감사의견 코드를 찾지 못했다.")

        name = label or f"코드 {code} (처음 보는 의견)"
        return _resolved(
            task,
            f"{latest.get('fiscal_year') or '최신'} 감사의견 {name}",
            [store.add(evidence.summary_field(latest, st.OPINION_CODE))],
        )

    if task["target"] == "auditor":
        names = [
            (report.get("fiscal_year") or "?", report.get("auditor") or "(미상)")
            for report in reports
        ]
        if not names:
            return _gap(task, "감사보고서가 없어 감사인을 비교할 수 없다.")

        distinct = {auditor for _, auditor in names}
        state = "동일" if len(distinct) == 1 else "교체 있음"
        pieces = [
            store.add(evidence.disclosure_item(context["corp_code"], evidence.disclosure_view(report)))
            for report in reports
        ]

        listed = " · ".join(f"{year} {auditor}" for year, auditor in names)

        return _resolved(task, f"{listed} ({state})", pieces)

    return _gap(task, f"조사 항목을 해석하지 못했다: {task['task_id']}")


# --- 주주표 -----------------------------------------------------------------
def _resolve_shareholder(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    """주주현황 표. notes 의 공개 함수만 써서 infer 를 import 하지 않는다."""
    notes = context["notes"]
    latest = context["gate"]["latest"]

    if latest is None or not notes["parsed"]:
        return _gap(task, "주석을 읽지 못해 주주표를 볼 수 없다.")

    for subsection in notes["subsections"]:
        for index, block in enumerate(subsection["blocks"]):
            if block.get("type") != "table" or not nt.is_shareholder_table(block):
                continue

            # 사람 수는 행 수가 아니라 **이름의 수**다. 한 사람이 보통주와 우선주를
            # 나눠 들면 두 행으로 오기 때문이다(센트비 실측 15행 / 12인). C-1 판정도
            # 같은 방식으로 세므로, 행 수를 쓰면 같은 보고서 안에서 두 숫자가 어긋난다.
            holders = {
                (row["holder"] or "").strip()
                for row in nt.parse_shareholders(block)
                if not row["is_total"] and (row["holder"] or "").strip()
            }

            return _resolved(
                task,
                f"주석 {subsection['number']}. {subsection['head']} 의 주주현황 표. "
                f"주주 {len(holders)}인",
                [context["store"].add(evidence.note_block(latest, subsection, index))],
            )

    return _gap(
        task,
        "주석에서 주주현황 표를 찾지 못했다. 실측 감사보고서 67건 중 35건에는 애초에 "
        "주주표가 없다.",
    )


# --- 공시·뉴스 ---------------------------------------------------------------
def _resolve_disclosure(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    reports = context["gate"]["reports"]
    if not reports:
        return _gap(task, "공시 목록을 확보하지 못했다.")

    corrected = [report for report in reports if report.get("corrected")]
    if not corrected:
        return _resolved(
            task,
            f"확인한 감사보고서 {len(reports)}건에 정정 공시가 없다 "
            "(그 이전 정정은 수집 범위 밖이다)",
            [
                context["store"].add(
                    evidence.disclosure_item(
                        context["corp_code"], evidence.disclosure_view(reports[0])
                    )
                )
            ],
        )

    pieces = [
        context["store"].add(
            evidence.disclosure_item(
                context["corp_code"], evidence.disclosure_view(report)
            )
        )
        for report in corrected
    ]
    listed = " · ".join(
        f"{report.get('fiscal_year') or '?'} {report.get('report_nm') or ''}".strip()
        for report in corrected
    )

    return _resolved(task, f"정정 공시 {len(corrected)}건 - {listed}", pieces)


def _resolve_news(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    """이미 수집된 뉴스를 다시 읽는다. 새로 검색하지 않는다."""
    news = context["collected"].get("news") or {}
    articles = news.get("articles") or []

    if not articles:
        return _gap(
            task,
            "수집된 뉴스가 없다. 뉴스는 공시가 아니므로 없다고 해서 사건이 없었다는 "
            "뜻은 아니다.",
        )

    picked = articles[:NEWS_LIMIT]
    pieces = [
        context["store"].add(evidence.news_item(context["corp_code"], article))
        for article in picked
    ]
    listed = " · ".join(
        f"{(article.get('title') or '').strip()}({article.get('site') or '?'})"
        for article in picked
    )

    return _resolved(task, f"기사 {len(picked)}건 - {listed}", pieces)


_RESOLVERS: dict[
    str, Callable[[sg.InvestigationTask, rules.Context], sg.InvestigationTask]
] = {
    sg.KIND_ACCOUNT: _resolve_account,
    sg.KIND_NOTE: _resolve_note,
    sg.KIND_SUMMARY: _resolve_summary,
    sg.KIND_SHAREHOLDER: _resolve_shareholder,
    sg.KIND_DISCLOSURE: _resolve_disclosure,
    sg.KIND_NEWS: _resolve_news,
}


def resolve(
    task: sg.InvestigationTask, context: rules.Context
) -> sg.InvestigationTask:
    """조사 하나를 실행한다. 실패해도 예외를 올리지 않는다.

    조사 한 건이 터졌다고 보고서 전체가 FAILED 가 되면 안 된다. 파서가 예상 못 한
    모양을 만나는 것은 우리 쪽 사정이고, 그 사실을 GAP 으로 적어 두면 읽는 사람이
    무엇이 빠졌는지 알 수 있다.
    """
    resolver = _RESOLVERS.get(task["kind"])
    if resolver is None:
        return _gap(task, f"조사 방법을 모른다: {task['kind']}")

    try:
        return resolver(task, context)
    except Exception as error:  # noqa: BLE001 - 조사 실패가 보고서를 죽이면 안 된다
        return _gap(task, f"조사 중 오류가 났다: {type(error).__name__}: {error}")


# ---------------------------------------------------------------------------
# [4] 진입점
# ---------------------------------------------------------------------------
def run(
    signals: list[sg.Signal], context: rules.Context
) -> list[sg.InvestigationTask]:
    """신호들 -> 중복을 없애고 우선순위대로 실행한 조사 큐."""
    tasks = prioritize(plan(signals))

    return [resolve(task, context) for task in tasks]
