"""이상징후를 탐지한다. 신호별 판단과 조사 연결.

신호의 골격은 signals.py 에, 조사 실행은 investigate.py 에, 근거 조각은 evidence.py 에
있다. 이 파일은 판정 결과(findings)와 재무 시계열(series)을 읽어 그 셋을 엮는다 -
infer.py 가 수집 결과에 대해 하는 일과 같다.

    [1] 도구      _pair · _delta · 파생 조각 색인
    [2] 탐지      신호별 함수
    [3] 진입점    run()

이미 있는 계산을 다시 하지 않는다

    infer._derive() 의 F-3(손익 전환)과 F-4(매출 증가·영업현금흐름 감소)는 이미
    "패턴이 있을 때만 발화하는" 탐지기다. 같은 계산을 여기서 다시 쓰면 두 곳이 갈라진다.
    그래서 F-3·F-4 는 **승격**한다 - 파생 조각을 찾아 그 result 문자열을 그대로 신호의
    trigger 로 쓰고, 조각 자체를 근거로 인용한다. F-5(부채비율)도 계산하지 않고 붙인다.

숫자는 반드시 파생 조각의 원문에 들어간다

    compose 의 후검증은 "문장의 숫자가 인용한 조각의 원문에 있어야 한다" 를 강제한다.
    신호가 "+43.7%" 라고 말하려면 그 문자열이 어떤 조각의 raw_content 안에 실제로
    있어야 하고, 그 자리는 evidence.derived(result=...) 뿐이다.

    그래서 trigger 문자열과 derived 조각의 result 를 **같은 문자열**로 만든다. 여기가
    이 파일에서 가장 틀리기 쉬운 지점이라 테스트로 못 박아 두었다.

임계값 판정을 문장에 적는다

    "부채가 급증했다" 가 아니라 "부채 증감률 +43.7% (기준 30%), 증감액이 자산총계의
    13.3% (기준 5%)" 라고 적는다. 그래야 읽는 사람이 오탐 여부를 스스로 판단할 수 있고,
    임계값을 조정할 때 무엇이 달라지는지 보인다.
"""

from collections.abc import Callable
from typing import Any, TypedDict

from app.domain.company.parser import notes as nt
from app.domain.company.parser import statements as st
from app.domain.company.parser.document_clean import normalize_parse_key
from app.domain.report import evidence, investigate, rules
from app.domain.report import signals as sg
from app.domain.report.rules import Verdict
from app.domain.report.signals import SignalDefinition

# 모든 재무 신호에 붙는 한계. 외감 감사보고서는 별도재무제표만 싣는다.
SEPARATE_ONLY = (
    "별도재무제표 기준이다. 종속기업이 있으면 연결 기준 수치는 이것과 다르다."
)

# 수집 범위의 한계. E-3 이 붙이는 경고와 같은 사실이다.
LIMITED_HISTORY = (
    "감사보고서 최근 3건만 확인했다. 그 이전 연도의 변화는 보이지 않는다."
)


# ---------------------------------------------------------------------------
# [1] 도구
# ---------------------------------------------------------------------------
class DetectResult(TypedDict):
    signals: list[sg.Signal]
    tasks: list[sg.InvestigationTask]
    coverage: dict[str, Any]


def _by_year(context: rules.Context, name: str) -> dict[int, dict[str, Any]]:
    return context["series"].get(name) or {}


def _years(by_year: dict[int, dict[str, Any]]) -> list[int]:
    """값이 있는 회계연도. 최신순. RECENT_YEARS 로 자르지 않는다.

    표시는 3개년이지만 탐지는 모인 4개년을 다 본다. 가장 오래된 해가 한 문서에만
    있어 표시에서 빠질 뿐, 추세를 볼 때는 그 해가 있어야 방향이 보인다 - 센트비
    2022년 매출 221.3억은 현재 보고서 어디에도 나오지 않는다.
    """
    return sorted(
        (year for year in by_year if by_year[year]["value"] is not None), reverse=True
    )


