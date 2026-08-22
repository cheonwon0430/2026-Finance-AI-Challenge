"""
DART 공시원문 XML 을 읽기 좋은 형태로 정리한다.

원본 그대로인 document.json 은 @WIDTH/@ALIGN/COLGROUP 같은 레이아웃 속성이 전부 남아
사람도 LLM 도 읽기 어렵다. 여기서는 그걸 걷어내고 본문 순서 · 표 격자 · 금액을 지킨다.

xmltodict 결과(document.json)가 아니라 원본 XML 을 입력으로 받는다.
xmltodict 는 동명 태그를 배열로 묶어버려서 P 와 TABLE 이 번갈아 나오던
본문 순서가 이미 소실되기 때문이다.

왜 라이브러리를 쓰지 않는가 (2026-08-20 실측, 근거는 아래 수치가 전부다)

    OpenDartReader 0.3.3  document() 는 zip 을 풀고 디코드해 원문 str 을 돌려주는 게 전부다.
                          우리 fetch_document_raw + extract_xml 과 결과가 sha256 까지 같다(15줄).
                          파싱·이스케이프·표 처리는 하지 않는다. 비상장은 finstate 도 (0,0) 이다.
    dart-fss 0.4.17       비상장 감사보고서에서도 재무제표를 뽑는다(뷰어 스크래핑). 유능하다.
                          같은 문서로 대조한 결과 금액 262셀 중 불일치 0 — 우리 파서와 완전히 같다.
                          다만 자본변동표(cis=None)·ACODE·본문 텍스트를 주지 않고,
                          arelle 포함 41개 패키지와 fake-useragent 를 끌고 온다.
    dart-fss-text         PyPI 미등재, python <3.13 핀, MongoDB 필수. 설치 자체가 불가능하다.

    즉 대체 가능한 건 API 호출 15줄뿐이고, 품이 든 escape_bare_tags(감사보고서 28%에 필수)와
    이 파일의 표·계정 구조화는 어느 쪽도 해주지 않는다. 현행 유지가 맞다.
    단 dart-fss 는 개발용 교차검증 도구로는 가치가 있다(프로덕션 의존성으로는 넣지 않는다).

계층 순서대로 위에서 아래로 읽으면 된다.

    [1] 설정
    [2] 원시 유틸    엘리먼트 -> 텍스트 / 숫자
    [3] 표 격자 복원  COLSPAN · ROWSPAN 을 펼쳐 모든 행의 열 수를 맞춘다
    [4] 재무제표 표   TE 의 ACODE/ALEVEL/ADELIM 을 살린다
    [5] 본문 순회    XML -> 정리된 dict
    [6] 자간 정리    DART 가 자간 대신 넣은 공백을 다듬는다 (끌 수 있다)
    [7] 렌더링      정리된 dict -> 마크다운
    [8] CLI

왜 마크다운인가 (2026-08-22 실측, 감사보고서 4건)

    이 결과물은 LLM 입력으로 들어간다. 고정폭 정렬 텍스트는 두 가지가 깨진다.
      1) 폭 계산이 len() 이라 2셀짜리 한글에서 정렬이 애초에 맞지 않는다.
      2) 더 중요한 건 열 모호성이다. 재무제표는 소계와 세부 금액을 서로 다른
         열에 넣는데, 평문에서는 그 둘이 같은 열처럼 보인다.

             Ⅰ. 유동자산                       11,010,943,287   <- 물리 2열(소계)
             1. 현금및현금성자산(주석3,9)  2,061,103,156         <- 물리 1열(세부)

    마크다운 파이프 표는 빈 칸을 명시하므로 이 모호성이 사라진다. 그리고
    ljust 패딩이 파이프보다 비싸서 결과가 오히려 작다. 즉 명확성과 토큰 비용이
    같은 방향이다.

    기(期)마다 두 칸이 반복되는 헤더는 합치지 않는다 (2026-08-22 판단)

        '제 10(당) 기말' 이 두 번 나오는 게 보기 싫어 두 열을 하나로 합쳤다가
        되돌렸다. 그 두 칸이 계층을 인코딩하고 있어서, 합치면 소계와 그 구성요소가
        같은 열에 놓여 읽는 쪽이 중복 합산할 수 있다.

            level 0 (Ⅰ.유동자산)  -> 바깥 칸 100 / 안쪽 칸   0
            level 1 ((1)당좌자산)  -> 바깥 칸  22 / 안쪽 칸 170
            level 2 (1.현금및…)    -> 바깥 칸   0 / 안쪽 칸 294

        ALEVEL 로는 복원되지 않는다(level 1 이 갈린다). 두 칸에 '세부'/'소계'
        이름을 붙이는 안도 폐기했다 - 현금흐름표에서는 부모(소계)와 자식(세목)이
        같은 칸에 들어가므로 그 이름이 틀린다. 바깥 칸의 정확한 의미는
        'level 0 대분류 총계' 이고 안쪽 칸은 '나머지 전부' 다.

사용법:
    python -m app.domain.company.parser.document_clean 20260414002654 > clean.json
    python -m app.domain.company.parser.document_clean 20260414002654 --md > doc.md
    python -m app.domain.company.parser.document_clean data/raw/01685996/doc_x.xml --md

    # --save 는 리다이렉트 없이 data/clean/ 에 .json 과 .md 를 함께 남긴다.
    # 둘 다 저장하므로 --save 를 주면 --md 는 무시된다.
    python -m app.domain.company.parser.document_clean 20260414002654 --save

    # --keep-spacing 은 자간 정리를 끄고 원문 공백을 그대로 둔다.
    # --save 와 함께 쓰면 {이름}_raw.json / {이름}_raw.md 로 따로 남는다.
    python -m app.domain.company.parser.document_clean 20260414002654 --md --keep-spacing
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.domain.company.api.dart_document import (
    escape_bare_tags,
    extract_xml,
    fetch_document_raw,
)

# ---------------------------------------------------------------------------
# [1] 설정
# ---------------------------------------------------------------------------
TITLE_TAGS = {"TITLE", "COVER-TITLE"}   # 여기서 새 섹션이 시작된다
# DART 문서의 셀 태그는 이 넷이 전부다 (코퍼스 실측: TD 7548, TE 7254, TH 1375, TU 119).
# TU 는 표지의 회계기간 날짜 셀로, AUNITVALUE 에 기계 판독용 값(20250101)을 들고 있다.
CELL_TAGS = ("TD", "TE", "TH", "TU")
PARAGRAPH_TAGS = {"P", "PGBRK"}         # 여기서 모아둔 텍스트를 한 문단으로 끊는다

_LABEL_DELIM = "0"                      # ADELIM="0" 이 계정과목 이름 열

OUTPUT_DIR = Path("data/clean")         # --save 결과를 두는 곳. data/ 는 gitignore 대상이다


# ---------------------------------------------------------------------------
# [2] 원시 유틸
# ---------------------------------------------------------------------------
# DART 는 자간을 벌리려고 글자 사이에 공백을 넣는다 ("한   미   회   계   법   인").
# 그렇다고 공백을 다 지우면 어절 띄어쓰기까지 사라지므로 두 단계로 나눈다.
_SPACES = re.compile(r"\s+")
_CJK_CHAR = re.compile(r"[가-힣㐀-䶿一-鿿]")
_NUMBERING = re.compile(r"^[IVXi-xⅠ-ⅫA-Za-z0-9()（）\[\].\-,·]+$")


def _squeeze(text: str) -> str:
    """[A] 개행과 연속 공백을 한 칸으로. 항상 안전하다."""
    return _SPACES.sub(" ", text).strip()


def _collapse_letter_spacing(text: str) -> str:
    """[B] 자간 흉내로 벌어진 글자를 붙인다.

    문자열 '전체' 가 1글자 토큰으로만 이뤄졌을 때만 손댄다. 일부만 붙이면
    본문의 '보통예금 및 큰 거래비용없이' 가 '및큰' 으로 망가진다.
    앞의 번호(I. / Ⅰ. / (1))는 그대로 두고, 숫자가 섞이면('제 9 기') 건드리지 않는다.
    """
    tokens = text.split(" ")
    head = ""

    # 'I. 유 동 자 산' 처럼 번호가 앞에 붙은 경우 번호는 남기고 뒤쪽만 본다
    if len(tokens) >= 3 and len(tokens[0]) > 1 and _NUMBERING.match(tokens[0]):
        head, tokens = tokens[0] + " ", tokens[1:]

    # 한글·한자 한 글자만 대상으로 한다. 'A & B' 같은 짧은 영문까지 붙이면 안 된다.
    if len(tokens) >= 2 and all(_CJK_CHAR.fullmatch(t) for t in tokens):
        return head + "".join(tokens)

    return text


def normalize_parse_key(text: str) -> str:
    """룰베이스 매칭 전용 key. whitespace 를 전부 제거한다.

        '부 채 및 자 본 총 계'
        '부  채  및  자  본  총  계'
        '부채 및 자본 총계'      -> 모두 '부채및자본총계'

    표시용 문자열과 분리해 두는 이유가 핵심이다. 공백을 다 지운 문자열은
    계정과목 이름을 찾는 데는 최적이지만 본문 문단에 적용하면
    '회사는당기중...' 이 되어 LLM/RAG 품질이 떨어진다. 그래서 이 함수는
    '이름'인 문자열(계정과목 라벨)에만 쓰고, 본문은 _squeeze 로만 다듬는다.

    비교하는 양쪽 모두에 걸어야 의미가 있다.

        normalize_parse_key(raw_label) == normalize_parse_key(target)
    """
    if not text:
        return text

    return _SPACES.sub("", text).strip()


def _text(elem: ET.Element) -> str:
    """엘리먼트 안의 모든 텍스트를 이어붙인다. 하위 태그는 걷어낸다.

    자간 정리는 여기서 하지 않는다. 파싱 단계는 원문을 그대로 들고 있고,
    다듬는 일은 [6] normalize_spacing() 이 맡는다.
    """
    return "".join(elem.itertext()).strip()


def _int_attr(elem: ET.Element, name: str) -> int:
    """COLSPAN/ROWSPAN 같은 정수 속성. 없거나 이상하면 1."""
    try:
        return max(1, int(elem.get(name, 1)))
    except (TypeError, ValueError):
        return 1


_PAREN = re.compile(r"^\((.*)\)$")


def parse_amount(raw: str) -> int | float | None:
    """금액 문자열 -> 숫자. 해석에 실패하면 None.

    원문(raw)을 절대 덮어쓰지 않는다. 이 결과는 raw 옆에 따로 붙는 참고값이다.
    회계 관례상 (1,234) 는 음수다. 빈 칸과 '-' 는 값 없음으로 본다.
    """
    s = raw.strip().replace(",", "").replace(" ", "")
    if s in ("", "-", "―", "–"):
        return None

    negative = False
    matched = _PAREN.match(s)
    if matched:
        negative, s = True, matched.group(1)

    if s.startswith(("△", "▲")):
        negative, s = True, s[1:]

    try:
        number = float(s) if "." in s else int(s)
    except ValueError:
        return None

    return -number if negative else number


# ---------------------------------------------------------------------------
# [3] 표 격자 복원 - COLSPAN · ROWSPAN 을 물리 격자로 펼친다
# ---------------------------------------------------------------------------
# 재무제표 THEAD 에는 COLSPAN="2" 헤더가 있다. 헤더 셀은 3개인데 본문은 5열이라
# 펼치지 않으면 헤더와 값이 통째로 어긋난다.
def _cells(tr: ET.Element) -> list[ET.Element]:
    return [c for c in tr if c.tag in CELL_TAGS]


def _expand_rows(trs: list[ET.Element]) -> list[list[dict]]:
    """TR 목록 -> 모든 행의 길이가 같은 격자.

    펼쳐진 칸은 spanned=True 로 표시한다. 값은 원본과 같지만 실제 셀이 아니므로
    합계를 낼 때 중복으로 세면 안 된다는 표시다.

    가로(COLSPAN)로 복제된 칸은 across=True 를 함께 단다. 렌더링할 때 둘을
    구분해야 하기 때문이다. 가로 복제는 원래 한 칸을 늘린 것이라 같은 행에서
    값이 반복되면 잡음일 뿐이고, 세로(ROWSPAN) 복제는 그 행의 묶음 이름이라
    남겨두는 편이 행 하나만 읽어도 뜻이 통한다.

    각 칸은 자기를 만든 엘리먼트를 elem 으로 들고 있는다. 이게 있어야
    [4] 가 ACODE/ADELIM 을 읽으면서 동시에 그 셀의 '물리 열 번호' 를 알 수 있다.
    elem 과 across 는 격자 안에서만 쓰고 JSON 으로는 elem 을 내보내지 않는다.
    """
    grid: list[list[dict]] = []
    carry: dict[int, tuple[str, int, ET.Element]] = {}  # 열 인덱스 -> (값, 남은 행 수, 엘리먼트)

    for tr in trs:
        row: list[dict] = []
        cells = _cells(tr)
        index = 0
        col = 0

        # 셀이 남아있거나, 이 행에서 채워야 할 ROWSPAN 이 남아있는 동안 진행
        while index < len(cells) or any(c >= col for c in carry):
            if col in carry:
                # 위 행에서 ROWSPAN 으로 내려온 칸
                value, left, elem = carry.pop(col)
                row.append({"text": value, "spanned": True, "across": False, "elem": elem})
                if left > 1:
                    carry[col] = (value, left - 1, elem)
            elif index < len(cells):
                cell = cells[index]
                index += 1
                value = _text(cell)
                rowspan = _int_attr(cell, "ROWSPAN")
                colspan = _int_attr(cell, "COLSPAN")
                for offset in range(colspan):
                    row.append(
                        {"text": value, "spanned": offset > 0, "across": offset > 0, "elem": cell}
                    )
                    if rowspan > 1:
                        carry[col + offset] = (value, rowspan - 1, cell)
                col += colspan
                continue
            else:
                # 셀은 떨어졌는데 더 뒤쪽 열에 ROWSPAN 이 남아있다. 사이를 빈 칸으로 메운다.
                row.append({"text": "", "spanned": False, "across": False, "elem": None})
            col += 1

        grid.append(row)

    # 행마다 길이가 다르면(원본이 불규칙하면) 가장 긴 행에 맞춰 빈 칸을 채운다
    width = max((len(r) for r in grid), default=0)
    for row in grid:
        row.extend(
            {"text": "", "spanned": False, "across": False, "elem": None}
            for _ in range(width - len(row))
        )

    return grid


def _section_rows(table: ET.Element, tag: str) -> list[ET.Element]:
    return [tr for part in table.findall(tag) for tr in part.iter("TR")]


def _spanned_grid(grid: list[list[dict]], key: str = "spanned") -> list[list[bool]] | None:
    """펼쳐진 칸 표시. 전부 False 면 통째로 생략한다(정보 없이 파일만 커진다)."""
    flags = [[cell[key] for cell in row] for row in grid]
    return flags if any(cell for row in flags for cell in row) else None


def _parse_table(table: ET.Element) -> dict:
    """TABLE 엘리먼트 -> {header, rows, ...}. 레이아웃 속성은 전부 버린다."""
    head = _expand_rows(_section_rows(table, "THEAD"))
    body_trs = _section_rows(table, "TBODY")
    if not body_trs and not head:
        # THEAD/TBODY 없이 TR 이 바로 오는 표도 있다
        body_trs = list(table.iter("TR"))
    body = _expand_rows(body_trs)

    block = {
        "type": "table",
        "class": table.get("ACLASS"),
        # 헤더가 여러 줄이면 그대로 여러 줄로 둔다. 마지막 줄만 쓰는 건 소비하는 쪽의 몫.
        "header": [[c["text"] for c in row] for row in head] or None,
        "header_spanned": _spanned_grid(head),
        # across = COLSPAN 으로 옆으로 늘어난 칸. 같은 행에서 값이 반복되므로
        # 렌더링할 때 비운다. spanned 는 ROWSPAN 까지 포함한 전체 복제 표시라
        # 합계를 낼 때 중복으로 세지 말라는 뜻이고, 둘은 쓰임이 다르다.
        "rows": [[c["text"] for c in row] for row in body],
        "spanned": _spanned_grid(body),
        "across": _spanned_grid(body, "across"),
    }

    accounts = _parse_accounts(body, head)
    if accounts:
        block["accounts"] = accounts

    units = _parse_units(table)
    if units:
        block["units"] = units

    return block


def _parse_units(table: ET.Element) -> list[dict]:
    """TU 셀의 AUNIT/AUNITVALUE. 표지의 회계기간을 문자열 파싱 없이 얻을 수 있다."""
    return [
        {"unit": tu.get("AUNIT"), "value": tu.get("AUNITVALUE"), "raw": _text(tu)}
        for tu in table.iter("TU")
        if tu.get("AUNIT")
    ]


# ---------------------------------------------------------------------------
# [4] 재무제표 표 - TE 의 ACODE/ALEVEL/ADELIM 을 살린다
# ---------------------------------------------------------------------------
# ACODE 는 DART 표준 계정과목 코드라 회사가 달라도 같다. 라벨 문자열 매칭보다 안정적이다.
#
# ADELIM 은 "당기/전기" 표시가 아니다. DART 가 부여한 논리 열 슬롯이고, 표 종류에
# 따라 물리 열 번호와 어긋난다. 실측(감사보고서 4건):
#
#     재무상태표·손익계산서·현금흐름표 (5열)  ADELIM 0,1,2,3,4  = 물리 0,1,2,3,4
#     자본변동표                    (4열)  ADELIM 0,1,5,6    = 물리 0,1,2,3
#                                          (1=자본금 5=이익잉여금 6=총계)
#
# 그래서 "delim 1·2 는 당기" 같은 규칙을 세우면 자본변동표를 조용히 오독한다.
# 값이 어느 기(期)/어느 항목인지는 물리 열(col)과 그 열의 헤더(header)로 답한다.
# delim 은 원문 속성이므로 지우지 않고 그대로 함께 남긴다.
def _parse_accounts(grid: list[list[dict]], head: list[list[dict]]) -> list[dict]:
    """펼쳐진 본문 격자 -> 계정과목 목록. head 는 열 제목을 붙이는 데 쓴다."""
    # 헤더가 여러 줄이면 가장 아래 줄이 실제 열 제목이다 (위는 묶음 제목).
    header_row = head[-1] if head else []

    def column_header(col: int) -> str | None:
        if col >= len(header_row):
            return None

        return header_row[col]["text"] or None

    accounts: list[dict] = []

    for row in grid:
        # spanned 칸은 COLSPAN/ROWSPAN 으로 복제된 사본이라 실제 셀이 아니다.
        cells = [
            (col, cell)
            for col, cell in enumerate(row)
            if not cell["spanned"]
            and cell["elem"] is not None
            and cell["elem"].get("ADELIM") is not None
        ]
        if not cells:
            continue

        label = next((cell for _, cell in cells if cell["elem"].get("ADELIM") == _LABEL_DELIM), None)
        if label is None:
            continue

        values = []
        for col, cell in cells:
            if cell["elem"].get("ADELIM") == _LABEL_DELIM:
                continue
            raw = cell["text"]
            if not raw:
                continue
            values.append({
                "delim": int(cell["elem"].get("ADELIM")),
                "col": col,                      # 물리 열 번호. 라벨 열이 보통 0
                "header": column_header(col),    # 그 열의 제목. 없으면 None
                "raw": raw,                      # 원문 그대로. 절대 가공하지 않는다
                "value": parse_amount(raw),      # 해석 실패 시 None
            })

        level = label["elem"].get("ALEVEL")
        display = label["text"]
        accounts.append({
            "code": label["elem"].get("ACODE"),
            "label": display,                          # 사람·LLM 이 읽을 문자열
            "key": normalize_parse_key(display),       # 룰베이스 매칭용
            "level": int(level) if level is not None and level.isdigit() else None,
            "values": values,
        })

    return accounts


# ---------------------------------------------------------------------------
# [5] 본문 순회 - XML -> 정리된 dict
# ---------------------------------------------------------------------------
class _Collector:
    """섹션과 블록을 순서대로 쌓는다. blocks 가 단일 배열인 것이 이 방식의 핵심."""

    def __init__(self) -> None:
        self.sections: list[dict] = []
        self._buffer: list[str] = []
        self._open_section(None)

    def _open_section(self, title: str | None) -> None:
        self.sections.append({"title": title, "blocks": []})

    @property
    def _blocks(self) -> list[dict]:
        return self.sections[-1]["blocks"]

    def add_text(self, text: str) -> None:
        if text:
            self._buffer.append(text)

    def flush(self) -> None:
        """모아둔 텍스트를 문단 하나로 끊는다."""
        if self._buffer:
            self._blocks.append({"type": "paragraph", "text": " ".join(self._buffer)})
            self._buffer.clear()

    def add_table(self, block: dict) -> None:
        self.flush()
        self._blocks.append(block)

    def start_section(self, title: str) -> None:
        self.flush()
        self._open_section(title)

    def result(self) -> list[dict]:
        self.flush()
        # 제목도 내용도 없는 껍데기 섹션은 버린다
        return [s for s in self.sections if s["title"] or s["blocks"]]


def _walk(elem: ET.Element, out: _Collector) -> None:
    for child in elem:
        tag = child.tag

        if tag in TITLE_TAGS:
            out.start_section(_text(child))
        elif tag == "TABLE":
            out.add_table(_parse_table(child))   # 표 안으로는 더 내려가지 않는다
        elif tag in PARAGRAPH_TAGS:
            out.add_text(_text(child))
            out.flush()
        elif len(child) == 0:
            out.add_text(_text(child))
        else:
            _walk(child, out)


def clean_document(xml_text: str, *, normalize: bool = True) -> dict:
    """공시원문 XML 텍스트 -> 정리된 dict.

    normalize=False 면 자간 정리를 건너뛰고 원문 공백을 그대로 남긴다.
    """
    root = ET.fromstring(escape_bare_tags(xml_text))

    summary = {}
    for extraction in root.iter("EXTRACTION"):
        code = extraction.get("ACODE")
        if code:
            summary[code] = _text(extraction)

    collector = _Collector()
    body = root.find("BODY")
    _walk(body if body is not None else root, collector)

    result = {
        "document_name": root.findtext("DOCUMENT-NAME", default="").strip() or None,
        "company_name": root.findtext("COMPANY-NAME", default="").strip() or None,
        "summary": summary,
        "sections": collector.result(),
    }

    return normalize_spacing(result) if normalize else result


# ---------------------------------------------------------------------------
# [6] 자간 정리 - 파싱이 끝난 결과를 한 번 훑으며 다듬는다
# ---------------------------------------------------------------------------
# 파싱 단계와 분리해 둔 이유가 두 가지다.
#   1) --keep-spacing 으로 통째로 끌 수 있다.
#   2) 'raw' 를 건드리지 않는다는 보장이 이 한 곳에만 있으면 된다.
#
# 문자열이라고 다 같은 문자열이 아니다. 어느 필드가 '이름'이고 어느 필드가
# '본문'인지에 따라 세기를 달리한다. 이걸 구분하지 않고 전부에 자간 붙임을
# 걸면 '그 중 한 곳' 이 '그중한곳' 이 되어 본문 품질이 떨어진다.
#
#     raw            아무것도 하지 않는다. 금액·날짜 원문이다
#     text           _squeeze 만. 문단 본문이라 어절 띄어쓰기를 지켜야 한다
#     그 외(이름류)   _squeeze + 자간 붙임. title / label / header / rows 셀 등
_KEEP_VERBATIM = {"raw"}    # 금액과 날짜 원문. 어떤 경우에도 변하면 안 된다
_BODY_TEXT = {"text"}       # 문단 본문. 공백을 줄이기만 하고 붙이지는 않는다


def normalize_spacing(clean: dict) -> dict:
    """DART 특유의 자간 공백을 정리한 사본을 반환한다. 원본은 건드리지 않는다."""
    return _normalize_node(clean)


def _normalize_node(node, field: str | None = None):
    # field 는 이 문자열이 어느 키 밑에 있었는지다. 리스트를 지날 때도 그대로
    # 물고 내려가야 rows(2중 리스트) 안의 셀까지 같은 규칙이 적용된다.
    if isinstance(node, dict):
        return {key: _normalize_node(value, key) for key, value in node.items()}
    if isinstance(node, list):
        return [_normalize_node(item, field) for item in node]
    if isinstance(node, str):
        if field in _KEEP_VERBATIM:
            return node
        if field in _BODY_TEXT:
            return _squeeze(node)
        return _collapse_letter_spacing(_squeeze(node))
    return node


# ---------------------------------------------------------------------------
# [7] 렌더링 - 정리된 dict -> 마크다운
# ---------------------------------------------------------------------------
# 여기서 하는 가공은 전부 '보여주기' 용이다. clean dict 자체(rows 격자)는
# 원본 그대로 남으므로, 렌더링이 마음에 안 들면 JSON 쪽에서 다시 뽑으면 된다.
def _md_cell(text: str) -> str:
    """표 칸 안에서 격자를 깨뜨리는 문자를 막는다.

    현 코퍼스에는 파이프도 개행도 0건이지만, 한 건만 섞여도 그 행 전체의
    열이 밀린다. 값을 버리는 대신 이스케이프한다.
    """
    return text.replace("|", r"\|").replace("\n", "<br>")


def _flatten_header(header: list[list[str]], width: int) -> list[str]:
    """여러 줄 헤더 -> 한 줄. 마크다운 표는 헤더 행을 하나만 받는다.

    열별로 위에서 아래로 읽으며 중복을 지우고 공백으로 잇는다.
    ('제10기' / '유동') 두 줄이면 '제10기 유동' 이 된다.
    """
    flat = []
    for col in range(width):
        seen = dict.fromkeys(row[col] for row in header if col < len(row) and row[col])
        flat.append(" ".join(seen))

    return flat


def _blank_across(rows: list[list[str]], flags: list[list[bool]] | None) -> list[list[str]]:
    """본문 행에서 COLSPAN 으로 옆으로 복제된 칸을 비운다.

    표지의 회계기간 셀처럼 한 칸을 두 칸으로 늘려놓은 경우, 그대로 두면
    같은 문장이 한 행에 두 번 찍힌다. 원래 한 칸이었으니 하나만 남기면 된다.

    두 가지는 건드리지 않는다.
      - ROWSPAN 복제: 세로로 내려온 값은 그 행의 묶음 이름이라, 남아 있어야
        행 하나만 떼어 읽어도 뜻이 통한다.
      - 헤더 행: 열마다 이름이 있어야 한다. '당기 | 당기' 가 '당기 | ' 보다 낫다.
    """
    if not flags:
        return rows

    return [
        [("" if dup else cell) for cell, dup in zip(row, row_flags)]
        for row, row_flags in zip(rows, flags)
    ]


def _render_table(block: dict) -> list[str]:
    """표 블록 -> 마크다운 줄 목록."""
    header = [list(row) for row in (block.get("header") or [])]
    rows = [list(row) for row in _blank_across(block["rows"], block.get("across"))]

    width = max((len(row) for row in header + rows), default=0)
    if width == 0:
        return []

    # 마크다운 표는 모든 행의 칸 수가 같아야 한다
    for row in header + rows:
        row.extend([""] * (width - len(row)))

    # 1열짜리는 표가 아니라 레이아웃용 껍데기다(문서당 10~12개). 문단으로 흘린다.
    if width == 1:
        return [row[0] for row in header + rows if row[0].strip()]

    flat = _flatten_header(header, width)

    def line(row: list[str]) -> str:
        return "| " + " | ".join(_md_cell(cell) for cell in row) + " |"

    # 헤더가 없는 표도 있다(문서당 25~51개). 마크다운은 헤더 행을 요구하므로
    # 그 경우엔 빈 헤더로 연다. spanned 칸은 비우지 않고 값을 반복해서 남기는데,
    # 각 행이 혼자서도 읽히는 편이 LLM 에 유리하기 때문이다.
    return [line(flat), "|" + "---|" * len(flat), *(line(row) for row in rows)]


def render_markdown(clean: dict) -> str:
    """정리된 dict -> 마크다운. LLM 입력으로 그대로 넣을 수 있는 형태다."""
    lines: list[str] = []

    # 어느 회사의 무슨 문서인지가 본문에 늘 적혀 있지는 않다. 맨 위에 못박아 둔다.
    title = " ".join(x for x in (clean["company_name"], clean["document_name"]) if x)
    if title:
        lines += [f"# {title}", ""]

    for section in clean["sections"]:
        if section["title"]:
            lines += ["", f"## {section['title']}", ""]

        for block in section["blocks"]:
            if block["type"] == "paragraph":
                lines += [block["text"], ""]
                continue

            rendered = _render_table(block)
            if rendered:
                lines += [*rendered, ""]

    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# [8] CLI
# ---------------------------------------------------------------------------
def load_xml(source: str) -> str:
    """접수번호면 API 를 부르고, .xml 경로면 그 파일을 읽는다.

    이미 받아둔 원본으로 네트워크 없이 반복 테스트할 수 있게 두 갈래를 둔다.
    """
    path = Path(source)
    if path.suffix.lower() == ".xml":
        return path.read_text(encoding="utf-8")

    documents = extract_xml(fetch_document_raw(source))
    return next(iter(documents.values()))


def save_outputs(clean: dict, name: str) -> tuple[Path, Path]:
    """정리 결과를 {name}.json 과 {name}.md 로 함께 저장하고 두 경로를 반환.

    .json 은 구조 원본이다. 금액 계산·DB 적재는 이쪽을 쓴다.
    .md 는 LLM 입력용이다. 사람이 읽기에도 이쪽이 낫다.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / f"{name}.json"
    md_path = OUTPUT_DIR / f"{name}.md"

    json_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(clean), encoding="utf-8")

    return json_path, md_path


if __name__ == "__main__":
    import sys

    # python -m app.domain.company.parser.document_clean 20260414002654 > clean.json
    # python -m app.domain.company.parser.document_clean 20260414002654 --md
    # python -m app.domain.company.parser.document_clean 20260414002654 --save
    # python -m app.domain.company.parser.document_clean 20260414002654 --md --keep-spacing
    args = sys.argv[1:]
    as_md = "--md" in args
    as_save = "--save" in args
    keep_spacing = "--keep-spacing" in args
    target = next(a for a in args if not a.startswith("--"))

    cleaned = clean_document(load_xml(target), normalize=not keep_spacing)

    if as_save:
        # 접수번호면 접수번호가, .xml 경로면 그 파일 이름이 그대로 stem 이 된다.
        # 두 모드가 서로를 덮어쓰지 않게 원문 보존본에는 _raw 를 붙인다.
        name = Path(target).stem + ("_raw" if keep_spacing else "")
        for path in save_outputs(cleaned, name):
            print(f"저장: {path}")
    else:
        print(render_markdown(cleaned) if as_md else json.dumps(cleaned, ensure_ascii=False, indent=2))
