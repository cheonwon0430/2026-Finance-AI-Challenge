"""document_clean 파서 테스트. 네트워크를 타지 않는다."""
import pytest

from app.domain.company.api.dart_document import escape_bare_tags
from app.domain.company.parser.document_clean import (
    clean_document,
    parse_amount,
    render_text,
)


def _wrap(body: str) -> str:
    return f"<DOCUMENT><DOCUMENT-NAME>감사보고서</DOCUMENT-NAME><BODY>{body}</BODY></DOCUMENT>"


def _tables(clean: dict) -> list[dict]:
    return [b for s in clean["sections"] for b in s["blocks"] if b["type"] == "table"]


# ---------------------------------------------------------------------------
# 이스케이프 강화 - DART 원문의 XML 규격 위반
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw_text",
    [
        "<당기말> 잔액",        # 한글 가짜 태그
        "<당기/당기말> 합계",    # 슬래시 포함
        "A & B",              # 이스케이프 안 된 &
        "<1분기> 실적",         # 숫자로 시작하는 가짜 태그
        "100 < 200",          # 부등호
    ],
)
def test_깨진_원문도_텍스트로_보존된다(raw_text):
    clean = clean_document(_wrap(f"<P>{raw_text}</P>"))
    assert clean["sections"][0]["blocks"][0]["text"] == raw_text


def test_정상_실체참조는_해석된다():
    clean = clean_document(_wrap("<P>a &amp; b &#65;</P>"))
    assert clean["sections"][0]["blocks"][0]["text"] == "a & b A"


def test_이스케이프가_정상_태그는_건드리지_않는다():
    assert escape_bare_tags("<TABLE><TR></TR></TABLE>") == "<TABLE><TR></TR></TABLE>"
    assert escape_bare_tags("<!-- 주석 -->") == "<!-- 주석 -->"


# ---------------------------------------------------------------------------
# 표 격자 복원
# ---------------------------------------------------------------------------
COLSPAN_TABLE = _wrap("""
<TABLE ACLASS="FINANCE" WIDTH="814">
  <COLGROUP WIDTH="814"><COL WIDTH="223"></COL></COLGROUP>
  <THEAD>
    <TR><TH WIDTH="214">과 목</TH>
        <TH COLSPAN="2" WIDTH="287">제 11(당) 기</TH>
        <TH COLSPAN="2" WIDTH="286">제 10(전) 기</TH></TR>
  </THEAD>
  <TBODY>
    <TR><TE ACODE="11200000040000" ADELIM="0" ALEVEL="0">I. 유동자산</TE>
        <TE ADELIM="1" ACODE="11200000040000"></TE>
        <TE ADELIM="2" ACODE="11200000040000">24,087,860,030</TE>
        <TE ADELIM="3" ACODE="11200000040000"></TE>
        <TE ADELIM="4" ACODE="11200000040000">13,574,392,766</TE></TR>
    <TR><TE ACODE="11110000040000" ADELIM="0" ALEVEL="2">현금및현금성자산</TE>
        <TE ADELIM="1" ACODE="11110000040000">16,525,890,663</TE>
        <TE ADELIM="2" ACODE="11110000040000"></TE>
        <TE ADELIM="3" ACODE="11110000040000">3,806,711,356</TE>
        <TE ADELIM="4" ACODE="11110000040000"></TE></TR>
  </TBODY>
</TABLE>
""")


def test_COLSPAN_을_펼쳐_헤더와_본문_열수가_맞는다():
    table = _tables(clean_document(COLSPAN_TABLE))[0]
    assert [len(row) for row in table["header"]] == [5]
    assert {len(row) for row in table["rows"]} == {5}
    # COLSPAN=2 헤더는 두 칸으로 복제된다
    # '과 목' 은 자간을 벌린 것이라 붙는다. '제 11(당) 기' 는 숫자가 섞여 그대로 둔다.
    assert table["header"][0] == [
        "과목", "제 11(당) 기", "제 11(당) 기", "제 10(전) 기", "제 10(전) 기",
    ]


