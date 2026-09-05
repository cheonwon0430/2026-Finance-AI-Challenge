"""감사보고서 주석을 하위 항목으로 쪼갠다.

document_clean 은 주석 전체를 섹션 하나로 준다. 실측하면 블록이 100~170개짜리
한 덩어리라, "차입금 주석이 있는가" 를 물으면 그 전부를 훑어야 한다. 여기서 번호가
붙은 하위 항목으로 나눠 목차를 만든다.

목차를 만드는 진짜 이유는 검색 편의가 아니라 판정이다. 하위 항목을 전부 세어 둬야
"소송 항목이 없다" 를 단정할 수 있다. 목차가 없으면 못 찾은 것과 없는 것이 같아진다.

    [1] 주석 섹션 찾기
    [2] 하위 항목 분할    번호 연속성으로 스캔한다
    [3] 주제 매칭        표기 흔들림을 흡수한다
    [4] 주주현황 표      오탐 배제가 핵심이다

왜 문단 시작 매칭이 아닌가 (2026-09-03 실측, 픽스처 3건)

    처음에는 '^\\d+\\.' 로 문단 첫머리만 봤다. 그랬더니 두 건에서 항목을 놓쳤다.

        (주)핀샷        "...66,462천원입니다. 12. 포인트충당부채 당기 및 전기 중..."
        주식회사 업스테이지 "...질권이 설정되어 있습니다.6. 지분법적용투자주식(1) 당기말과..."

    DART 원문에서 앞 항목의 마지막 문장과 다음 항목의 제목이 같은 P 태그에 들어
    있다. 문단 첫머리만 보면 번호가 통째로 사라진다.

    그래서 문단 안쪽까지 훑되, 아무 숫자나 잡지 않도록 **다음에 올 번호만** 찾는다.
    1을 찾았으면 다음은 2, 그다음은 3이다. 금액이나 날짜에 섞인 '12.' 같은 것은
    순서가 맞지 않아 저절로 걸러진다.

왜 표기 목록을 하드코딩하는가

    같은 항목의 제목이 회사마다 다르다(실측).

        개요        1.당사의 개요 / 1.회사의 개요 / 1.일반사항
        특수관계자   20.특수관계자와의 거래 / 11.특수관계자 거래
        우발채무     21.우발부채 및 약정사항 / 17.우발채무와 약정사항 / 19.우발채무 및 약정사항

    그래서 완전일치로는 안 되고 부분 문자열로 본다. 대상이 그 문서의 하위 항목
    8~21개뿐인 닫힌 목록이라 전수 비교이고, 못 찾으면 '없다' 고 말할 수 있다.
"""

import re
from typing import Any

from app.domain.company.parser.document_clean import normalize_parse_key

# ---------------------------------------------------------------------------
# [1] 주석 섹션 찾기
# ---------------------------------------------------------------------------
NOTES_TITLE = "주석"

# 하위 항목의 제목과 본문은 한 문단에 붙어 온다(실측). 잘라 쓰는 길이를 두 개 둔다.
#
#     HEAD_WINDOW   60자. 사람이 목차에서 읽을 조각이라 문맥이 조금 있는 편이 낫다
#     TITLE_WINDOW  30자. 주제를 매칭할 때만 쓴다
#
# 매칭 창을 따로 좁힌 이유가 있다. 제목은 번호 바로 뒤에서 시작하므로 30자면 실측한
# 가장 긴 제목('금융부채의 유동성위험 관리방법 및 종류별 만기 분석', 27자)도 들어간다.
# 반대로 60자를 그대로 쓰면 본문 앞부분이 딸려 들어와, 다른 항목이 지나가는 말로 꺼낸
# '소송' 같은 단어에 걸린다.
HEAD_WINDOW = 60
TITLE_WINDOW = 30


def find_notes_section(clean: dict[str, Any]) -> dict[str, Any] | None:
    """정리 결과에서 주석 섹션을 찾는다. 없으면 None."""
    for section in clean.get("sections") or []:
        if NOTES_TITLE in normalize_parse_key(section.get("title") or ""):
            return section

    return None


