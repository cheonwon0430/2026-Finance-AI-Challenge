"""document_clean 파서 테스트. 네트워크를 타지 않는다."""
import re

import pytest

from app.domain.company.api.dart_document import escape_bare_tags
from app.domain.company.parser.document_clean import (
    clean_document,
    normalize_parse_key,
    parse_amount,
    render_markdown,
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


def test_소계와_세부항목이_서로_다른_열에_들어간다():
    # 빈 칸을 압축해 버리면 소계와 세부항목이 같은 열에 있는 것처럼 보인다
    accounts = _tables(clean_document(COLSPAN_TABLE))[0]["accounts"]
    assert [v["col"] for v in accounts[0]["values"]] == [2, 4]   # 소계
    assert [v["col"] for v in accounts[1]["values"]] == [1, 3]   # 세부항목


def test_값마다_물리_열과_그_열의_헤더가_붙는다():
    # '어느 기(期)인가' 는 헤더 문자열로 답한다. delim 을 해석해서 맞히지 않는다.
    accounts = _tables(clean_document(COLSPAN_TABLE))[0]["accounts"]
    assert [(v["col"], v["header"]) for v in accounts[1]["values"]] == [
        (1, "제 11(당) 기"),
        (3, "제 10(전) 기"),
    ]


# 자본변동표는 ADELIM 이 물리 열과 어긋난다. 실제 감사보고서에서 뽑은 구조다.
EQUITY_TABLE = _wrap("""
<TABLE ACLASS="FINANCE">
  <THEAD>
    <TR><TH>과 목</TH><TH>자 본 금</TH><TH>이 익잉여금</TH><TH>총 계</TH></TR>
  </THEAD>
  <TBODY>
    <TR><TE ADELIM="0">2024.01.01 (전기초)</TE>
        <TE ADELIM="1">4,000,000,000</TE>
        <TE ADELIM="5">10,213,564,720</TE>
        <TE ADELIM="6">14,213,564,720</TE></TR>
  </TBODY>
</TABLE>
""")


def test_ADELIM_은_물리_열_번호가_아니다():
    # 자본변동표는 4열인데 ADELIM 이 0/1/5/6 으로 온다. 'delim 1·2 는 당기' 같은
    # 규칙을 세우면 이 표를 조용히 오독한다. 그래서 col 을 따로 들고 있는다.
    values = _tables(clean_document(EQUITY_TABLE))[0]["accounts"][0]["values"]
    assert [v["delim"] for v in values] == [1, 5, 6]
    assert [v["col"] for v in values] == [1, 2, 3]
    # '이 익잉여금' 은 DART 가 낸 그대로다. 앞 한 글자만 떼어놓은 표기라 자간 정리가
    # 손대지 않는다 - '그 중요한' 같은 정상 어절까지 붙여버릴 위험이 더 크기 때문이다.
    assert [v["header"] for v in values] == ["자본금", "이 익잉여금", "총계"]


def test_헤더가_없으면_열_헤더는_None_이다():
    clean = clean_document(_wrap(
        '<TABLE ACLASS="FINANCE"><TBODY><TR>'
        '<TE ADELIM="0">자본금</TE><TE ADELIM="1">100</TE>'
        "</TR></TBODY></TABLE>"
    ))
    assert _tables(clean)[0]["accounts"][0]["values"][0]["header"] is None


# ---------------------------------------------------------------------------
# 매칭용 key - 표시용 문자열과 분리한다
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw_text",
    [
        "부 채 및 자 본 총 계",
        "부  채  및  자  본  총  계",
        "부채 및 자본 총계",
        "부채및자본총계",
    ],
)
def test_공백_표기가_달라도_같은_key_가_된다(raw_text):
    # DART 는 같은 계정과목을 문서마다 다른 간격으로 준다. 어느 쪽이 와도 하나로 모인다.
    assert normalize_parse_key(raw_text) == "부채및자본총계"