def test_ROWSPAN_이_다음_행을_채우고_spanned_로_표시된다():
    clean = clean_document(_wrap(
        "<TABLE><TBODY>"
        '<TR><TD ROWSPAN="2">구분</TD><TD>1행</TD></TR>'
        "<TR><TD>2행</TD></TR>"
        "</TBODY></TABLE>"
    ))
    table = _tables(clean)[0]
    assert table["rows"] == [["구분", "1행"], ["구분", "2행"]]
    # 두 번째 행의 '구분' 은 실제 셀이 아니라 펼쳐진 칸이다
    assert table["spanned"] == [[False, False], [True, False]]


def test_빈_열은_버리지_않는다():
    # 열 위치가 곧 기(期)를 의미하므로 빈 칸을 압축하면 안 된다
    table = _tables(clean_document(COLSPAN_TABLE))[0]
    assert table["rows"][0] == ["I. 유동자산", "", "24,087,860,030", "", "13,574,392,766"]


@pytest.mark.parametrize("cell", ["TD", "TE", "TH", "TU"])
def test_네_가지_셀_태그가_모두_같게_처리된다(cell):
    clean = clean_document(_wrap(
        f"<TABLE><TBODY><TR><{cell}>가</{cell}><{cell}>나</{cell}></TR></TBODY></TABLE>"
    ))
    assert _tables(clean)[0]["rows"] == [["가", "나"]]


def test_TU_의_회계기간_메타데이터를_보존한다():
    clean = clean_document(_wrap(
        "<TABLE><TBODY><TR>"
        '<TU AUNIT="PERIODFROM" AUNITVALUE="20250101">2025년 01월 01일</TU>'
        "<TD>부터</TD>"
        "</TR></TBODY></TABLE>"
    ))
    assert _tables(clean)[0]["units"] == [
        {"unit": "PERIODFROM", "value": "20250101", "raw": "2025년 01월 01일"}
    ]


# ---------------------------------------------------------------------------
# 재무제표 메타데이터와 숫자 정확성
# ---------------------------------------------------------------------------
def test_ACODE_ALEVEL_ADELIM_이_보존된다():
    accounts = _tables(clean_document(COLSPAN_TABLE))[0]["accounts"]
    assert accounts[0]["code"] == "11200000040000"
    assert accounts[0]["level"] == 0
    assert accounts[1]["code"] == "11110000040000"
    assert accounts[1]["level"] == 2


def test_소계와_세부항목이_서로_다른_delim_에_들어간다():
    # 이걸 구분하지 못하면 어느 기(期)의 값인지 알 수 없다
    accounts = _tables(clean_document(COLSPAN_TABLE))[0]["accounts"]
    assert [v["delim"] for v in accounts[0]["values"]] == [2, 4]   # 소계
    assert [v["delim"] for v in accounts[1]["values"]] == [1, 3]   # 세부항목


def test_금액_원문이_한_글자도_변하지_않는다():
    accounts = _tables(clean_document(COLSPAN_TABLE))[0]["accounts"]
    raws = [v["raw"] for a in accounts for v in a["values"]]
    assert raws == [
        "24,087,860,030", "13,574,392,766", "16,525,890,663", "3,806,711,356",
    ]
    # 모든 raw 는 원본 XML 에 그대로 존재해야 한다
    for raw in raws:
        assert raw in COLSPAN_TABLE


def test_해석값은_raw_옆에_따로_붙는다():
    accounts = _tables(clean_document(COLSPAN_TABLE))[0]["accounts"]
    first = accounts[0]["values"][0]
    assert first["raw"] == "24,087,860,030"
    assert first["value"] == 24087860030


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1,234", 1234),
        ("(1,234)", -1234),      # 회계 관례상 괄호는 음수
        ("△1,234", -1234),
        ("", None),
        ("-", None),
        ("해당사항없음", None),
        ("12.5", 12.5),
    ],
)
def test_금액_해석(raw, expected):
    assert parse_amount(raw) == expected


def test_손실_계정이라도_부호를_뒤집지_않는다():
    # 라벨을 보고 부호를 바꾸는 휴리스틱은 원문 값을 말없이 바꾸므로 쓰지 않는다
    assert parse_amount("5,000") == 5000