# ---------------------------------------------------------------------------
# [2] 하위 항목 분할
# ---------------------------------------------------------------------------
# 번호 앞뒤를 모두 막되, 앞의 마침표는 가려서 막아야 한다. 실측으로 양쪽 다 당했다.
#
#     뒤에 숫자   '2.2 재무제표 작성기준'      -> 2번 항목으로 열면 안 된다
#     앞에 '숫자.' '2.5. 대손충당금'            -> 5번 항목으로 열면 안 된다  ((주)핀샷)
#     앞에 '글자.' '...있습니다.6. 지분법투자'  -> 6번 항목이 맞다          (업스테이지)
#
# 마지막 줄이 함정이다. 앞 문자가 점이라는 이유로 싸잡아 막으면 문장 끝에 바로 붙어
# 나온 진짜 항목을 잃는다. 그래서 '점' 이 아니라 '숫자 뒤의 점' 만 배제한다.
#
#     (?<![0-9])     앞 한 글자가 숫자면 제외        '12' 의 2 를 2번으로 읽지 않는다
#     (?<![0-9]\.)   앞 두 글자가 '숫자.' 면 제외    '2.5.' 의 5 를 5번으로 읽지 않는다
_MAX_SKIP = 3  # 회사가 번호를 건너뛰었을 수 있으니 이만큼은 앞을 내다본다


def _header_pattern(number: int) -> re.Pattern[str]:
    return re.compile(rf"(?<![0-9])(?<![0-9]\.){number}\.\s*(?=[^\s0-9])")


def _head_of(text: str) -> str:
    """항목 제목으로 쓸 앞부분. 제목과 본문이 붙어 있어 길이로 자른다."""
    return " ".join(text[:HEAD_WINDOW].split())


def split_subsections(section: dict[str, Any]) -> list[dict[str, Any]]:
    """주석 섹션 -> 번호가 붙은 하위 항목 목록.

    각 항목은 자기 시작 블록의 인덱스를 들고 있는다. 근거 앵커가 그 인덱스를 쓴다.
    표는 바로 앞 항목에 딸린 것으로 본다 - 주석의 표는 항상 설명 문단 뒤에 온다.
    """
    blocks = section.get("blocks") or []
    subsections: list[dict[str, Any]] = []
    expected = 1

    for index, block in enumerate(blocks):
        if block.get("type") != "paragraph":
            # 표는 열려 있는 항목에 붙인다
            if subsections:
                subsections[-1]["blocks"].append(block)
            continue

        text = block.get("text") or ""
        cursor = 0

        # 한 문단 안에 여러 항목이 이어 붙어 있을 수 있어 끝까지 훑는다
        while cursor < len(text):
            found = None

            for candidate in range(expected, expected + _MAX_SKIP + 1):
                match = _header_pattern(candidate).search(text, cursor)
                if match is not None and (found is None or match.start() < found[1].start()):
                    found = (candidate, match)

            if found is None:
                break

            number, match = found

            # 직전 항목의 본문은 이 헤더 앞에서 끝난다
            if subsections:
                subsections[-1]["text"] += " " + text[cursor : match.start()].strip()

            body = text[match.end() :]
            subsections.append(
                {
                    "number": number,
                    "head": _head_of(body),
                    "text": body,
                    "blocks": [block],
                    "block_index": index,
                }
            )
            expected = number + 1
            cursor = match.end()

        else:
            continue

        # 헤더를 못 찾은 나머지 문단은 열려 있는 항목의 본문이다
        if subsections and cursor < len(text):
            subsections[-1]["text"] += " " + text[cursor:].strip()

    return subsections


def numbering_gaps(subsections: list[dict[str, Any]]) -> list[int]:
    """빠진 번호. 비어 있지 않으면 항목을 놓쳤을 수 있다는 신호다.

    회사가 번호를 실제로 건너뛴 경우와 우리가 못 읽은 경우를 구분할 수단이 없으므로,
    부재(ABSENT)를 단정하기 전에 이 값을 확인해야 한다.
    """
    if not subsections:
        return []

    numbers = {item["number"] for item in subsections}

    return [n for n in range(1, max(numbers) + 1) if n not in numbers]


