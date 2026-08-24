"""
DART 감사보고서 원문(document.xml)에서 재무상태표/손익계산서/현금흐름표를 파싱.

DART 감사보고서 XML 구조:
  <TITLE>재 무 상 태 표</TITLE>
  <TABLE ACLASS="EXTRACTION">...표지(기수/단위)...</TABLE>
  <TABLE ACLASS="FINANCE">
    <THEAD><TR><TH>과목</TH><TH COLSPAN=2>제9(당)기</TH><TH COLSPAN=2>제8(전)기</TH></TR></THEAD>
    <TBODY>
      <TR><TE ADELIM="0">유동자산</TE><TE ADELIM="1"></TE><TE ADELIM="2">426,122,695,612</TE>...</TR>
      ...
    </TBODY>
  </TABLE>

각 TR의 TE 중 ADELIM="0"이 계정과목명, 나머지 ADELIM 중 값이 채워진 셀만 순서대로
당기/전기 등 기간별 금액으로 취급한다(빈 스페이서 컬럼은 자동으로 걸러짐).
"""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

from lxml import etree as ET  # DART 원문은 주석 섹션에 이스케이프 안 된 "<당기말>" 같은
# 텍스트가 섞여 있어 표준 xml.etree는 깨진다. recover=True 파서로 관대하게 처리한다.

_PARSER = ET.XMLParser(recover=True)

TARGET_TITLES = {"재 무 상 태 표", "손 익 계 산 서", "현 금 흐 름 표", "자 본 변 동 표"}


def fetch_document_xml(rcept_no: str, api_key: str) -> str:
    """document.xml API는 zip으로 응답. 압축 해제해서 XML 텍스트 반환."""
    url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={api_key}&rcept_no={rcept_no}"
    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        name = zf.namelist()[0]
        return zf.read(name).decode("utf-8")


def _text(elem) -> str:
    return "".join(elem.itertext()).strip()


def parse_financial_statements(xml_text: str) -> dict:
    root = ET.fromstring(xml_text.encode("utf-8"), parser=_PARSER)

    statements = {}
    current_title = None
    for elem in root.iter():
        if elem.tag == "TITLE":
            t = _text(elem)
            current_title = t if t in TARGET_TITLES else current_title if t == "" else None
        elif elem.tag == "TABLE" and elem.get("ACLASS") == "FINANCE" and current_title:
            periods = []
            thead = elem.find("THEAD")
            if thead is not None:
                for th in thead.iter("TH"):
                    txt = _text(th)
                    if txt and txt != "과                        목" and "과목" not in txt:
                        periods.append(txt)

            rows = []
            tbody = elem.find("TBODY")
            if tbody is not None:
                for tr in tbody.findall("TR"):
                    tes = tr.findall("TE")
                    if not tes:
                        continue
                    label = _text(tes[0])
                    values = [_text(te) for te in tes[1:] if _text(te)]
                    if label:
                        rows.append({"label": label, "values": values})

            statements.setdefault(current_title, {"periods": periods, "rows": []})
            statements[current_title]["rows"].extend(rows)

    return statements


def summarize(statements: dict, keys: list[str]) -> dict:
    """전체 계정 중 요약에 쓸 핵심 항목만 label로 골라낸다."""
    out = {}
    for title, body in statements.items():
        picked = [r for r in body["rows"] if r["label"] in keys]
        out[title] = {"periods": body["periods"], "rows": picked}
    return out


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1])
    xml_text = path.read_text(encoding="utf-8")
    statements = parse_financial_statements(xml_text)
    for title, body in statements.items():
        print(f"=== {title} === periods={body['periods']}")
        for r in body["rows"][:15]:
            print(f"  {r['label']:<20} {r['values']}")
        print(f"  ... 총 {len(body['rows'])}행")