# ---------------------------------------------------------------------------
# 본문 순서와 정리
# ---------------------------------------------------------------------------
def test_문단과_표의_순서가_보존된다():
    # xmltodict 는 동명 태그를 배열로 묶어 이 순서를 잃는다. 이 작업의 존재 이유.
    clean = clean_document(_wrap(
        "<P>첫 문단</P>"
        "<TABLE><TBODY><TR><TD>표</TD></TR></TBODY></TABLE>"
        "<P>둘째 문단</P>"
        "<TABLE><TBODY><TR><TD>표2</TD></TR></TBODY></TABLE>"
    ))
    blocks = clean["sections"][0]["blocks"]
    assert [b["type"] for b in blocks] == ["paragraph", "table", "paragraph", "table"]
    assert blocks[0]["text"] == "첫 문단"
    assert blocks[2]["text"] == "둘째 문단"


def test_TITLE_에서_섹션이_나뉜다():
    clean = clean_document(_wrap(
        "<TITLE>감사보고서</TITLE><P>본문1</P>"
        "<TITLE>주석</TITLE><P>본문2</P>"
    ))
    assert [s["title"] for s in clean["sections"]] == ["감사보고서", "주석"]
    assert clean["sections"][1]["blocks"][0]["text"] == "본문2"


def test_레이아웃_속성과_빈_문단이_사라진다():
    clean = clean_document(_wrap(
        '<P></P><P USERMARK="F-18">내용</P><P></P>'
        '<TABLE WIDTH="600" BORDER="0">'
        '<COLGROUP WIDTH="600"><COL WIDTH="342"></COL></COLGROUP>'
        '<TBODY><TR HEIGHT="30"><TD ALIGN="CENTER" WIDTH="591">값</TD></TR></TBODY></TABLE>'
    ))
    dumped = str(clean)
    for noise in ("WIDTH", "ALIGN", "USERMARK", "COLGROUP", "HEIGHT", "BORDER"):
        assert noise not in dumped
    assert [b["type"] for b in clean["sections"][0]["blocks"]] == ["paragraph", "table"]


def test_문서_머리말과_요약을_뽑는다():
    clean = clean_document(
        "<DOCUMENT><DOCUMENT-NAME ACODE='00760'>감사보고서</DOCUMENT-NAME>"
        "<COMPANY-NAME>주식회사 센트비</COMPANY-NAME>"
        "<SUMMARY><EXTRACTION ACODE='TOT_ASSETS'>24087860030</EXTRACTION></SUMMARY>"
        "<BODY><P>본문</P></BODY></DOCUMENT>"
    )
    assert clean["document_name"] == "감사보고서"
    assert clean["company_name"] == "주식회사 센트비"
    assert clean["summary"]["TOT_ASSETS"] == "24087860030"


# ---------------------------------------------------------------------------
# 렌더링
# ---------------------------------------------------------------------------
def test_섹션_배너를_낸다():
    text = render_text(clean_document(_wrap("<TITLE>감   사   보   고   서</TITLE><P>본문</P>")))
    assert "===== 감사보고서 =====" in text
    assert "본문" in text


def test_ROWSPAN_으로_복제된_칸은_렌더링에서_비운다():
    clean = clean_document(_wrap(
        "<TABLE><TBODY>"
        '<TR><TD ROWSPAN="2">구분</TD><TD>1행</TD></TR>'
        "<TR><TD>2행</TD></TR>"
        "</TBODY></TABLE>"
    ))
    lines = [ln for ln in render_text(clean).splitlines() if ln.strip()]
    assert lines[0].startswith("구분")
    assert "구분" not in lines[1]   # 같은 값이 반복되지 않는다
    assert "2행" in lines[1]