def test_양쪽을_모두_normalize_해야_비교가_된다():
    assert normalize_parse_key("부  채  및  자  본  총  계") == normalize_parse_key("부채 및 자본 총계")


def test_계정과목에_표시용_라벨과_매칭용_key_가_함께_붙는다():
    account = _tables(clean_document(SPACED_TABLE))[0]["accounts"][0]
    assert account["label"] == "자산총계"          # 사람·LLM 이 읽는 쪽
    assert account["key"] == "자산총계"            # 룰베이스가 찾는 쪽


def test_자간_정리를_꺼도_key_는_공백이_없다():
    # 표시용은 원문을 지키더라도 매칭은 되어야 한다
    account = clean_document(SPACED_TABLE, normalize=False)[
        "sections"][0]["blocks"][0]["accounts"][0]
    assert account["label"] == "자      산      총      계"
    assert account["key"] == "자산총계"


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
# 마크다운 렌더링
# ---------------------------------------------------------------------------
_MD_SEPARATOR = re.compile(r"^\|(?:\s*-+\s*\|)+$")
_MD_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def _md_rows(markdown: str) -> list[list[str]]:
    """마크다운에서 표 행만 뽑아 칸 목록으로 돌려준다.

    구분선만 버린다. 헤더가 없는 표는 빈 헤더 행으로 열리는데 그것도 한 행으로
    센다(항상 rows[0] 이 헤더). 이스케이프된 파이프에서는 칸을 나누지 않는다.
    """
    rows = []
    for line in markdown.splitlines():
        if not line.startswith("|") or _MD_SEPARATOR.match(line):
            continue
        rows.append([cell.strip() for cell in _MD_UNESCAPED_PIPE.split(line.strip("|"))])

    return rows


def test_섹션_제목을_h2_로_낸다():
    md = render_markdown(clean_document(_wrap("<TITLE>감   사   보   고   서</TITLE><P>본문</P>")))
    assert "## 감사보고서" in md
    assert "본문" in md


def test_모든_행의_칸_수가_같다():
    # 마크다운 표는 칸 수가 어긋나면 그 행 전체가 밀린다
    md = render_markdown(clean_document(COLSPAN_TABLE))
    assert {len(row) for row in _md_rows(md)} == {5}   # 과목 + 기(期)당 2칸


def test_ROWSPAN_으로_내려온_값은_각_행에_남긴다():
    # 세로로 복제된 값은 그 행의 묶음 이름이다. 행 하나만 떼어 읽어도 뜻이 통해야 한다.
    clean = clean_document(_wrap(
        "<TABLE><TBODY>"
        '<TR><TD ROWSPAN="2">구분</TD><TD>1행</TD></TR>'
        "<TR><TD>2행</TD></TR>"
        "</TBODY></TABLE>"
    ))
    assert _md_rows(render_markdown(clean))[1:] == [["구분", "1행"], ["구분", "2행"]]


def test_COLSPAN_으로_늘어난_칸은_렌더링에서_비운다():
    # 가로 복제는 원래 한 칸을 늘린 것이라, 그대로 두면 같은 값이 한 행에 두 번 찍힌다
    clean = clean_document(_wrap(
        '<TABLE><TBODY><TR><TD COLSPAN="2">2025년 12월 31일 현재</TD><TD>비고</TD></TR></TBODY></TABLE>'
    ))
    assert _md_rows(render_markdown(clean))[1:] == [["2025년 12월 31일 현재", "", "비고"]]


def test_칸_안의_파이프와_개행을_이스케이프한다():
    # 한 건만 섞여도 그 행의 열이 통째로 밀린다
    clean = clean_document(_wrap("<TABLE><TBODY><TR><TD>가|나</TD><TD>다</TD></TR></TBODY></TABLE>"))
    md = render_markdown(clean)
    assert r"가\|나" in md
    assert {len(row) for row in _md_rows(md)} == {2}