# ---------------------------------------------------------------------------
# [3] 주제 매칭
# ---------------------------------------------------------------------------
# 값은 부분 문자열이다. 공백을 지운 뒤 비교하므로 '특수관계자 거래' 와
# '특수관계자와의거래' 가 같은 키워드에 걸린다.
#
# 부분 문자열로 충분한가 (2026-09-05 실측, 감사보고서 73건 / 주석 분할 성공 67건)
#
#     제목 표기는 회사마다 갈린다. 특수관계자만 해도 '특수관계자거래'(8) /
#     '특수관계자와의거래'(7) / '특수관계자'(5) / '특수관계자와의주요거래내용'(3) 이고
#     차입금도 '차입금'(13) / '장기차입금'(3) / '장ㆍ단기차입금'(2) 로 갈린다.
#
#     그런데 전부 핵심 어휘를 품고 있어서 normalize_parse_key + 부분일치가 그 변형을
#     그대로 흡수한다. 특수관계자 66/67 · 차입금 62/67 · 계속기업 4/67 · 소송 2/67 이고
#     놓친 것이 0건이다. 의미 매칭(LLM)이 필요한 사례는 한 건도 나오지 않았다.
TOPICS: dict[str, tuple[str, ...]] = {
    "overview": ("회사의개요", "당사의개요", "일반사항"),
    "borrowings": ("차입금",),
    "related_party": ("특수관계자",),
    # '우발' 만 보면 52/67. 담보제공·지급보증 주석 9건을 놓치는데 그 9건은 전부
    # '담보제공자산등' / '지급보증' 류로 우발채무·소송·보증 범위 안이다 -> 61/67.
    #
    # '충당' 은 넣지 않는다. 넣으면 63/67 이 되지만 퇴직급여충당부채 8건과
    # 대손충당금 2건이 딸려 온다. 둘 다 확정부채·평가충당금이라 우발채무가 아니다.
    "contingency": ("우발", "지급보증", "담보제공"),
    "capital": ("자본금", "자본"),
    "litigation": ("소송",),
    # '전환우선주' 는 '상환전환우선주' 의 부분 문자열이라 둘 다 걸린다 (2 -> 3건).
    "convertible_bond": ("전환사채", "신주인수권부사채", "전환우선주"),
    "going_concern": ("계속기업",),
}


def find_subsection(
    subsections: list[dict[str, Any]], topic: str
) -> dict[str, Any] | None:
    """주제에 해당하는 하위 항목을 찾는다. 없으면 None(= 확인했으나 없음).

    제목 부분만 본다. 본문 전체를 보면 다른 항목이 지나가는 말로 언급한 것까지
    걸린다 - 실측 사례로 '충당부채' 는 주석이 아니라 재무상태표 세부항목에서도
    잡힌다(dump_extracted/_verify_45_raw.md).
    """
    keywords = TOPICS.get(topic)
    if not keywords:
        raise KeyError(f"알 수 없는 주제: {topic}")

    for item in subsections:
        title = normalize_parse_key(item["head"])[:TITLE_WINDOW]
        if any(keyword in title for keyword in keywords):
            return item

    return None