# ---------------------------------------------------------------------------
# 자간 정리 - DART 는 자간을 벌리려고 글자 사이에 공백을 넣는다
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw_text, expected",
    [
        ("한   미   회   계   법   인", "한미회계법인"),   # 자간 벌린 회계법인명
        ("과                        목", "과목"),
        ("재 무 상 태 표", "재무상태표"),
        ("합  계", "합계"),
        ("I. 유 동 자 산", "I. 유동자산"),              # 앞 번호는 그대로 둔다
        ("Ⅰ. 영 업 수 익", "Ⅰ. 영업수익"),
    ],
)
def test_자간을_벌린_글자는_붙인다(raw_text, expected):
    clean = clean_document(_wrap(f"<P>{raw_text}</P>"))
    assert clean["sections"][0]["blocks"][0]["text"] == expected


@pytest.mark.parametrize(
    "raw_text",
    [
        "보통예금 및 큰 거래비용없이 현금으로",   # '및 큰' 이 '및큰' 으로 붙으면 안 된다
        "제 9 기",                          # 숫자가 섞이면 기수 표기다
        "제 6(당) 기",
        "주식회사 업스테이지",
        "A & B",                           # 짧은 영문도 대상이 아니다
        "(1) 당좌자산",
    ],
)
def test_본문과_기수_표기는_건드리지_않는다(raw_text):
    clean = clean_document(_wrap(f"<P>{raw_text}</P>"))
    assert clean["sections"][0]["blocks"][0]["text"] == raw_text


def test_연속_공백과_개행은_한_칸으로_줄인다():
    clean = clean_document(_wrap("<P>2026년  3월   23일</P><P>1.   회사의 개요</P>"))
    texts = [b["text"] for b in clean["sections"][0]["blocks"]]
    assert texts == ["2026년 3월 23일", "1. 회사의 개요"]


# ---------------------------------------------------------------------------
# 자간 정리 끄기 - normalize=False / --keep-spacing
# ---------------------------------------------------------------------------
SPACED_TABLE = _wrap("""
<TABLE ACLASS="FINANCE">
  <TBODY>
    <TR><TE ACODE="11000000000000" ADELIM="0" ALEVEL="0">자      산      총      계</TE>
        <TE ADELIM="1" ACODE="11000000000000">24,087,860,030</TE></TR>
  </TBODY>
</TABLE>
""")


def test_끄면_원문_자간이_그대로_남는다():
    clean = clean_document(_wrap("<P>한   미   회   계   법   인</P>"), normalize=False)
    assert clean["sections"][0]["blocks"][0]["text"] == "한   미   회   계   법   인"


def _first_label(normalize: bool) -> str:
    clean = clean_document(SPACED_TABLE, normalize=normalize)
    return clean["sections"][0]["blocks"][0]["accounts"][0]["label"]


def test_켜고_끈_결과가_실제로_다르다():
    assert _first_label(normalize=False) == "자      산      총      계"
    assert _first_label(normalize=True) == "자산총계"


def test_정규화를_켜도_금액_raw_는_후처리를_타지_않는다():
    # 이게 자간 정리를 파싱에서 떼어낸 이유다. raw 는 어떤 모드에서도 원문이어야 한다.
    for normalize in (True, False):
        values = clean_document(SPACED_TABLE, normalize=normalize)[
            "sections"][0]["blocks"][0]["accounts"][0]["values"]
        assert values[0]["raw"] == "24,087,860,030"
        assert values[0]["raw"] in SPACED_TABLE


def test_units_의_raw_도_보존된다():
    xml = _wrap(
        "<TABLE><TBODY><TR>"
        '<TU AUNIT="PERIODFROM" AUNITVALUE="20250101">2025년  01월  01일</TU>'
        "</TR></TBODY></TABLE>"
    )
    units = clean_document(xml)["sections"][0]["blocks"][0]["units"]
    assert units[0]["raw"] == "2025년  01월  01일"   # 연속 공백까지 그대로


def test_끄더라도_표_격자와_ACODE_는_그대로_동작한다():
    # --keep-spacing 은 자간 정리만 되돌린다. 나머지 정리는 항상 적용된다.
    table = clean_document(COLSPAN_TABLE, normalize=False)["sections"][0]["blocks"][0]
    assert [len(row) for row in table["header"]] == [5]
    assert {len(row) for row in table["rows"]} == {5}
    assert table["accounts"][0]["code"] == "11200000040000"
    assert "WIDTH" not in str(table)