def test_한_열짜리_표는_표로_그리지_않는다():
    # 문서당 10여 개가 레이아웃용 껍데기다. 파이프를 둘러봐야 잡음만 는다.
    clean = clean_document(_wrap("<TABLE><TBODY><TR><TD>표지 문구</TD></TR></TBODY></TABLE>"))
    md = render_markdown(clean)
    assert "표지 문구" in md
    assert "|" not in md


def test_재무제표는_기별_두_칸을_그대로_둔다():
    # 두 칸은 계층을 인코딩한다. 실측상 level 0 은 100/100 바깥 칸, level 2 는
    # 294/294 안쪽 칸이다. 합치면 소계와 그 구성요소가 같은 열에 놓여 읽는 쪽이
    # 중복 합산할 수 있고, ALEVEL 로는 복원되지 않는다(level 1 이 170/22 로 갈린다).
    rows = _md_rows(render_markdown(clean_document(COLSPAN_TABLE)))
    assert rows[0] == ["과목", "제 11(당) 기", "제 11(당) 기", "제 10(전) 기", "제 10(전) 기"]
    assert rows[1] == ["I. 유동자산", "", "24,087,860,030", "", "13,574,392,766"]
    assert rows[2] == ["현금및현금성자산", "16,525,890,663", "", "3,806,711,356", ""]


def test_금액은_하나도_잃지_않는다():
    md = render_markdown(clean_document(COLSPAN_TABLE))
    for raw in ("24,087,860,030", "13,574,392,766", "16,525,890,663", "3,806,711,356"):
        assert raw in md


def test_헤더가_같아도_열을_합치지_않는다():
    # 합치면 서로 다른 값이 뭉개진다. 표 종류를 가리지 않고 그대로 둔다.
    clean = clean_document(_wrap(
        "<TABLE>"
        '<THEAD><TR><TH>구분</TH><TH COLSPAN="2">당기</TH></TR></THEAD>'
        "<TBODY><TR><TD>매출</TD><TD>100</TD><TD>200</TD></TR></TBODY>"
        "</TABLE>"
    ))
    rows = _md_rows(render_markdown(clean))
    assert rows[0] == ["구분", "당기", "당기"]
    assert rows[1] == ["매출", "100", "200"]   # 100 과 200 이 뭉개지지 않는다


def test_여러_줄_헤더는_한_줄로_평탄화된다():
    clean = clean_document(_wrap(
        "<TABLE><THEAD>"
        '<TR><TH>구분</TH><TH COLSPAN="2">제11기</TH></TR>'
        "<TR><TH></TH><TH>유동</TH><TH>비유동</TH></TR>"
        "</THEAD><TBODY><TR><TD>자산</TD><TD>1</TD><TD>2</TD></TR></TBODY></TABLE>"
    ))
    assert _md_rows(render_markdown(clean))[0] == ["구분", "제11기 유동", "제11기 비유동"]


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
def test_자간을_벌린_이름은_붙인다(raw_text, expected):
    # 제목·계정과목처럼 '이름' 인 문자열에만 적용한다. 본문 문단은 대상이 아니다.
    clean = clean_document(_wrap(f"<TITLE>{raw_text}</TITLE>"))
    assert clean["sections"][0]["title"] == expected


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
def test_기수_표기와_어절은_이름_자리에서도_건드리지_않는다(raw_text):
    clean = clean_document(_wrap(f"<TITLE>{raw_text}</TITLE>"))
    assert clean["sections"][0]["title"] == raw_text


def test_본문_문단은_자간을_붙이지_않는다():
    # 본문까지 붙이면 '그 중 한 곳' 이 '그중한곳' 이 된다. 표시용과 매칭용을
    # 나눠 둔 이유가 이것이고, 매칭은 normalize_parse_key 가 따로 맡는다.
    clean = clean_document(_wrap("<P>그 중 한 곳</P><P>한   미   회   계   법   인</P>"))
    texts = [b["text"] for b in clean["sections"][0]["blocks"]]
    assert texts == ["그 중 한 곳", "한 미 회 계 법 인"]


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