def table_of_contents(subsections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """번호와 제목만 추린 목차. 부재 판정의 근거로 보고서에 싣는다."""
    return [
        {"number": item["number"], "head": item["head"]} for item in subsections
    ]


# ---------------------------------------------------------------------------
# [4] 주주현황 표
# ---------------------------------------------------------------------------
# 오탐 배제가 이 절의 전부다 (2026-09-03 실측).
#
#     주식회사 업스테이지 주석에는 '지분율' 을 가진 표가 3개 있다.
#
#         주주명 | 보통주 | 우선주 | 합계 | 지분율(%)          <- 주주현황
#         피투자회사명 | 주식수 | 지분율(%) | 취득원가 | ...    <- 종속기업 투자내역
#
#     뒤 둘은 "회사가 투자한 곳" 이라 방향이 정반대다. 걸러내지 못하면
#     "업스테이지의 주주는 UPSTAGE AI, INC. 100%" 라는 문장이 나온다.
#
# 그래서 '지분율' 로 찾지 않는다. '주주명' 을 요구하고 '피투자회사' 를 배제한다.
SHAREHOLDER_REQUIRED = "주주명"
SHAREHOLDER_EXCLUDED = ("피투자회사",)

# 열 위치는 회사마다 다르다. 고정 인덱스로 읽으면 반드시 깨진다.
#
#     (주)센트비      주식의 종류 | 주주명 | 소유주식수 | 지분율     (4열, 행으로 종류 구분)
#     주식회사 업스테이지 주주명 | 보통주 | 우선주 | 합계 | 지분율(%)  (5열, 열로 종류 구분)
_HOLDER_COLUMN = "주주명"
_RATIO_COLUMN = "지분율"
_SHARES_COLUMNS = ("합계", "소유주식수", "주식수")
_CLASS_COLUMN = "주식의종류"

# 소계·합계 행. 사람 이름이 아니므로 주주로 세지 않되 버리지도 않는다.
_TOTAL_LABELS = ("합계", "소계", "계")


def _header_cells(block: dict[str, Any]) -> list[str]:
    """열 이름 행. 헤더가 여러 줄이면 마지막 줄이 실제 열 이름이다."""
    header = block.get("header")
    if header:
        return list(header[-1])

    # 헤더가 없는 표도 있다. 그때만 첫 행을 열 이름으로 본다.
    rows = block.get("rows") or []

    return list(rows[0]) if rows else []


def is_shareholder_table(block: dict[str, Any]) -> bool:
    """주주현황 표인가. 열 이름만 보고 판정한다."""
    if block.get("type") != "table":
        return False

    cells = [normalize_parse_key(cell) for cell in _header_cells(block)]
    if not any(SHAREHOLDER_REQUIRED in cell for cell in cells):
        return False

    return not any(
        excluded in cell for cell in cells for excluded in SHAREHOLDER_EXCLUDED
    )


def find_shareholder_tables(section: dict[str, Any]) -> list[dict[str, Any]]:
    """주석 섹션에서 주주현황 표를 모두 찾는다. 없으면 빈 리스트."""
    return [b for b in (section.get("blocks") or []) if is_shareholder_table(b)]


def _column_index(cells: list[str], *names: str) -> int | None:
    for index, cell in enumerate(cells):
        if any(name in cell for name in names):
            return index

    return None


def parse_shareholders(block: dict[str, Any]) -> list[dict[str, Any]]:
    """주주현황 표 -> 주주 목록. 열은 이름으로 찾는다.

    합계·소계 행도 버리지 않고 is_total 로 표시만 한다. '우선주 소계 55.77%' 같은
    값이 자본구조를 말할 때 그대로 근거가 되기 때문이다.
    """
    cells = [normalize_parse_key(cell) for cell in _header_cells(block)]

    holder_at = _column_index(cells, _HOLDER_COLUMN)
    if holder_at is None:
        return []

    ratio_at = _column_index(cells, _RATIO_COLUMN)
    shares_at = _column_index(cells, *_SHARES_COLUMNS)
    class_at = _column_index(cells, _CLASS_COLUMN)

    # 헤더가 없어 첫 행을 열 이름으로 쓴 경우 그 행은 데이터가 아니다
    rows = block.get("rows") or []
    if not block.get("header") and rows:
        rows = rows[1:]

    holders: list[dict[str, Any]] = []

    for row in rows:
        if holder_at >= len(row):
            continue

        name = (row[holder_at] or "").strip()
        if not name:
            continue

        holders.append(
            {
                "holder": name,
                "share_class": _cell(row, class_at),
                "shares": _cell(row, shares_at),
                "ratio": _cell(row, ratio_at),
                "is_total": normalize_parse_key(name) in _TOTAL_LABELS,
            }
        )

    return holders


def _cell(row: list[str], index: int | None) -> str | None:
    """행에서 한 칸을 꺼낸다. 열이 없거나 비어 있으면 None."""
    if index is None or index >= len(row):
        return None

    return (row[index] or "").strip() or None
