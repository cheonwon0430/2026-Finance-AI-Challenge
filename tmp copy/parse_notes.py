"""
DART 감사보고서 원문(document.xml)의 '주석' 섹션에서 특정 하위 항목
(예: '회사의 개요', '특수관계자와의 거래', '자본금') 텍스트를 추출.

주석은 표(TABLE)가 아니라 P(문단) 태그로 구성되고, 각 하위항목은
"1.  회사의 개요" 처럼 숫자+제목으로 시작하는 P로 구분된다.
"""
import re
from lxml import etree as ET

_PARSER = ET.XMLParser(recover=True)
_SECTION_HEAD = re.compile(r"^\s*\d+\.\s*(.+)$")


def load_root(xml_path: str):
    text = open(xml_path, encoding="utf-8").read()
    return ET.fromstring(text.encode("utf-8"), parser=_PARSER)


def list_note_subsections(root) -> list[str]:
    """'주석' TITLE부터 다음 대제목 전까지, 숫자로 시작하는 P 헤더만 나열."""
    heads = []
    in_notes = False
    for elem in root.iter():
        if elem.tag == "TITLE":
            t = "".join(elem.itertext()).strip()
            if t == "주석":
                in_notes = True
                continue
            if in_notes and t and t != "주석":
                break
        if in_notes and elem.tag == "P":
            t = "".join(elem.itertext()).strip()
            m = _SECTION_HEAD.match(t)
            if m and len(t) < 60:
                heads.append(t)
    return heads


def extract_note_section(root, keyword: str, max_chars: int = 3000) -> str | None:
    """제목에 keyword가 포함된 주석 하위 섹션의 본문 텍스트를 모아서 반환."""
    in_notes = False
    in_target = False
    collected = []
    for elem in root.iter():
        if elem.tag == "TITLE":
            t = "".join(elem.itertext()).strip()
            if t == "주석":
                in_notes = True
                continue
            if in_notes and t and t != "주석":
                break  # 주석 섹션 끝 (다음 대제목 도달)

        if not in_notes:
            continue

        if elem.tag == "P":
            t = "".join(elem.itertext()).strip()
            m = _SECTION_HEAD.match(t)
            if m:
                # 새 하위 섹션 시작
                if in_target:
                    break  # 타겟 섹션이 끝나고 다음 섹션 시작 -> 종료
                in_target = keyword in t
                if in_target:
                    collected.append(t)
                continue

        if in_target and len(elem) == 0:  # 자식 요소가 없는 리프 노드만 (중복 방지)
            txt = (elem.text or "").strip()
            if txt:
                collected.append(txt)
            if sum(len(c) for c in collected) > max_chars:
                break

    return "\n".join(collected) if collected else None


if __name__ == "__main__":
    import sys

    root = load_root(sys.argv[1])
    if len(sys.argv) > 2:
        print(extract_note_section(root, sys.argv[2]))
    else:
        for h in list_note_subsections(root):
            print(h)