def _pair(
    context: rules.Context, name: str
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """최근 2개년 (당해, 직전). 둘 다 값이 있어야 한다. infer._pair 와 같은 규칙이다."""
    by_year = _by_year(context, name)
    years = _years(by_year)

    if len(years) < 2:
        return None

    return by_year[years[0]] | {"year": years[0]}, by_year[years[1]] | {
        "year": years[1]
    }


def _scale(context: rules.Context, year: int) -> float | None:
    """그 해의 자산총계. 증감액의 절대 기준을 회사 규모로 정규화할 때 쓴다."""
    cell = _by_year(context, "total_assets").get(year)
    if cell is None or not cell["value"]:
        return None

    return abs(cell["value"])


def _cite(context: rules.Context, *cells: dict[str, Any]) -> list[str]:
    """계정 셀들을 근거로 등록한다. 중복 ID 는 한 번만 남는다."""
    pieces: list[str] = []
    for cell in cells:
        piece = context["store"].add(
            evidence.account(cell["report"], cell["name"], cell["entry"])
        )
        if piece not in pieces:
            pieces.append(piece)

    return pieces


def _register(
    context: rules.Context,
    item: SignalDefinition,
    *,
    formula: str,
    trigger: str,
    based_on: list[str],
) -> str:
    """신호의 계산을 파생 조각으로 굳힌다.

    result 에 trigger 를 **그대로** 넣는다. 후검증이 신호 문장의 숫자를 여기서 찾기
    때문이다. 두 문자열이 갈라지는 순간 LLM 이 쓴 "+43.7%" 는 근거 없는 숫자가 되어
    문장째로 폐기된다.
    """
    return context["store"].add(
        evidence.derived(
            context["corp_code"],
            item.signal_id,
            label=item.label,
            formula=formula,
            result=trigger,
            based_on=based_on,
        )
    )


def _source(context: rules.Context) -> evidence.Source:
    latest = context["gate"]["latest"]
    if latest is None:
        return {
            "name": "DART 감사보고서",
            "as_of": None,
            "as_of_kind": None,
            "document_url": None,
            "rcept_no": None,
        }

    return evidence.report_source(latest)


def _derived_pieces(
    context: rules.Context, derived_ids: list[str]
) -> dict[str, list[evidence.Evidence]]:
    """F 블록 파생 조각을 rule_id 로 색인한다. 승격 신호가 이걸 뒤진다."""
    ledger = {piece["evidence_id"]: piece for piece in context["store"].dump()}
    index: dict[str, list[evidence.Evidence]] = {}

    for evidence_id in derived_ids:
        piece = ledger.get(evidence_id)
        if piece is None:
            continue
        index.setdefault(piece.get("rule_id") or "", []).append(piece)

    return index


def _promote(piece: evidence.Evidence) -> list[str]:
    """파생 조각과 그것이 딛고 선 원본을 함께 근거로 삼는다."""
    return [piece["evidence_id"], *(piece.get("based_on") or [])]


# ---------------------------------------------------------------------------
# [2] 탐지
# ---------------------------------------------------------------------------
def _operating_loss_continued(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """영업손실이 연속으로 났는가.

    순손실 지속을 따로 세지 않는다. 조사할 자료가 완전히 같아서 신호를 나누면 같은
    주석을 두 번 읽게 된다. 대신 순손익을 facts 에 함께 적어 둘 다 보이게 한다.
    """
    by_year = _by_year(context, "operating_income")
    years = _years(by_year)

    streak = 0
    for year in years:
        if by_year[year]["value"] >= 0:
            break
        streak += 1

    if streak < sg.THRESHOLD_LOSS_STREAK:
        return None

    losing = years[:streak]
    trigger = (
        f"영업손실이 {streak}개년 연속이다 "
        f"(기준 {sg.THRESHOLD_LOSS_STREAK}개년). "
        f"{losing[-1]}년부터 {losing[0]}년까지 한 해도 영업이익을 내지 못했다."
    )

    cells = [by_year[year] for year in losing]
    net = _by_year(context, "net_income")
    cells += [net[year] for year in losing if year in net]

    pieces = _cite(context, *cells)
    pieces.append(
        _register(
            context,
            item,
            formula="영업이익 부호가 음수인 해가 최신 연도부터 몇 해 이어지는가",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=sg.year_facts(by_year, losing, "영업이익")
        + sg.year_facts(net, losing, "당기순이익"),
        evidence_ids=pieces,
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


def _profit_sign_turned(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """손익 전환. F-3 을 승격시킨다 - 같은 계산을 두 번 쓰지 않는다."""
    found = index.get("F-3")
    if not found:
        return None

    piece = found[0]
    trigger = f"당기순손익의 부호가 바뀌었다. {piece['raw_content']}"
    based = _promote(piece)

    return sg.signal(
        item,
        trigger=trigger,
        facts=[piece["raw_content"]],
        evidence_ids=based,
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


def _sales_up_cfo_down(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """매출과 영업현금흐름이 반대로 움직였는가.

    두 갈래다. (가) F-4 가 이미 잡은 '매출 증가 + 영업CF 감소' 를 승격시킨다.
    (나) F-4 가 보지 않는 '영업이익 흑자인데 영업CF 는 음수' 를 새로 잡는다.
    """
    found = index.get("F-4")
    if found:
        piece = found[0]
        trigger = f"매출과 영업활동현금흐름이 반대 방향으로 움직였다. {piece['raw_content']}"

        return sg.signal(
            item,
            trigger=trigger,
            facts=[piece["raw_content"]],
            evidence_ids=_promote(piece),
            source=_source(context),
            warnings=[SEPARATE_ONLY],
        )

    operating = _pair(context, "operating_income")
    cash = _pair(context, "operating_cash_flow")
    if operating is None or cash is None:
        return None

    op_now, _op_prev = operating
    cf_now, _cf_prev = cash
    if not (op_now["value"] > 0 and cf_now["value"] < 0):
        return None

    trigger = (
        f"{op_now['year']}년 영업이익은 {sg.won(op_now['value'])} 흑자인데 "
        f"영업활동현금흐름은 {sg.won(cf_now['value'])} 로 음수다. "
        "이익이 현금으로 들어오지 않았다."
    )

    pieces = _cite(context, op_now, cf_now)
    pieces.append(
        _register(
            context,
            item,
            formula="영업이익 부호 vs 영업활동현금흐름 부호 (같은 해)",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=[
            f"{op_now['year']}년 영업이익 {sg.won(op_now['value'])}",
            f"{cf_now['year']}년 영업활동현금흐름 {sg.won(cf_now['value'])}",
        ],
        evidence_ids=pieces,
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


def _debt_surge(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """부채총계가 급증했는가. 증감률과 규모 대비 증감액을 함께 요구한다."""
    pair = _pair(context, "total_liabilities")
    if pair is None:
        return None

    now, prev = pair
    if not prev["value"]:
        return None

    delta = now["value"] - prev["value"]
    if delta <= 0:
        return None

    rate = delta / abs(prev["value"])
    scale = _scale(context, now["year"])
    if scale is None:
        return None

    weight = delta / scale
    if rate < sg.THRESHOLD_DEBT_SURGE_RATE:
        return None
    if weight < sg.THRESHOLD_DEBT_SURGE_OF_ASSETS:
        return None

    trigger = (
        f"부채총계가 {prev['year']}년 {sg.won(prev['value'])}에서 "
        f"{now['year']}년 {sg.won(now['value'])}로 {sg.won(delta)} 늘었다. "
        f"증감률 {sg.pct(rate)} (기준 {sg.share(sg.THRESHOLD_DEBT_SURGE_RATE)}), "
        f"증감액은 자산총계의 {sg.share(weight)} "
        f"(기준 {sg.share(sg.THRESHOLD_DEBT_SURGE_OF_ASSETS)})."
    )

    pieces = _cite(context, prev, now)
    # F-5 부채비율은 이미 계산되어 있다. 다시 구하지 않고 붙이기만 한다.
    ratio_pieces = [piece["evidence_id"] for piece in index.get("F-5", [])]
    pieces.append(
        _register(
            context,
            item,
            formula="부채총계 전년 대비 증감률 AND 증감액 / 당해 자산총계",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=[
            f"{prev['year']}년 부채총계 {sg.won(prev['value'])}",
            f"{now['year']}년 부채총계 {sg.won(now['value'])}",
            f"증감액 {sg.won(delta)} ({sg.eok(delta)})",
            f"증감률 {sg.pct(rate)}",
            f"자산총계 대비 {sg.share(weight)}",
        ],
        evidence_ids=pieces + [p for p in ratio_pieces if p not in pieces],
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


def _financing_cf_surge(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """재무활동현금흐름이 급증했는가.

    증가액과 당해 금액 **둘 다** 자산총계의 10% 를 넘어야 한다. 증가액만 보면
    전년이 크게 음수였다가 올해 소액 양수인 경우에도 신호가 뜬다 - 그건 조달이 아니라
    상환이 끝난 것이다.
    """
    pair = _pair(context, "financing_cash_flow")
    if pair is None:
        return None

    now, prev = pair
    if now["value"] <= 0:
        return None

    increase = now["value"] - prev["value"]
    if increase <= 0:
        return None

    scale = _scale(context, now["year"])
    if scale is None:
        return None

    grew = increase / scale
    size = now["value"] / scale
    if grew < sg.THRESHOLD_FINANCING_OF_ASSETS:
        return None
    if size < sg.THRESHOLD_FINANCING_OF_ASSETS:
        return None

    trigger = (
        f"재무활동현금흐름이 {prev['year']}년 {sg.won(prev['value'])}에서 "
        f"{now['year']}년 {sg.won(now['value'])}로 {sg.won(increase)} 늘었다. "
        f"당해 조달액은 자산총계의 {sg.share(size)}, 증가액은 {sg.share(grew)} "
        f"(기준 {sg.share(sg.THRESHOLD_FINANCING_OF_ASSETS)}). "
        "무엇으로 조달했는지는 차입금·자본금 조사가 가른다."
    )

    pieces = _cite(context, prev, now)
    pieces.append(
        _register(
            context,
            item,
            formula="재무활동현금흐름 증가액 / 당해 자산총계 AND 당해 금액 / 당해 자산총계",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=[
            f"{prev['year']}년 재무활동현금흐름 {sg.won(prev['value'])}",
            f"{now['year']}년 재무활동현금흐름 {sg.won(now['value'])} ({sg.eok(now['value'])})",
            f"증가액 {sg.won(increase)}",
            f"자산총계 대비 {sg.share(size)}",
        ],
        evidence_ids=pieces,
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


def _capital_impairment(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """자본잠식. 임계값이 없다 - 자본총계와 자본금의 대소가 곧 사실이다."""
    equity = _by_year(context, "total_equity")
    capital = _by_year(context, "capital_stock")
    shared = sorted(
        (
            year
            for year in set(equity) & set(capital)
            if equity[year]["value"] is not None and capital[year]["value"] is not None
        ),
        reverse=True,
    )

    if not shared:
        return None

    year = shared[0]
    equity_value = equity[year]["value"]
    capital_value = capital[year]["value"]

    if equity_value <= 0:
        kind = "완전자본잠식"
        detail = "자본총계가 0 이하다."
    elif equity_value < capital_value:
        kind = "부분자본잠식"
        rate = 1 - equity_value / capital_value
        detail = f"자본총계가 자본금보다 작다. 잠식률 {sg.share(rate)}."
    else:
        return None

    trigger = (
        f"{year}년 자본총계 {sg.won(equity_value)}, 자본금 {sg.won(capital_value)} - "
        f"{kind}. {detail}"
    )

    pieces = _cite(context, equity[year], capital[year])
    pieces.append(
        _register(
            context,
            item,
            formula="자본총계 <= 0 (완전) 또는 자본총계 < 자본금 (부분)",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=[
            f"{year}년 자본총계 {sg.won(equity_value)}",
            f"{year}년 자본금 {sg.won(capital_value)}",
        ],
        evidence_ids=pieces,
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


# 라벨로 찾을 투자성 증권. ACODE 를 실측하지 못한 것들이다.
_CB_LABELS = ("전환사채", "상환전환우선주", "신주인수권부사채")


def _terms_in_note_tables(
    context: rules.Context,
) -> tuple[dict[str, Any], int] | None:
    """주석 **표 안**에서 투자성 증권을 찾는다. (하위항목, 블록 인덱스) 또는 None.

    왜 제목이 아니라 표를 보는가 (2026-09-06 실측으로 드러난 오탐)

        C-3 은 하위항목 제목 앞 30자만 본다. 본문 전역 검색이 지나가는 말에 걸린다는
        실측 근거가 있어서 그렇게 정했고, 그 판단 자체는 옳다.

        그런데 센트비의 상환전환우선주 조건은 주석 12 '자본' 의 **네 번째 표**에 통째로
        들어 있다 - 우선주의 종류(상환전환우선주식), 배당률, 잔여재산분배, 전환권(발행일
        후 10년, 자동전환), 전환조건. 제목은 "자본(1) 당기말과 전기말 현재 자본금의
        구성내역은…" 이라 어떤 키워드에도 걸리지 않는다.

        그래서 C-3 이 ABSENT 가 되고, 그 위에 세운 PREFERRED_TERMS_UNKNOWN 이
        "조건을 공시에서 확인할 수 없다" 는 **사실과 반대되는 주장**을 만들었다.

    본문 전역 검색의 오탐 위험은 어떻게 피하는가

        키워드를 notes.TOPICS["convertible_bond"] 에서 그대로 빌려 쓴다. 전환사채·
        신주인수권부사채·전환우선주는 증권의 고유명사라 지나가는 말로 나오기 어렵다.
        실측 오탐 사례였던 '충당' 같은 일반 명사와는 성격이 다르다.

        문단이 아니라 **표만** 본다. 조건은 표로 오고, 문단에서의 언급은 "…에 대해서는
        주석 12 참조" 같은 참조인 경우가 많다.
    """
    keywords = nt.TOPICS["convertible_bond"]

    for subsection in context["notes"]["subsections"]:
        for index, block in enumerate(subsection["blocks"]):
            if block.get("type") != "table":
                continue

            text = normalize_parse_key(evidence.flatten_table(block))
            if any(keyword in text for keyword in keywords):
                return subsection, index

    return None


def _cb_found(
    item: SignalDefinition, context: rules.Context, findings: dict, index: dict
) -> sg.Signal | None:
    """투자성 증권을 세 경로로 찾는다. 하나라도 걸리면 신호다.

    주석(C-3)만 보면 재무상태표에 계정으로 잡힌 사채를 놓치고, 계정만 보면 표준
    ACODE 가 없는 전환사채를 놓친다. 직방은 신주인수권부사채가 계정(116103000)으로
    잡히는데 실측 5개사 중 그 회사뿐이라 코드 하나만 믿을 수 없다.
    """
    latest = context["gate"]["latest"]
    routes: list[str] = []
    pieces: list[str] = []
    facts: list[str] = []

    note = findings.get("C-3") or {}
    if note.get("verdict") == Verdict.CONFIRMED.value:
        routes.append("주석")
        pieces += list(note.get("evidence_ids") or [])
        facts.append(f"주석에서 확인: {note.get('value')}")

    by_year = _by_year(context, "bond_with_warrant")
    years = _years(by_year)
    if years:
        routes.append("재무상태표 계정")
        pieces += _cite(context, *(by_year[year] for year in years))
        facts += sg.year_facts(by_year, years, "신주인수권부사채")

    if latest is not None:
        for entry in st.find_accounts_by_label(
            latest["clean"], st.BALANCE_SHEET, _CB_LABELS
        ):
            # bond_with_warrant 로 이미 잡은 계정은 건너뛴다.
            if entry["code"] == (by_year[years[0]]["entry"]["code"] if years else None):
                continue
            routes.append("재무상태표 라벨")
            pieces.append(
                context["store"].add(
                    evidence.account(latest, "bond_with_warrant", entry)
                )
            )
            current = (entry["periods"].get(st.CURRENT_PERIOD) or {}).get("value")
            if current is not None:
                facts.append(f"{entry['label']} {sg.won(current)}")

    # 주석 표 경로. C-3 이 제목만 보느라 놓친 것을 여기서 줍는다(센트비 실측).
    in_tables = _terms_in_note_tables(context)
    if in_tables is not None and latest is not None:
        subsection, index = in_tables
        routes.append("주석 표")
        pieces.append(
            context["store"].add(evidence.note_block(latest, subsection, index))
        )
        facts.append(f"주석 {subsection['number']}. {subsection['head']} 의 표에서 확인")

    if not routes:
        return None

    unique_routes = list(dict.fromkeys(routes))
    trigger = (
        f"전환사채·신주인수권부사채·전환우선주에 해당하는 항목을 찾았다 "
        f"(경로: {', '.join(unique_routes)}). 발행금액·발행일·전환조건은 주석 원문에서 "
        "확인해야 한다."
    )

    pieces = list(dict.fromkeys(pieces))
    pieces.append(
        _register(
            context,
            item,
            formula="주석 C-3 판정 OR 재무상태표 사채 계정 OR 계정 라벨 일치",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=facts,
        evidence_ids=pieces,
        source=_source(context),
        warnings=[SEPARATE_ONLY],
    )


def _restatement_detected(
    item: SignalDefinition, context: rules.Context, _: dict, index: dict
) -> sg.Signal | None:
    """같은 해의 값이 문서마다 다른가.

    build_series 는 겹치는 해를 최신 문서로 덮어쓰면서 "두 값의 차이를 계산하거나 어느
    쪽이 옳은지 판단하지 않는다" 고 못 박았다. 그 규율을 지킨다 - 우리도 판단하지 않고
    **차이가 있다는 사실만** 적는다. 어느 쪽이 맞는지는 회사가 답할 일이다.

    재분류(계정을 옮김)와 재작성(값을 바꿈)을 우리는 구분하지 못한다. 그래서 항등식
    확인을 조사 항목으로 함께 건다.
    """
    reports = context["gate"]["reports"]
    if len(reports) < 2:
        return None

    # {회계연도: {계정: [(rcept_no, 값)]}}
    seen: dict[int, dict[str, list[tuple[str, float]]]] = {}

    for report in reports:
        fiscal = report.get("fiscal_year") or ""
        if len(fiscal) < 4 or not fiscal[:4].isdigit():
            continue
        base = int(fiscal[:4])

        for name, entry in st.extract_financials(report["clean"]).items():
            if name not in st.CORE_ACCOUNTS:
                continue
            for period, offset in ((st.CURRENT_PERIOD, 0), (st.PRIOR_PERIOD, 1)):
                value = (entry.get("periods") or {}).get(period)
                if value is None or value["value"] is None:
                    continue
                seen.setdefault(base - offset, {}).setdefault(name, []).append(
                    (report["rcept_no"], value["value"])
                )

    changes: list[str] = []
    touched: list[str] = []

    for year in sorted(seen, reverse=True):
        for name, entries in sorted(seen[year].items()):
            values = {value for _, value in entries}
            if len(values) < 2:
                continue

            (_, older), (_, newer) = entries[0], entries[-1]
            if not older:
                continue
            if abs(newer - older) / abs(older) < sg.THRESHOLD_RESTATEMENT_RATE:
                continue

            label = evidence.ACCOUNT_LABELS.get(name, name)
            changes.append(
                f"{year}년 {label} {sg.won(older)} -> {sg.won(newer)} "
                f"(차이 {sg.won(abs(newer - older))})"
            )
            cell = (_by_year(context, name) or {}).get(year)
            if cell is not None:
                touched += _cite(context, cell)

    if not changes:
        return None

    trigger = (
        f"같은 회계연도의 수치가 감사보고서마다 다르다 ({len(changes)}건). "
        f"{' / '.join(changes)}. 재분류인지 재작성인지는 이 자료만으로 가릴 수 없다."
    )

    pieces = list(dict.fromkeys(touched)) or _cite(
        context, *[cell for cell in [_by_year(context, "total_assets").get(max(seen))] if cell]
    )
    if not pieces:
        return None

    pieces.append(
        _register(
            context,
            item,
            formula="문서 간 같은 (회계연도, 계정) 값 대조. 차이 >= 이전값의 1%",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=changes,
        evidence_ids=pieces,
        source=_source(context),
        warnings=[SEPARATE_ONLY, LIMITED_HISTORY],
    )


def _preferred_terms_unknown(
    item: SignalDefinition, context: rules.Context, findings: dict, index: dict
) -> sg.Signal | None:
    """우선주 비중이 큰데 그 조건을 확인할 주석이 없는가.

    "확인했더니 알 수 없다" 를 신호로 만드는 유일한 규칙이다. 우선주가 자본금의 상당
    부분인데 상환·전환 조건이 공시에 없으면, 그 자본이 실질적으로 부채인지 자본인지
    판단할 수 없다. 비상장 기업 분석에서 이보다 중요한 공백은 드물다.

    C-3 이 ABSENT 일 때만 발화한다. EXTRACTION_FAILED 면 우리가 못 읽은 것이므로
    회사가 안 썼다고 말할 수 없다 - note_verdict 가 그 둘을 가르는 이유가 여기서 쓰인다.
    """
    note = findings.get("C-3") or {}
    if note.get("verdict") != Verdict.ABSENT.value:
        return None

    # C-3 이 ABSENT 여도 그것만 믿고 "없다" 고 말하지 않는다. 제목에 안 걸렸을 뿐
    # 표 안에 조건이 통째로 들어 있을 수 있다 - 센트비가 정확히 그 경우였고, 이 확인이
    # 없을 때 이 신호는 사실과 반대되는 주장을 만들었다(2026-09-06 실측).
    #
    # 조건을 찾았으면 공백이 아니므로 침묵한다. 그 사실은 CB_FOUND 가 말한다.
    if _terms_in_note_tables(context) is not None:
        return None

    preferred = _by_year(context, "preferred_capital")
    capital = _by_year(context, "capital_stock")
    shared = sorted(
        (
            year
            for year in set(preferred) & set(capital)
            if preferred[year]["value"] and capital[year]["value"]
        ),
        reverse=True,
    )

    if not shared:
        return None

    year = shared[0]
    preferred_value = preferred[year]["value"]
    capital_value = capital[year]["value"]
    weight = preferred_value / capital_value

    if weight < sg.THRESHOLD_PREFERRED_OF_CAPITAL:
        return None

    trigger = (
        f"{year}년 우선주자본금 {sg.won(preferred_value)}이 자본금 "
        f"{sg.won(capital_value)}의 {sg.share(weight)}를 차지한다 "
        f"(기준 {sg.share(sg.THRESHOLD_PREFERRED_OF_CAPITAL)}). "
        "그런데 전환·상환 조건을 담은 주석은 결번 없이 확인한 목차에 없다. "
        "이 우선주가 상환 의무를 지는지 공시만으로는 알 수 없다."
    )

    pieces = _cite(context, preferred[year], capital[year])
    pieces += [
        piece["evidence_id"] for piece in index.get("F-1", []) + index.get("F-2", [])
    ]
    pieces = list(dict.fromkeys(pieces))
    pieces.append(
        _register(
            context,
            item,
            formula="우선주자본금 / 자본금 AND 주석 C-3 판정이 ABSENT",
            trigger=trigger,
            based_on=pieces,
        )
    )

    return sg.signal(
        item,
        trigger=trigger,
        facts=[
            f"{year}년 우선주자본금 {sg.won(preferred_value)}",
            f"{year}년 자본금 {sg.won(capital_value)}",
            f"우선주 비중 {sg.share(weight)}",
            "전환사채·전환우선주 주석: 확인했으나 없음(ABSENT)",
        ],
        evidence_ids=pieces,
        source=_source(context),
        warnings=[
            (
                "조건을 확인하지 못한 것이지 불리한 조건이 있다는 뜻이 아니다. "
                "등기부·투자계약은 이 시스템의 수집 범위 밖이다."
            )
        ],
    )


_DETECTORS: dict[
    str,
    Callable[[SignalDefinition, rules.Context, dict, dict], sg.Signal | None],
] = {
    "OPERATING_LOSS_CONTINUED": _operating_loss_continued,
    "PROFIT_SIGN_TURNED": _profit_sign_turned,
    "SALES_UP_CFO_DOWN": _sales_up_cfo_down,
    "DEBT_SURGE": _debt_surge,
    "FINANCING_CF_SURGE": _financing_cf_surge,
    "CAPITAL_IMPAIRMENT": _capital_impairment,
    "CB_FOUND": _cb_found,
    "RESTATEMENT_DETECTED": _restatement_detected,
    "PREFERRED_TERMS_UNKNOWN": _preferred_terms_unknown,
}


# ---------------------------------------------------------------------------
# [3] 진입점
# ---------------------------------------------------------------------------
def _coverage(context: rules.Context) -> dict[str, Any]:
    """무엇을 평가할 수 있었는가.

    이것이 없으면 "이상징후 0건" 이 거짓말이 된다. IFRS 채택사(실측 8.3%)와 의견거절
    (5.0%) 문서는 재무제표가 표로 오지 않아 series 가 비고, 그러면 재무 신호는 구조적
    으로 0개다. 그 0 과 "멀쩡한 회사라 0" 은 완전히 다른 사실이다.
    """
    years = _years(_by_year(context, "total_assets"))

    return {
        "audited": context["gate"]["audited"],
        "reports": len(context["gate"]["reports"]),
        "financial_years": years,
        "notes_parsed": context["notes"]["parsed"],
        "note_gaps": list(context["notes"]["gaps"]),
        "summary_fallback": context["gate"]["summary_fallback"],
    }


def run(
    context: rules.Context, findings: dict[str, rules.Finding], derived: list[str]
) -> DetectResult:
    """판정 결과 + 시계열 -> 이상징후와 그에 딸린 조사 결과.

    infer.run() 이 _derive() 를 끝낸 뒤에 부른다. F-3·F-4·F-5 파생 조각이 이미
    등록되어 있어야 승격 신호가 그것을 찾을 수 있기 때문이다.

    조사는 신호가 하나라도 있을 때만 돈다. 신호가 없으면 조사할 이유도 없다.
    """
    index = _derived_pieces(context, derived)

    signals: list[sg.Signal] = []
    for definition in sg.SIGNALS:
        detector = _DETECTORS[definition.signal_id]
        found = detector(definition, context, findings, index)
        if found is not None:
            signals.append(found)

    tasks = investigate.run(signals, context) if signals else []

    return {"signals": signals, "tasks": tasks, "coverage": _coverage(context)}
