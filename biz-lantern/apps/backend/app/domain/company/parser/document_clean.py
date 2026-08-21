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
    [7] 렌더링      정리된 dict -> 읽기 좋은 텍스트
    [8] CLI

사용법:
    python -m app.domain.company.parser.document_clean 20260414002654 > clean.json
    python -m app.domain.company.parser.document_clean 20260414002654 --text > doc.txt
    python -m app.domain.company.parser.document_clean data/raw/01685996/doc_x.xml --text

    # --save 는 리다이렉트 없이 data/clean/ 에 .json 과 .txt 를 함께 남긴다.
    # 둘 다 저장하므로 --save 를 주면 --text 는 무시된다.
    python -m app.domain.company.parser.document_clean 20260414002654 --save

    # --keep-spacing 은 자간 정리를 끄고 원문 공백을 그대로 둔다.
    # --save 와 함께 쓰면 {이름}_raw.json / {이름}_raw.txt 로 따로 남는다.
    python -m app.domain.company.parser.document_clean 20260414002654 --text --keep-spacing
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
    """
    grid: list[list[dict]] = []
    carry: dict[int, tuple[str, int]] = {}  # 열 인덱스 -> (값, 남은 행 수)

    for tr in trs:
        row: list[dict] = []
        cells = _cells(tr)
        index = 0
        col = 0

        # 셀이 남아있거나, 이 행에서 채워야 할 ROWSPAN 이 남아있는 동안 진행
        while index < len(cells) or any(c >= col for c in carry):
            if col in carry:
                # 위 행에서 ROWSPAN 으로 내려온 칸
                value, left = carry.pop(col)
                row.append({"text": value, "spanned": True})
                if left > 1:
                    carry[col] = (value, left - 1)
            elif index < len(cells):
                cell = cells[index]
                index += 1
                value = _text(cell)
                rowspan = _int_attr(cell, "ROWSPAN")
                colspan = _int_attr(cell, "COLSPAN")
                for offset in range(colspan):
                    row.append({"text": value, "spanned": offset > 0})
                    if rowspan > 1:
                        carry[col + offset] = (value, rowspan - 1)
                col += colspan
                continue
            else:
                # 셀은 떨어졌는데 더 뒤쪽 열에 ROWSPAN 이 남아있다. 사이를 빈 칸으로 메운다.
                row.append({"text": "", "spanned": False})
            col += 1

        grid.append(row)

    # 행마다 길이가 다르면(원본이 불규칙하면) 가장 긴 행에 맞춰 빈 칸을 채운다
    width = max((len(r) for r in grid), default=0)
    for row in grid:
        row.extend({"text": "", "spanned": False} for _ in range(width - len(row)))

    return grid


def _section_rows(table: ET.Element, tag: str) -> list[ET.Element]:
    return [tr for part in table.findall(tag) for tr in part.iter("TR")]


def _spanned_grid(grid: list[list[dict]]) -> list[list[bool]] | None:
    """펼쳐진 칸 표시. 전부 False 면 통째로 생략한다(정보 없이 파일만 커진다)."""
    flags = [[cell["spanned"] for cell in row] for row in grid]
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
        "rows": [[c["text"] for c in row] for row in body],
        "spanned": _spanned_grid(body),
    }

    accounts = _parse_accounts(body_trs)
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
# ADELIM 은 열 위치다. 1·2 가 당기 한 쌍, 3·4 가 전기 한 쌍이고 들여쓰기 수준에 따라
# 쌍 중 한쪽에만 값이 들어간다. 어느 기(期)인지 잃지 않도록 ADELIM 을 그대로 남긴다.
def _parse_accounts(trs: list[ET.Element]) -> list[dict]:
    accounts: list[dict] = []

    for tr in trs:
        cells = [c for c in _cells(tr) if c.get("ADELIM") is not None]
        if not cells:
            continue

        label_cell = next((c for c in cells if c.get("ADELIM") == _LABEL_DELIM), None)
        if label_cell is None:
            continue

        values = []
        for cell in cells:
            if cell.get("ADELIM") == _LABEL_DELIM:
                continue
            raw = _text(cell)
            if not raw:
                continue
            values.append({
                "delim": int(cell.get("ADELIM")),
                "raw": raw,                  # 원문 그대로. 절대 가공하지 않는다
                "value": parse_amount(raw),  # 해석 실패 시 None
            })

        level = label_cell.get("ALEVEL")
        accounts.append({
            "code": label_cell.get("ACODE"),
            "label": _text(label_cell),
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
_KEEP_VERBATIM = {"raw"}   # 금액과 날짜 원문. 어떤 경우에도 변하면 안 된다


def normalize_spacing(clean: dict) -> dict:
    """DART 특유의 자간 공백을 정리한 사본을 반환한다. 원본은 건드리지 않는다."""
    return _normalize_node(clean)


def _normalize_node(node):
    if isinstance(node, dict):
        return {
            key: value if key in _KEEP_VERBATIM else _normalize_node(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_normalize_node(item) for item in node]
    if isinstance(node, str):
        return _collapse_letter_spacing(_squeeze(node))
    return node


# ---------------------------------------------------------------------------
# [7] 렌더링 - 정리된 dict -> 읽기 좋은 텍스트
# ---------------------------------------------------------------------------
def _blank_spans(rows: list[list[str]], flags: list[list[bool]] | None) -> list[list[str]]:
    """펼쳐진 칸을 비운다. COLSPAN/ROWSPAN 으로 복제된 값이 반복되지 않게 한다."""
    if not flags:
        return rows
    return [
        [cell if not dup else "" for cell, dup in zip(row, row_flags)]
        for row, row_flags in zip(rows, flags)
    ]


def _render_table(block: dict) -> list[str]:
    header = _blank_spans(block.get("header") or [], block.get("header_spanned"))
    body = _blank_spans(block["rows"], block.get("spanned"))

    grid = [*header, *body]
    if not grid:
        return []

    widths = [max(len(row[i]) for row in grid if i < len(row)) for i in range(len(grid[0]))]

    def line(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()

    out = [line(row) for row in header]
    if header:
        out.append("-" * min(sum(widths) + 2 * (len(widths) - 1), 120))
    out.extend(line(row) for row in body)
    return out


def render_text(clean: dict) -> str:
    """정리된 dict -> 사람이 읽는 평문. 기존 xml_to_readable.py 와 같은 형식."""
    lines: list[str] = []

    for section in clean["sections"]:
        if section["title"]:
            lines.append("")
            lines.append(f"===== {section['title']} =====")

        for block in section["blocks"]:
            if block["type"] == "paragraph":
                lines.append(block["text"])
            else:
                lines.extend(_render_table(block))

    return "\n".join(lines)


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
    """정리 결과를 {name}.json 과 {name}.txt 로 함께 저장하고 두 경로를 반환."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / f"{name}.json"
    text_path = OUTPUT_DIR / f"{name}.txt"

    json_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    text_path.write_text(render_text(clean) + "\n", encoding="utf-8")

    return json_path, text_path


if __name__ == "__main__":
    import sys

    # python -m app.domain.company.parser.document_clean 20260414002654 > clean.json
    # python -m app.domain.company.parser.document_clean 20260414002654 --text
    # python -m app.domain.company.parser.document_clean 20260414002654 --save
    # python -m app.domain.company.parser.document_clean 20260414002654 --text --keep-spacing
    args = sys.argv[1:]
    as_text = "--text" in args
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
        print(render_text(cleaned) if as_text else json.dumps(cleaned, ensure_ascii=False, indent=2))
